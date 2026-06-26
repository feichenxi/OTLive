import os
import sys
import logging
import time
import threading
import socket
import wave
from typing import Optional, Dict, Callable
from datetime import datetime
from queue import Queue

logger = logging.getLogger('aiwav')

USE_STREAMING_OUTPUT = True # 是否使用流式输出

ESP32_IP = "192.168.1.101"
ESP32_PORT = 1234
ESP32_SAMPLE_RATE = 48000
ESP32_PACKET_SIZE = 1024


class StreamResultCallback:
    STREAM_END_MARKER = b'__STREAM_END__'
    
    def __init__(self, data_queue: Queue, logger, save_to_file=False, filename=None):
        self.data_queue = data_queue
        self.logger = logger
        self.file = None
        self.completed = False
        self.error = None
        self.completed_event = threading.Event()
        self.save_to_file = save_to_file
        self.filename = filename
        self.temp_file = None
        
        # 如果需要保存到文件，创建临时文件
        if self.save_to_file and self.filename:
            try:
                # 获取项目根目录
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                
                temp_dir = os.path.join(base_dir, 'temp', 'wav')
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, self.filename)
                self.temp_file = open(temp_path, 'wb')
                self.logger.info(f"创建临时音频文件: {temp_path}")
            except Exception as e:
                self.logger.error(f"创建临时音频文件失败: {e}")
    
    def on_open(self):
        self.logger.info("流式语音合成连接建立")
    
    def on_complete(self):
        self.logger.info("流式语音合成完成")
        self.completed = True
        self.completed_event.set()
        self.data_queue.put(self.STREAM_END_MARKER)
        if self.file:
            self.file.close()
        if self.temp_file:
            self.temp_file.close()
            self.logger.info(f"临时音频文件已保存: {self.filename}")
    
    def on_error(self, message: str):
        self.logger.error(f"流式语音合成异常: {message}")
        self.error = message
        self.completed = True
        self.completed_event.set()
        self.data_queue.put(self.STREAM_END_MARKER)
        if self.temp_file:
            self.temp_file.close()
    
    def on_close(self):
        self.logger.info("流式语音合成连接关闭")
        if self.file:
            self.file.close()
        if self.temp_file:
            self.temp_file.close()
    
    def on_event(self, message):
        pass
    
    def on_data(self, data: bytes) -> None:
        self.data_queue.put(data)
        # 同时写入临时文件
        if self.temp_file:
            try:
                self.temp_file.write(data)
            except Exception as e:
                self.logger.error(f"写入临时音频文件失败: {e}")
    
    def wait_for_complete(self, timeout=None):
        return self.completed_event.wait(timeout)


class GiftVoiceGenerator:
    def __init__(self, config: Dict):
        self.enabled = config.get('enabled', False)
        self.provider = config.get('provider', '')
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', '')

        self.logger = logger

        if self.enabled and self.provider == 'cosyvoice':
            self._init_dashscope()
    
    def _init_dashscope(self):
        try:
            import dashscope
            if self.api_key:
                dashscope.api_key = self.api_key
            dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'
        except ImportError:
            self.logger.error("DashScope SDK 未安装，请运行: pip install dashscope")
        except Exception as e:
            self.logger.error(f"DashScope SDK 初始化失败: {e}")

    def generate_voice_file(self, text: str, output_path: str, voice_id: str = None) -> bool:
        if not self.enabled:
            self.logger.warning("语音生成功能未启用")
            return False

        if not text or not text.strip():
            self.logger.warning("文本内容为空，无法生成语音")
            return False

        try:
            return self._generate_cosyvoice_to_file(text, output_path, voice_id)
        except Exception as e:
            self.logger.error(f"语音文件生成失败: {e}")
            return False

    def _generate_cosyvoice_to_file(self, text: str, output_path: str, voice_id: str = None) -> bool:
        start_time = time.time()

        try:
            import dashscope
            from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
        except ImportError:
            self.logger.error("DashScope SDK 未安装，请运行: pip install dashscope")
            return False

        if not self.api_key:
            self.logger.error("阿里云百炼 API Key 未配置")
            return False

        use_voice = voice_id
        use_model = self.model

        if use_voice:
            use_model = 'cosyvoice-v3.5-flash'
        else:
            use_voice = 'longanyang'
            use_model = 'cosyvoice-v3-flash'

        self.logger.info(f"语音文件生成 - model: {use_model}, voice_id: {use_voice}")

        try:
            audio_format = AudioFormat.WAV_48000HZ_MONO_16BIT

            synthesizer = SpeechSynthesizer(
                model=use_model,
                voice=use_voice,
                format=audio_format
            )

            audio_data = synthesizer.call(text)

            if not audio_data:
                self.logger.error("语音合成返回空数据")
                return False

            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            with open(output_path, 'wb') as f:
                f.write(audio_data)

            elapsed_time = time.time() - start_time
            self.logger.info(f"语音文件生成完成，保存到: {output_path}，耗时: {elapsed_time:.2f}秒")
            return True

        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error(f"语音文件生成失败，voice_id: {use_voice}, 错误: {e}, 耗时: {elapsed_time:.2f}秒")
            return False

    def generate_voice_stream(self, text: str, data_queue: Queue, voice_id: str = None) -> bool:
        if not self.enabled:
            self.logger.warning("语音生成功能未启用")
            return False
        
        if not text or not text.strip():
            self.logger.warning("文本内容为空，无法生成语音")
            return False
        
        try:
            if USE_STREAMING_OUTPUT:
                if self.provider == 'cosyvoice':
                    return self._generate_cosyvoice_stream(text, data_queue, voice_id)
                else:
                    self.logger.warning(f"不支持的语音提供商: {self.provider}")
                    return False
            else:
                return self.generate_voice_non_streaming(text, voice_id)
                
        except Exception as e:
            self.logger.error(f"语音生成失败: {e}")
            return False
    
    def _generate_cosyvoice_stream(self, text: str, data_queue: Queue, voice_id: str = None) -> bool:
        start_time = time.time()
        
        try:
            import dashscope
            from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat, ResultCallback
        except ImportError:
            self.logger.error("DashScope SDK 未安装，请运行: pip install dashscope")
            return False
        
        if not self.api_key:
            self.logger.error("阿里云百炼 API Key 未配置")
            return False
        
        use_voice = voice_id
        use_model = self.model
        
        if use_voice:
            use_model = 'cosyvoice-v3.5-flash'
            self.logger.info(f"使用自定义音色，切换到模型: {use_model}")
        else:
            use_voice = 'longanyang'
            use_model = 'cosyvoice-v3-flash'
            self.logger.info(f"使用系统音色，切换到模型: {use_model}")
        
        self.logger.info(f"流式语音生成 - 使用model: {use_model}, voice_id: {use_voice}")
        
        try:
            audio_format = AudioFormat.WAV_48000HZ_MONO_16BIT
            
            self.logger.info(f"使用音频格式: {audio_format}")
            
            temp_filename = f"temp_audio_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.wav"
            callback = StreamResultCallback(data_queue, self.logger, save_to_file=True, filename=temp_filename)
            
            synthesizer = SpeechSynthesizer(
                model=use_model,
                voice=use_voice,
                format=audio_format,
                callback=callback
            )
            
            synthesizer.call(text)
            
            if not callback.wait_for_complete(timeout=120):
                self.logger.error("流式语音合成超时")
                return False
            
            elapsed_time = time.time() - start_time
            
            if callback.error:
                self.logger.error(f"流式语音合成返回错误: {callback.error}")
                return False
            
            self.logger.info(f"流式语音生成完成，耗时: {elapsed_time:.2f}秒")
            return True
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error(f"阿里云百炼 CosyVoice 流式API 请求失败，voice_id: {use_voice}, 错误: {e}", exc_info=True)
            print(f"[AI流式语音生成] 输入: {text} | 失败: {e} | 耗时: {elapsed_time:.2f}秒")
            return False
    
    def is_enabled(self):
        if self.provider == 'cosyvoice':
            return self.enabled and bool(self.api_key)
        else:
            return self.enabled and bool(self.api_key)
    
    def _create_udp_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        return sock
    
    def _high_precision_sleep(self, duration: float):
        end_time = time.perf_counter() + duration
        while time.perf_counter() < end_time:
            pass
    
    def _send_wav_to_esp32(self, wav_path: str):
        try:
            with wave.open(wav_path, 'rb') as wf:
                info = {
                    'channels': wf.getnchannels(),
                    'sample_width': wf.getsampwidth(),
                    'framerate': wf.getframerate(),
                    'nframes': wf.getnframes(),
                    'duration': wf.getnframes() / wf.getframerate()
                }
                
                audio_data = wf.readframes(wf.getnframes())
                
                sock = self._create_udp_socket()
                self.logger.info(f"发送WAV到ESP32: {ESP32_IP}:{ESP32_PORT}")
                
                target_buffer_size = ESP32_PACKET_SIZE
                total_bytes_sent = 0
                chunk_count = 0
                
                audio_buffer = audio_data
                
                samples_per_packet = target_buffer_size // 2
                packet_duration = samples_per_packet / ESP32_SAMPLE_RATE
                
                start_time = time.perf_counter()
                next_send_time = start_time
                
                while len(audio_buffer) >= target_buffer_size:
                    packet = audio_buffer[:target_buffer_size]
                    audio_buffer = audio_buffer[target_buffer_size:]
                    
                    current_time = time.perf_counter()
                    if current_time < next_send_time:
                        self._high_precision_sleep(next_send_time - current_time)
                    
                    sock.sendto(packet, (ESP32_IP, ESP32_PORT))
                    total_bytes_sent += len(packet)
                    chunk_count += 1
                    
                    next_send_time = start_time + (chunk_count * packet_duration)
                    
                    if chunk_count % 50 == 0:
                        elapsed = time.perf_counter() - start_time
                        expected_time = chunk_count * packet_duration
                        drift = (elapsed - expected_time) * 1000
                        self.logger.debug(f"已发送 {chunk_count} 个包, 偏移: {drift:+.2f}ms")
                
                if len(audio_buffer) > 0:
                    padding = b'\x00' * (target_buffer_size - len(audio_buffer))
                    packet = audio_buffer + padding
                    sock.sendto(packet, (ESP32_IP, ESP32_PORT))
                    total_bytes_sent += len(packet)
                
                elapsed = time.perf_counter() - start_time
                sock.close()
                self.logger.info(f"WAV发送完成 - 总字节: {total_bytes_sent}, 实际耗时: {elapsed:.3f}s")
                return True
                
        except Exception as e:
            self.logger.error(f"发送WAV到ESP32失败: {e}", exc_info=True)
            return False
    
    def generate_voice_non_streaming(self, text: str, voice_id: str = None) -> bool:
        if not self.enabled:
            self.logger.warning("语音生成功能未启用")
            return False
        
        if not text or not text.strip():
            self.logger.warning("文本内容为空，无法生成语音")
            return False
        
        try:
            if self.provider == 'cosyvoice':
                return self._generate_cosyvoice_non_streaming(text, voice_id)
            else:
                self.logger.warning(f"不支持的语音提供商: {self.provider}")
                return False
                
        except Exception as e:
            self.logger.error(f"非流式语音生成失败: {e}")
            return False
    
    def _generate_cosyvoice_non_streaming(self, text: str, voice_id: str = None) -> bool:
        start_time = time.time()
        
        try:
            import dashscope
            from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
        except ImportError:
            self.logger.error("DashScope SDK 未安装，请运行: pip install dashscope")
            return False
        
        if not self.api_key:
            self.logger.error("阿里云百炼 API Key 未配置")
            return False
        
        use_voice = voice_id
        use_model = self.model
        
        if use_voice:
            use_model = 'cosyvoice-v3.5-flash'
            self.logger.info(f"使用自定义音色，切换到模型: {use_model}")
        else:
            use_voice = 'longanyang'
            use_model = 'cosyvoice-v3-flash'
            self.logger.info(f"使用系统音色，切换到模型: {use_model}")
        
        self.logger.info(f"非流式语音生成 - 使用model: {use_model}, voice_id: {use_voice}")
        
        try:
            audio_format = AudioFormat.WAV_48000HZ_MONO_16BIT
            
            self.logger.info(f"使用音频格式: {audio_format}")
            
            synthesizer = SpeechSynthesizer(
                model=use_model,
                voice=use_voice,
                format=audio_format
            )
            
            audio_data = synthesizer.call(text)
            
            temp_filename = f"temp_audio_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.wav"
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            temp_dir = os.path.join(base_dir, 'temp', 'wav')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, temp_filename)
            
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            self.logger.info(f"非流式语音生成完成，保存到: {temp_path}")
            
            self._send_wav_to_esp32(temp_path)
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"非流式语音生成+发送完成，总耗时: {elapsed_time:.2f}秒")
            return True
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error(f"阿里云百炼 CosyVoice 非流式API 请求失败，voice_id: {use_voice}, 错误: {e}", exc_info=True)
            print(f"[AI非流式语音生成] 输入: {text} | 失败: {e} | 耗时: {elapsed_time:.2f}秒")
            return False
