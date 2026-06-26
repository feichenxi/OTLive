import pyaudio
import socket
import threading
import queue
import time
import array
import asyncio
import subprocess
import math
import sys
import os
import wave
import struct
import pymysql
from collections import deque
from typing import Optional, Dict, List, Tuple
from common.logger import get_logger
from common.database_manager import get_database_manager


def high_precision_sleep(duration: float):
    """高精度睡眠函数 - 使用perf_counter实现微秒级精度"""
    end_time = time.perf_counter() + duration
    while time.perf_counter() < end_time:
        pass


def normalize_volume(audio_data: bytes, target_peak: float = 0.85) -> bytes:
    """音量归一化 - 将音频峰值调整到目标水平
    
    Args:
        audio_data: 原始音频数据（16位PCM）
        target_peak: 目标峰值（0.0-1.0），推荐0.70-0.85
    
    Returns:
        归一化后的音频数据
    """
    try:
        samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
        
        # 找到最大绝对值
        max_abs = 0
        for sample in samples:
            abs_sample = abs(sample)
            if abs_sample > max_abs:
                max_abs = abs_sample
        
        if max_abs == 0:
            return audio_data
        
        current_peak = max_abs / 32767.0
        normalization_factor = target_peak / current_peak
        
        # 归一化处理
        normalized_samples = []
        for sample in samples:
            new_sample = int(round(sample * normalization_factor))
            new_sample = max(-32768, min(32767, new_sample))
            normalized_samples.append(new_sample)
        
        return struct.pack(f'<{len(normalized_samples)}h', *normalized_samples)
    except Exception as e:
        # 如果归一化失败，返回原始数据
        return audio_data


def apply_fade_in_out(audio_data: bytes, sample_rate: int = 48000, fade_duration_ms: float = 20.0) -> bytes:
    """淡入淡出效果 - 消除音频开始和结束时的爆音
    
    Args:
        audio_data: 原始音频数据（16位PCM）
        sample_rate: 采样率
        fade_duration_ms: 淡入淡出时长（毫秒），推荐20-30ms
    
    Returns:
        应用淡入淡出后的音频数据
    """
    try:
        samples = list(struct.unpack(f'<{len(audio_data)//2}h', audio_data))
        num_samples = len(samples)
        
        # 计算淡入淡出的样本数
        fade_samples = int(fade_duration_ms * sample_rate / 1000)
        fade_samples = min(fade_samples, num_samples // 2)
        
        # 应用淡入（使用余弦曲线实现平滑过渡）
        for i in range(fade_samples):
            factor = 0.5 - 0.5 * math.cos((i / fade_samples) * math.pi)
            samples[i] = max(-32768, min(32767, int(round(samples[i] * factor))))
        
        # 应用淡出
        for i in range(fade_samples):
            idx = num_samples - fade_samples + i
            factor = 0.5 - 0.5 * math.cos(((fade_samples - i) / fade_samples) * math.pi)
            samples[idx] = max(-32768, min(32767, int(round(samples[idx] * factor))))
        
        return struct.pack(f'<{num_samples}h', *samples)
    except Exception as e:
        # 如果淡入淡出失败，返回原始数据
        return audio_data


class AudioRecorder:
    """音频录制器 - Windows PyAudio实现"""

    def __init__(self, device=None, sample_rate=16000, channels=2, chunk_size=1024):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.is_running = False
        self.audio_queue = queue.Queue(maxsize=100)
        self.logger = get_logger()
        
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            self._stream = None
            self._thread = None
            self._recording = False
            self.logger.info("Windows音频录制器初始化成功")
        except ImportError:
            self.logger.error("PyAudio未安装")
            raise

    def start(self):
        if self.is_running:
            self.logger.warning("音频录制器已经在运行中")
            return True

        try:
            self.logger.info("正在启动Windows音频录制器...")
            self._start_windows_recording()
            self.is_running = True
            self.logger.info("音频录制器已启动")
            return True
        except Exception as e:
            self.logger.error(f"音频录制器启动失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _start_windows_recording(self):
        """Windows平台录制循环"""
        self._recording = True
        self._thread = threading.Thread(target=self._windows_record_loop, daemon=True)
        self._thread.start()

    def _windows_record_loop(self):
        """Windows录制循环"""
        try:
            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=None,
                frames_per_buffer=self.chunk_size
            )

            while self._recording:
                try:
                    data = self._stream.read(self.chunk_size, exception_on_overflow=False)

                    # 如果是2通道，转换为1通道（取左右声道的平均值）
                    if self.channels == 2:
                        samples = array.array('h', data)
                        mono_samples = array.array('h')
                        for i in range(0, len(samples), 2):
                            left = samples[i]
                            right = samples[i + 1]
                            mono = (left + right) // 2
                            mono_samples.append(mono)
                        data = mono_samples.tobytes()

                    if not self.audio_queue.full():
                        self.audio_queue.put(data)
                    else:
                        self.logger.warning("音频队列已满，丢弃数据")
                except Exception as e:
                    self.logger.error(f"Windows音频录制错误: {e}")
                    time.sleep(0.01)
        except Exception as e:
            self.logger.error(f"Windows音频录制器错误: {e}")
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()

    def stop(self):
        if not self.is_running:
            return

        self.is_running = False
        self._recording = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if hasattr(self, '_pyaudio'):
            self._pyaudio.terminate()

        self.logger.info("音频录制器已停止")

    def read(self):
        try:
            return self.audio_queue.get(timeout=0.1)
        except queue.Empty:
            return None


class AudioRouter:
    def __init__(self, device_manager=None, socketio=None):
        self.logger = get_logger()
        self.config = get_database_manager()
        self.device_manager = device_manager
        self.socketio = socketio
        
        audio_config = self.config.get_audio_config()
        self.sample_rate = audio_config.get('sample_rate', 16000)
        self.channels = audio_config.get('channels', 1)
        self.chunk_size = audio_config.get('chunk_size', 1024)
        self.format = pyaudio.paInt16
        self.buffer_size = audio_config.get('buffer_size', 8192)
        
        self.input_device_index = audio_config.get('input_device_index', 0)
        self.output_device_index = audio_config.get('output_device_index', None)
        
        self.active_room: Optional[int] = None
        self.broadcast_mode: bool = False
        self.is_running: bool = False
        
        self.audio_queue: queue.Queue = queue.Queue(maxsize=100)
        self.audio_buffers: Dict[int, deque] = {}
        self.udp_sockets: Dict[int, socket.socket] = {}
        
        self.pyaudio: Optional[pyaudio.PyAudio] = None
        self.audio_stream: Optional[pyaudio.Stream] = None

        # 音频录制器
        self.alsa_recorder: Optional[AudioRecorder] = None
        
        self.rooms_config = self.config.get_rooms_config()
        self.udp_port = self.config.get('network.udp_port', 5000)
        
        self.simulation_mode = self.config.get('system.simulation_mode', False)
        
        # ESP32配置
        self.esp32_sample_rate = 48000
        self.esp32_buffer_len = 512
        self.esp32_packet_size = self.esp32_buffer_len * 2
        self.udp_port = 1234
        
        self._lock = threading.Lock()
        self._capture_thread: Optional[threading.Thread] = None
        self._broadcast_thread: Optional[threading.Thread] = None
        self._capture_running: bool = False
        
        self.room_intercom_enabled: Dict[int, bool] = {}
        self._intercom_thread: Optional[threading.Thread] = None
        self._intercom_stream: Optional[pyaudio.Stream] = None
        self._intercom_queue: queue.Queue = queue.Queue(maxsize=100)
        
        # 用于跟踪被AI语音播放临时挂起的对讲
        self.suspended_intercom_rooms: Dict[int, bool] = {}

    def initialize(self):
        try:
            self.pyaudio = pyaudio.PyAudio()
            self.logger.info("PyAudio初始化成功")
            
            for room in self.rooms_config:
                room_id = room['id']
                self.audio_buffers[room_id] = deque(maxlen=self.buffer_size // self.chunk_size)
                
            self.logger.info(f"音频路由引擎初始化完成，支持{len(self.rooms_config)}个房间")
            return True
            
        except Exception as e:
            self.logger.error(f"音频路由引擎初始化失败: {e}")
            return False

    def start(self):
        if self.is_running:
            self.logger.warning("音频路由引擎已在运行")
            return

        self.is_running = True

        if not self.simulation_mode:
            # 使用音频录制器
            self.alsa_recorder = AudioRecorder(
                device=None,
                sample_rate=self.sample_rate,
                channels=2,
                chunk_size=self.chunk_size
            )
            self.alsa_recorder.start()

            self._capture_thread = threading.Thread(target=self._capture_audio, daemon=True)
            self._capture_thread.start()

            self._broadcast_thread = threading.Thread(target=self._broadcast_audio, daemon=True)
            self._broadcast_thread.start()
        else:
            self.logger.info("模拟模式：音频采集和广播已禁用")

        self.logger.info("音频路由引擎已启动")

    def stop(self):
        self.is_running = False
        
        if self.alsa_recorder:
            self.alsa_recorder.stop()
        
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        if self._broadcast_thread:
            self._broadcast_thread.join(timeout=2)
            
        self._cleanup()
        self.logger.info("音频路由引擎已停止")

    def _capture_audio(self):
        try:
            self.logger.info("音频采集已启动，使用PyAudio录制器")
            self._capture_running = True
            
            while self.is_running and self._capture_running:
                try:
                    data = self.alsa_recorder.read()
                    
                    if data is not None:
                        if not self.audio_queue.full():
                            self.audio_queue.put(data)
                        else:
                            self.logger.warning("音频队列已满，丢弃数据")
                        
                except Exception as e:
                    self.logger.error(f"音频采集错误: {e}")
                    time.sleep(0.01)
            
            self._capture_running = False
            self.logger.info("音频采集已停止")
                
        except Exception as e:
            self.logger.error(f"音频采集线程错误: {e}")

    def _broadcast_audio(self):
        while self.is_running:
            try:
                if not self.audio_queue.empty():
                    data = self.audio_queue.get(timeout=0.1)
                    
                    if self.broadcast_mode:
                        self._send_to_all_rooms(data)
                    elif self.active_room is not None:
                        self._send_to_room(self.active_room, data)
                        
                time.sleep(0.001)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"音频广播错误: {e}")

    def _send_to_room(self, room_id: int, data: bytes, apply_volume: bool = True):
        try:
            with self._lock:
                if room_id not in self.udp_sockets:
                    room = next((r for r in self.rooms_config if r['id'] == room_id), None)
                    if room:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.settimeout(1.0)
                        self.udp_sockets[room_id] = sock
                        self.logger.info(f"为房间{room_id}创建UDP socket，目标IP: {room['ip']}:{self.udp_port}")
                    else:
                        self.logger.warning(f"房间{room_id}配置不存在")
                        return
                
                sock = self.udp_sockets[room_id]
                room = next((r for r in self.rooms_config if r['id'] == room_id), None)
                
                if room:
                    # 应用房间对讲音量（仅在需要时）
                    if apply_volume and self.device_manager and room_id in self.device_manager.rooms:
                        volume = self.device_manager.rooms[room_id].intercom_volume
                        gain = volume / 100.0
                        
                        if volume != 100:
                            samples = array.array('h', data)
                            for i in range(len(samples)):
                                # 应用音量增益，四舍五入并防止溢出
                                adjusted = int(round(samples[i] * gain))
                                samples[i] = max(-32768, min(32767, adjusted))
                            data = samples.tobytes()
                            self.logger.debug(f"房间{room_id}对讲音量: {volume}%, 增益: {gain:.2f}")
                    
                    sent_bytes = sock.sendto(data, (room['ip'], self.udp_port))
                    self.logger.debug(f"发送到房间{room_id} ({room['ip']}:{self.udp_port}): {sent_bytes} 字节")
                    if sent_bytes != len(data):
                        self.logger.warning(f"发送不完整: {sent_bytes}/{len(data)} 字节")
                    
        except Exception as e:
            self.logger.error(f"发送音频到房间{room_id}失败: {e}")
    
    def send_control_command(self, room_id: int, command: dict):
        """发送控制命令到 ESP32-S3"""
        try:
            import json
            json_str = json.dumps(command)
            self._send_to_room(room_id, json_str.encode('utf-8'), apply_volume=False)
            self.logger.debug(f"发送控制命令到房间{room_id}: {command}")
        except Exception as e:
            self.logger.error(f"发送控制命令失败: {e}")

    def _send_to_all_rooms(self, data: bytes):
        for room in self.rooms_config:
            self._send_to_room(room['id'], data)

    def switch_to_room(self, room_id: int) -> bool:
        try:
            with self._lock:
                if room_id not in [r['id'] for r in self.rooms_config]:
                    self.logger.error(f"房间{room_id}不存在")
                    return False
                
                self.active_room = room_id
                self.broadcast_mode = False
                
                self.logger.info(f"切换到房间{room_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"切换房间失败: {e}")
            return False

    def enable_broadcast(self) -> bool:
        try:
            with self._lock:
                self.broadcast_mode = True
                self.active_room = None
                self.logger.info("启用广播模式")
                return True
                
        except Exception as e:
            self.logger.error(f"启用广播模式失败: {e}")
            return False

    def disable_broadcast(self) -> bool:
        try:
            with self._lock:
                self.broadcast_mode = False
                self.logger.info("禁用广播模式")
                return True
                
        except Exception as e:
            self.logger.error(f"禁用广播模式失败: {e}")
            return False

    def get_active_room(self) -> Optional[int]:
        return self.active_room

    def is_broadcasting(self) -> bool:
        return self.broadcast_mode

    def get_room_buffer_status(self, room_id: int) -> Dict:
        if room_id in self.audio_buffers:
            return {
                'room_id': room_id,
                'buffer_size': len(self.audio_buffers[room_id]),
                'max_size': self.audio_buffers[room_id].maxlen
            }
        return {}

    def get_all_intercom_status(self) -> Dict[int, bool]:
        with self._lock:
            return dict(self.room_intercom_enabled)

    def toggle_room_intercom(self, room_id: int, enabled: bool) -> bool:
        try:
            print(f"【对讲切换】收到请求：房间{room_id}, 启用={enabled}")
            with self._lock:
                if room_id not in [r['id'] for r in self.rooms_config]:
                    self.logger.error(f"房间{room_id}不存在")
                    print(f"【对讲切换】错误：房间{room_id}不存在")
                    return False
                
                if enabled:
                    # 开启对讲：先关闭所有其他房间的对讲
                    for other_room_id in list(self.room_intercom_enabled.keys()):
                        if other_room_id != room_id and self.room_intercom_enabled.get(other_room_id, False):
                            self.logger.info(f"关闭房间{other_room_id}的对讲（互斥）")
                            self.room_intercom_enabled[other_room_id] = False
                            # 同步到 device_manager
                            if self.device_manager:
                                self.device_manager.set_room_intercom_enabled(other_room_id, False)
                    
                    # 更新当前对讲房间ID
                    self.config.set_system_db_config('current_intercom_room_id', room_id)
                    # 发送WebSocket事件通知前端
                    if self.socketio:
                        self.socketio.emit('current_intercom_room_update', {'room_id': room_id})
                
                self.room_intercom_enabled[room_id] = enabled
                
                if enabled:
                    print(f"【对讲切换】准备启动房间{room_id}的对讲")
                    self._start_intercom(room_id)
                else:
                    print(f"【对讲切换】准备停止房间{room_id}的对讲")
                    self._stop_intercom(room_id)
                    # 如果关闭的是当前对讲房间，清除记录
                    current_id = self.config.get_current_intercom_room_id()
                    if current_id == room_id:
                        self.config.set_system_db_config('current_intercom_room_id', 0)
                        # 发送WebSocket事件通知前端
                        if self.socketio:
                            self.socketio.emit('current_intercom_room_update', {'room_id': 0})
                
                self.logger.info(f"房间{room_id}对话状态: {enabled}")
                print(f"【对讲切换】房间{room_id}对话状态已切换: {enabled}")
                
                # 同步到 device_manager
                if self.device_manager:
                    self.device_manager.set_room_intercom_enabled(room_id, enabled)
                
                return True
                
        except Exception as e:
            self.logger.error(f"切换房间对讲失败: {e}")
            print(f"【对讲切换错误】切换房间对讲失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def suspend_intercom(self, room_id: int) -> bool:
        """临时挂起房间对讲，用于AI语音播放时"""
        try:
            with self._lock:
                if self.room_intercom_enabled.get(room_id, False):
                    self.logger.info(f"临时挂起房间{room_id}的对讲")
                    self.suspended_intercom_rooms[room_id] = True
                    # 临时关闭对讲
                    self.room_intercom_enabled[room_id] = False
                    self._stop_intercom(room_id)
                    return True
                return False
        except Exception as e:
            self.logger.error(f"挂起房间对讲失败: {e}")
            return False

    def resume_intercom(self, room_id: int) -> bool:
        """恢复被临时挂起的房间对讲"""
        try:
            with self._lock:
                if self.suspended_intercom_rooms.get(room_id, False):
                    self.logger.info(f"恢复房间{room_id}的对讲")
                    self.suspended_intercom_rooms[room_id] = False
                    # 重新开启对讲
                    self.room_intercom_enabled[room_id] = True
                    self._start_intercom(room_id)
                    return True
                return False
        except Exception as e:
            self.logger.error(f"恢复房间对讲失败: {e}")
            return False

    def _start_intercom(self, room_id: int):
        try:
            print(f"【对讲启动】准备启动房间{room_id}的对讲")
            if self._intercom_thread is None or not self._intercom_thread.is_alive():
                if self._capture_running:
                    self._capture_running = False
                    if self._capture_thread:
                        self._capture_thread.join(timeout=2)
                    self.logger.info("已停止音频采集线程，为房间对讲腾出设备")
                
                self._intercom_thread = threading.Thread(target=self._intercom_loop, daemon=True)
                self._intercom_thread.start()
                print(f"【对讲启动】房间对讲线程已启动")
                self.logger.info(f"房间对讲线程已启动")
        except Exception as e:
            print(f"【对讲启动错误】启动房间对讲线程失败: {e}")
            self.logger.error(f"启动房间对讲线程失败: {e}")

    def _stop_intercom(self, room_id: int):
        try:
            if not any(self.room_intercom_enabled.values()):
                if self._intercom_stream:
                    try:
                        if self._intercom_stream.is_active():
                            self._intercom_stream.stop_stream()
                        self._intercom_stream.close()
                    except Exception as e:
                        self.logger.warning(f"关闭音频流时出错: {e}")
                    finally:
                        self._intercom_stream = None
                self.logger.info(f"房间对讲已停止")
                
                if not self.simulation_mode and self.is_running and not self._capture_running:
                    self._capture_thread = threading.Thread(target=self._capture_audio, daemon=True)
                    self._capture_thread.start()
                    self.logger.info("已重新启动音频采集线程")
        except Exception as e:
            self.logger.error(f"停止房间对讲失败: {e}")

    def _intercom_loop(self):
        """房间对讲音频循环 - 完全按照 test_audio_direct.py 的方式，直接用PyAudio"""
        import pyaudio
        stream = None
        p = None
        try:
            # 创建PyAudio实例
            p = pyaudio.PyAudio()
            
            # 打开音频流
            stream = p.open(
                format=pyaudio.paInt16,
                channels=2,
                rate=self.esp32_sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            # 音频缓冲区 - 优化为更高采样率
            audio_buffer = b''
            target_buffer_size = 1024  # 发送稍大的包，减少网络开销（512样本×2字节）
            packets_sent = 0
            audio_blocks_read = 0
            start_time = time.time()
            level_update_counter = 0
            
            while self.is_running and any(self.room_intercom_enabled.values()):
                try:
                    # 检查流是否还活跃
                    if stream is None or not stream.is_active():
                        break
                    
                    # 直接从PyAudio读取（立体声）
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    if not data:
                        time.sleep(0.001)
                        continue
                    
                    # 将立体声混音为单声道（取左右声道平均值）- 使用更高效且安全的方法
                    samples = array.array('h', data)
                    # 使用切片快速获取左右声道
                    left_channel = samples[0::2]
                    right_channel = samples[1::2]
                    # 使用列表推导式快速混音，防止溢出
                    mono_samples = array.array('h', [
                        max(-32768, min(32767, (int(l) + int(r)) // 2)) 
                        for l, r in zip(left_channel, right_channel)
                    ])
                    data = mono_samples.tobytes()
                    
                    # 减少音量计算频率（每20次更新一次）
                    level_update_counter += 1
                    if level_update_counter >= 20 and self.socketio:
                        level_update_counter = 0
                        # 计算音频音量并发送到前端显示
                        rms = 0
                        # 只使用部分样本计算以提升性能
                        for i in range(0, min(len(mono_samples), 200), 2):
                            sample = mono_samples[i]
                            rms += sample * sample
                        rms = int(math.sqrt(rms / min(100, len(mono_samples))))
                        level = int((rms / 32767) * 100)
                        for room_id in self.room_intercom_enabled:
                            if self.room_intercom_enabled[room_id]:
                                self.socketio.emit('audio_level_update', {
                                    'room_id': room_id,
                                    'level': level
                                })
                    
                    audio_blocks_read += 1
                    audio_buffer += data
                    
                    # 当缓冲区达到目标大小时发送 - 完全按照 test_audio_direct.py
                    while len(audio_buffer) >= target_buffer_size:
                        send_data = audio_buffer[:target_buffer_size]
                        audio_buffer = audio_buffer[target_buffer_size:]
                        
                        # 发送到所有启用的房间（不打印详细信息以提高效率）
                        for room_id, enabled in self.room_intercom_enabled.items():
                            if enabled:
                                self._send_to_room(room_id, send_data)
                        
                        packets_sent += 1
                        
                except OSError as e:
                    # 处理PyAudio特定错误
                    if e.errno in [-9999, -9988]:
                        # 主机错误或流已关闭，优雅退出
                        self.logger.info(f"音频流状态变化，退出对讲循环: {e}")
                        break
                    else:
                        self.logger.warning(f"对讲音频读取错误: {e}")
                        time.sleep(0.01)
                except Exception as e:
                    self.logger.warning(f"对讲音频处理错误: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(0.01)
                    
        except Exception as e:
            self.logger.error(f"房间对讲循环错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                if stream is not None:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
                if p is not None:
                    p.terminate()
            except Exception as e:
                self.logger.warning(f"关闭音频流时出错: {e}")


    def _broadcast_intercom_audio(self):
        try:
            if self._intercom_queue.empty():
                return
                
            data = self._intercom_queue.get(timeout=0.01)
            
            sent_count = 0
            for room_id, enabled in self.room_intercom_enabled.items():
                if enabled:
                    self._send_to_room(room_id, data)
                    sent_count += 1
            
            if sent_count > 0:
                self.logger.info(f"房间对讲音频已发送到{sent_count}个房间")
                    
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.error(f"广播房间对讲音频失败: {e}")

    def is_intercom_enabled(self, room_id: int) -> bool:
        return self.room_intercom_enabled.get(room_id, False)

    def _cleanup(self):
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            
        if self._intercom_stream:
            self._intercom_stream.stop_stream()
            self._intercom_stream.close()
            self._intercom_stream = None
            
        for sock in self.udp_sockets.values():
            try:
                sock.close()
            except:
                pass
        self.udp_sockets.clear()
        
        if self.pyaudio:
            self.pyaudio.terminate()

    def __del__(self):
        self._cleanup()


class AIVoicePlayer:
    """AI语音播放器 - 播放AI生成的语音到对应的房间"""

    STATUS_PENDING = 0
    STATUS_TEXT_GENERATED = 1
    STATUS_VOICE_GENERATED = 2
    STATUS_PLAYING = 3
    STATUS_COMPLETED = 9

    def __init__(self, audio_router, device_manager, socketio=None):
        self.logger = get_logger()
        self.audio_router = audio_router
        self.device_manager = device_manager
        self.config = get_database_manager()
        self.socketio = socketio

        self.running = False
        self.thread = None

        self.db_config = {
            'host': 'YOUR_MYSQL_HOST',
            'port': 3306,
            'database': 'YOUR_MYSQL_DB',
            'user': 'YOUR_MYSQL_USER',
            'password': 'YOUR_MYSQL_PASSWORD'
        }
        self.db_connection = None

        self.esp32_sample_rate = 48000
        self.esp32_packet_size = 1024

        self.room_play_locks: Dict[int, threading.Lock] = {}
        self._init_room_locks()

        # 确定项目根目录，用于解析相对路径
        if getattr(sys, 'frozen', False):
            # 打包后的exe模式
            self.base_dir = os.path.dirname(sys.executable)
        else:
            # 开发模式：当前文件位于 iot/core/audio.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.base_dir = os.path.dirname(os.path.dirname(current_dir))
        
    def _init_room_locks(self):
        rooms = self.device_manager.get_all_rooms()
        for room in rooms:
            self.room_play_locks[room['id']] = threading.Lock()
    
    def _get_db_connection(self):
        if self.db_connection is not None:
            try:
                self.db_connection.ping(reconnect=True)
                return self.db_connection
            except Exception:
                try:
                    self.db_connection.close()
                except:
                    pass
                self.db_connection = None

        try:
            self.db_connection = pymysql.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True
            )
            return self.db_connection
        except Exception as e:
            self.logger.error(f"连接数据库失败: {e}")
            self.db_connection = None
            return None
    
    def _close_db_connection(self):
        if self.db_connection:
            try:
                self.db_connection.close()
            except:
                pass
            self.db_connection = None

    def _get_absolute_wav_path(self, wav_path: str) -> str:
        """将wav路径转换为绝对路径

        如果wav_path是相对路径，则基于base_dir转换为绝对路径
        如果已经是绝对路径，则直接返回
        """
        if not wav_path:
            return wav_path

        # 如果已经是绝对路径，直接返回
        if os.path.isabs(wav_path):
            return wav_path

        # 将正斜杠转换回系统路径分隔符
        wav_path = wav_path.replace('/', os.sep)

        # 基于base_dir构建绝对路径
        return os.path.join(self.base_dir, wav_path)
    
    STREAM_END_MARKER = b'__STREAM_END__'
    
    def _parse_wav_header(self, data: bytes):
        if len(data) < 12:
            return None
        
        if data[0:4] != b'RIFF' or data[8:12] != b'WAVE':
            return None
        
        offset = 12
        fmt_chunk_found = False
        data_chunk_found = False
        num_channels = 1 
        sample_rate = 48000
        bits_per_sample = 16
        data_offset = 0
        
        while offset < len(data) - 8:
            chunk_id = data[offset:offset+4]
            chunk_size = int.from_bytes(data[offset+4:offset+8], 'little')
            
            if chunk_id == b'fmt ':
                if chunk_size >= 16:
                    num_channels = int.from_bytes(data[offset+10:offset+12], 'little')
                    sample_rate = int.from_bytes(data[offset+12:offset+16], 'little')
                    bits_per_sample = int.from_bytes(data[offset+22:offset+24], 'little')
                    fmt_chunk_found = True
                offset += 8 + chunk_size
            elif chunk_id == b'data':
                data_offset = offset + 8
                data_chunk_found = True
                break
            else:
                offset += 8 + chunk_size
        
        if fmt_chunk_found and data_chunk_found:
            return {
                'num_channels': num_channels,
                'sample_rate': sample_rate,
                'bits_per_sample': bits_per_sample,
                'data_offset': data_offset
            }
        return None
    
    def _high_precision_sleep(self, duration: float):
        """高精度睡眠函数 - 使用混合方式减少CPU占用"""
        if duration <= 0:
            return
        end_time = time.perf_counter() + duration
        # 先睡大部分时间（留出1ms的余量用忙等待保证精度）
        sleep_time = duration - 0.001
        if sleep_time > 0:
            time.sleep(sleep_time)
        # 最后一小段时间用忙等待保证精度
        while time.perf_counter() < end_time:
            pass
    
    def play_streamed_voice(self, room_id: int, data_queue, wav_path: str = None) -> bool:
        print(f"[DEBUG] play_streamed_voice 开始执行，room_id={room_id}")
        
        # 记录对讲是否被挂起
        intercom_suspended = False
        
        try:
            self.logger.info(f"play_streamed_voice 开始执行，room_id={room_id}")
            
            room = self.device_manager.rooms.get(room_id)
            if not room:
                self.logger.warning(f"房间{room_id}不存在")
                return False
            
            # 发送AI语音正在播放的事件
            if self.socketio:
                self.socketio.emit('ai_voice_playing', {'room_id': room_id, 'playing': True})
            
            # 临时挂起房间对讲（如果开启）
            intercom_suspended = self.audio_router.suspend_intercom(room_id)
            if intercom_suspended:
                self.logger.info(f"已临时挂起房间{room_id}的对讲")
            
            self.logger.info(f"找到房间，直接播放原始WAV流，使用精确时序控制")
            
            audio_buffer = b''
            wav_header_parsed = False
            total_bytes_sent = 0
            stream_ended = False
            wav_info = None
            chunk_count = 0
            
            target_buffer_size = 1024
            samples_per_packet = target_buffer_size // 2
            packet_duration = samples_per_packet / self.esp32_sample_rate
            
            self.logger.info("开始等待音频数据...")
            
            start_time = None
            next_send_time = None
            sent_chunk_count = 0
            
            while not stream_ended:
                try:
                    chunk = data_queue.get(timeout=120)
                    chunk_count += 1
                    self.logger.info(f"收到第 {chunk_count} 个数据块，大小: {len(chunk)} 字节")
                except:
                    self.logger.warning("等待音频数据超时")
                    break
                
                if chunk == self.STREAM_END_MARKER:
                    self.logger.info("收到流结束标记")
                    stream_ended = True
                    break
                
                audio_buffer += chunk
                
                if not wav_header_parsed and len(audio_buffer) >= 44:
                    wav_info = self._parse_wav_header(audio_buffer)
                    if wav_info:
                        self.logger.info(f"WAV头解析: 采样率={wav_info['sample_rate']}Hz, 声道={wav_info['num_channels']}, 位深={wav_info['bits_per_sample']}bit, 数据偏移={wav_info['data_offset']}")
                        audio_buffer = audio_buffer[wav_info['data_offset']:]
                        wav_header_parsed = True
                    else:
                        self.logger.warning("WAV头解析失败，跳过44字节")
                        audio_buffer = audio_buffer[44:]
                        wav_header_parsed = True
                
                while len(audio_buffer) >= target_buffer_size:
                    if start_time is None:
                        start_time = time.perf_counter()
                        next_send_time = start_time
                    
                    packet = audio_buffer[:target_buffer_size]
                    audio_buffer = audio_buffer[target_buffer_size:]
                    
                    current_time = time.perf_counter()
                    if current_time < next_send_time:
                        self._high_precision_sleep(next_send_time - current_time)
                    
                    self.audio_router._send_to_room(room_id, packet)
                    total_bytes_sent += len(packet)
                    sent_chunk_count += 1
                    
                    next_send_time = start_time + (sent_chunk_count * packet_duration)
                    
                    if sent_chunk_count % 50 == 0:
                        elapsed = time.perf_counter() - start_time
                        expected_time = sent_chunk_count * packet_duration
                        drift = (elapsed - expected_time) * 1000
                        self.logger.debug(f"已发送 {sent_chunk_count} 个包, 偏移: {drift:+.2f}ms")
            
            if len(audio_buffer) > 0 and wav_header_parsed:
                if start_time is None:
                    start_time = time.perf_counter()
                    next_send_time = start_time
                
                while len(audio_buffer) < target_buffer_size:
                    audio_buffer += b'\x00' * (target_buffer_size - len(audio_buffer))
                
                packet = audio_buffer[:target_buffer_size]
                
                current_time = time.perf_counter()
                if current_time < next_send_time:
                    self._high_precision_sleep(next_send_time - current_time)
                
                self.audio_router._send_to_room(room_id, packet)
                total_bytes_sent += len(packet)
            
            self.logger.info(f"流式播放完成，共发送 {total_bytes_sent} 字节")
            
            # 发送AI语音播放结束的事件
            if self.socketio:
                self.socketio.emit('ai_voice_playing', {'room_id': room_id, 'playing': False})
            
            # 恢复被挂起的对讲
            if intercom_suspended:
                self.logger.info(f"正在恢复房间{room_id}的对讲")
                self.audio_router.resume_intercom(room_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"流式播放失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # 发送AI语音播放结束的事件
            if self.socketio:
                self.socketio.emit('ai_voice_playing', {'room_id': room_id, 'playing': False})
            
            # 即使失败也要尝试恢复对讲
            if intercom_suspended:
                self.logger.warning(f"播放失败，尝试恢复房间{room_id}的对讲")
                try:
                    self.audio_router.resume_intercom(room_id)
                except Exception as resume_error:
                    self.logger.error(f"恢复对讲失败: {resume_error}")
            
            return False

    def play_wav_file(self, room_id: int, wav_path: str) -> bool:
        intercom_suspended = False

        try:
            self.logger.info(f"play_wav_file 开始执行，room_id={room_id}, wav_path={wav_path}")

            room = self.device_manager.rooms.get(room_id)
            if not room:
                self.logger.warning(f"房间{room_id}不存在")
                return False

            if not os.path.exists(wav_path):
                self.logger.error(f"wav文件不存在: {wav_path}")
                return False

            if self.socketio:
                self.socketio.emit('ai_voice_playing', {'room_id': room_id, 'playing': True})

            intercom_suspended = self.audio_router.suspend_intercom(room_id)
            if intercom_suspended:
                self.logger.info(f"已临时挂起房间{room_id}的对讲")

            with open(wav_path, 'rb') as f:
                audio_data = f.read()

            wav_info = self._parse_wav_header(audio_data)
            if wav_info:
                data_offset = wav_info['data_offset']
                audio_buffer = audio_data[data_offset:]
                self.logger.info(f"WAV头解析: 采样率={wav_info['sample_rate']}Hz, 声道={wav_info['num_channels']}, 位深={wav_info['bits_per_sample']}bit")
            else:
                self.logger.warning("WAV头解析失败，跳过44字节")
                audio_buffer = audio_data[44:]

            target_buffer_size = 1024
            samples_per_packet = target_buffer_size // 2
            packet_duration = samples_per_packet / self.esp32_sample_rate

            start_time = None
            next_send_time = None
            sent_chunk_count = 0
            total_bytes_sent = 0

            while len(audio_buffer) >= target_buffer_size:
                if start_time is None:
                    start_time = time.perf_counter()
                    next_send_time = start_time

                packet = audio_buffer[:target_buffer_size]
                audio_buffer = audio_buffer[target_buffer_size:]

                current_time = time.perf_counter()
                if current_time < next_send_time:
                    self._high_precision_sleep(next_send_time - current_time)

                self.audio_router._send_to_room(room_id, packet)
                total_bytes_sent += len(packet)
                sent_chunk_count += 1

                next_send_time = start_time + (sent_chunk_count * packet_duration)

                if sent_chunk_count % 50 == 0:
                    elapsed = time.perf_counter() - start_time
                    expected_time = sent_chunk_count * packet_duration
                    drift = (elapsed - expected_time) * 1000
                    self.logger.debug(f"已发送 {sent_chunk_count} 个包, 偏移: {drift:+.2f}ms")

            if len(audio_buffer) > 0:
                if start_time is None:
                    start_time = time.perf_counter()
                    next_send_time = start_time

                while len(audio_buffer) < target_buffer_size:
                    audio_buffer += b'\x00' * (target_buffer_size - len(audio_buffer))

                packet = audio_buffer[:target_buffer_size]

                current_time = time.perf_counter()
                if current_time < next_send_time:
                    self._high_precision_sleep(next_send_time - current_time)

                self.audio_router._send_to_room(room_id, packet)
                total_bytes_sent += len(packet)

            self.logger.info(f"WAV文件播放完成，共发送 {total_bytes_sent} 字节")

            if self.socketio:
                self.socketio.emit('ai_voice_playing', {'room_id': room_id, 'playing': False})

            if intercom_suspended:
                self.logger.info(f"正在恢复房间{room_id}的对讲")
                self.audio_router.resume_intercom(room_id)

            return True

        except Exception as e:
            self.logger.error(f"WAV文件播放失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            if self.socketio:
                self.socketio.emit('ai_voice_playing', {'room_id': room_id, 'playing': False})

            if intercom_suspended:
                self.logger.warning(f"播放失败，尝试恢复房间{room_id}的对讲")
                try:
                    self.audio_router.resume_intercom(room_id)
                except Exception as resume_error:
                    self.logger.error(f"恢复对讲失败: {resume_error}")

            return False

    def start(self):
        if self.running:
            self.logger.warning("AI语音播放器已经在运行")
            return
        
        self.logger.info("=" * 60)
        self.logger.info("正在启动 AI语音播放器...")
        self.logger.info("=" * 60)
        
        self.running = True
        self.logger.info("AI语音播放器已启动（流式模式）")
    
    def stop(self):
        if not self.running:
            return
        
        self.running = False
        self._close_db_connection()
        self.logger.info("AI语音播放器已停止")


class TriggerSoundPlayer:
    """触发音效播放器 - 播放设备触发时的音效"""

    def __init__(self, audio_router, device_manager):
        self.logger = get_logger()
        self.audio_router = audio_router
        self.device_manager = device_manager
        self.config = get_database_manager()
        
        self.esp32_sample_rate = 48000
        self.esp32_packet_size = 1024
        
        self._lock = threading.Lock()
        self._playing = False
        self._sound_cache: Dict[Tuple[int, str], bytes] = {}
        
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.base_dir = os.path.dirname(os.path.dirname(current_dir))
        
        self.sound_dir = os.path.join(self.base_dir, 'sound')
    
    def _get_sound_file_path(self, room_id: int, device_name: str) -> Optional[str]:
        """获取音效文件路径，仅支持WAV格式"""
        room_dir = os.path.join(self.sound_dir, str(room_id))
        wav_path = os.path.join(room_dir, f'{device_name}.wav')
        if os.path.exists(wav_path):
            return wav_path
        return None
    
    def sound_file_exists(self, room_id: int, device_name: str) -> bool:
        """检查音效文件是否存在"""
        return self._get_sound_file_path(room_id, device_name) is not None
    
    def get_room_sound_status(self, room_id: int) -> List[Dict]:
        """获取房间内所有设备的音效状态"""
        room = self.device_manager.rooms.get(room_id)
        if not room:
            return []
        
        status_list = []
        for device_name, device in room.devices.items():
            status_list.append({
                'device_id': device.id,
                'device_name': device.name,
                'device_label': device.label,
                'sound_exists': self.sound_file_exists(room_id, device.name),
                'trigger_sound': device.trigger_sound
            })
        return status_list
    
    def _high_precision_sleep(self, duration: float):
        """高精度睡眠函数 - 使用混合方式减少CPU占用"""
        if duration <= 0:
            return
        end_time = time.perf_counter() + duration
        # 先睡大部分时间（留出1ms的余量用忙等待保证精度）
        sleep_time = duration - 0.001
        if sleep_time > 0:
            time.sleep(sleep_time)
        # 最后一小段时间用忙等待保证精度
        while time.perf_counter() < end_time:
            pass
    
    def _parse_wav_file(self, wav_path: str) -> Optional[Dict]:
        """解析WAV文件，返回音频数据"""
        try:
            with wave.open(wav_path, 'rb') as wf:
                num_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                num_frames = wf.getnframes()
                
                self.logger.info(f"WAV文件信息: 声道={num_channels}, 位深={sample_width*8}bit, 采样率={frame_rate}Hz, 帧数={num_frames}")
                
                audio_data = wf.readframes(num_frames)
                
                if num_channels != 1:
                    samples = array.array('h', audio_data)
                    mono_samples = array.array('h')
                    if num_channels == 2:
                        for i in range(0, len(samples), 2):
                            left = samples[i]
                            right = samples[i + 1]
                            mono = (int(left) + int(right)) // 2
                            mono_samples.append(mono)
                    else:
                        for i in range(0, len(samples), num_channels):
                            avg = 0
                            for j in range(num_channels):
                                avg += int(samples[i + j])
                            avg = avg // num_channels
                            mono_samples.append(avg)
                    audio_data = mono_samples.tobytes()
                
                if frame_rate != self.esp32_sample_rate:
                    self.logger.warning(f"WAV采样率({frame_rate}Hz)与ESP32采样率({self.esp32_sample_rate}Hz)不匹配，可能需要重采样")
                
                if sample_width != 2:
                    self.logger.warning(f"WAV位深({sample_width*8}bit)与16bit不匹配")
                
                audio_data = apply_fade_in_out(audio_data, self.esp32_sample_rate)
                audio_data = normalize_volume(audio_data)
                
                return {
                    'data': audio_data,
                    'sample_rate': self.esp32_sample_rate
                }
        except Exception as e:
            self.logger.error(f"解析WAV文件失败: {wav_path}, 错误: {e}", exc_info=True)
            return None
    
    def play_trigger_sound(self, room_id: int, device_name: str):
        """播放触发音效"""
        try:
            room = self.device_manager.rooms.get(room_id)
            if not room:
                return False
            
            device = room.devices.get(device_name)
            if not device:
                return False
            
            if not device.trigger_sound:
                return False
            
            sound_path = self._get_sound_file_path(room_id, device_name)
            if not sound_path:
                return False
            
            with self._lock:
                if self._playing:
                    self.logger.warning("上一个音效尚未播放完成，跳过当前音效")
                    return False
                self._playing = True
            
            try:
                self.logger.info(f"播放触发音效: room={room_id}, device={device_name}, file={sound_path}")
                
                cache_key = (room_id, device_name)
                if cache_key in self._sound_cache:
                    audio_data = self._sound_cache[cache_key]
                else:
                    wav_info = self._parse_wav_file(sound_path)
                    if not wav_info:
                        return False
                    audio_data = wav_info['data']
                    self._sound_cache[cache_key] = audio_data
                
                target_buffer_size = self.esp32_packet_size
                
                audio_buffer = audio_data
                total_bytes_sent = 0
                
                samples_per_packet = target_buffer_size // 2
                packet_duration = samples_per_packet / self.esp32_sample_rate
                
                self.audio_router.send_control_command(room_id, {
                    'type': 'trigger_audio_start',
                    'volume': 1.0
                })
                
                start_time = None
                next_send_time = None
                sent_chunk_count = 0
                
                while len(audio_buffer) > 0:
                    if start_time is None:
                        start_time = time.perf_counter()
                        next_send_time = start_time
                    
                    if len(audio_buffer) >= target_buffer_size:
                        packet = audio_buffer[:target_buffer_size]
                        audio_buffer = audio_buffer[target_buffer_size:]
                    else:
                        packet = audio_buffer
                        while len(packet) < target_buffer_size:
                            packet += b'\x00'
                        audio_buffer = b''
                    
                    current_time = time.perf_counter()
                    if current_time < next_send_time:
                        self._high_precision_sleep(next_send_time - current_time)
                    
                    self.audio_router._send_to_room(room_id, packet, apply_volume=False)
                    total_bytes_sent += len(packet)
                    sent_chunk_count += 1
                    
                    next_send_time = start_time + (sent_chunk_count * packet_duration)
                
                # 发送结束控制命令
                self.audio_router.send_control_command(room_id, {
                    'type': 'trigger_audio_end'
                })
                
                self.logger.info(f"触发音效播放完成，共发送 {total_bytes_sent} 字节")
                return True
                
            finally:
                with self._lock:
                    self._playing = False
            
        except Exception as e:
            self.logger.error(f"播放触发音效失败: room={room_id}, device={device_name}, 错误: {e}", exc_info=True)
            with self._lock:
                self._playing = False
            return False

    def upload_sound_to_esp32(self, room_id: int, device_name: str) -> bool:
        """上传音效文件到ESP32的SPIFFS"""
        try:
            room = self.device_manager.rooms.get(room_id)
            if not room:
                self.logger.error(f"房间{room_id}不存在")
                return False

            sound_path = self._get_sound_file_path(room_id, device_name)
            if not sound_path:
                self.logger.error(f"音效文件不存在: room={room_id}, device={device_name}")
                return False

            import requests
            url = f"http://{room.ip}/sound/upload"

            with open(sound_path, 'rb') as f:
                files = {'file': (f'/sound/{device_name}.wav', f, 'audio/wav')}
                response = requests.post(url, files=files, timeout=30)

            if response.status_code == 200:
                self.logger.info(f"音效上传成功: room={room_id}, device={device_name}")
                return True
            else:
                self.logger.error(f"音效上传失败: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"上传音效到ESP32失败: {e}")
            return False

    def delete_sound_from_esp32(self, room_id: int, device_name: str) -> bool:
        """删除ESP32上的音效文件"""
        try:
            room = self.device_manager.rooms.get(room_id)
            if not room:
                return False

            import requests
            response = requests.post(
                f"http://{room.ip}/sound/delete",
                json={"device": device_name},
                timeout=10
            )

            if response.status_code == 200:
                self.logger.info(f"音效删除成功: room={room_id}, device={device_name}")
                return True
            else:
                self.logger.error(f"音效删除失败: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"删除ESP32音效失败: {e}")
            return False