import socket
import json
import time
import threading
import asyncio
import configparser
import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime
from common.logger import get_logger
from common.database_manager import get_database_manager


@dataclass
class Device:
    id: int
    name: str
    label: str
    pin: int
    trigger_on_duration: float = 0.3
    trigger_off_duration: float = 0.3
    state: bool = False
    enabled: bool = False
    gift_event: str = ''
    trigger_sound: bool = False
    trigger_sound_delay: float = 0
    loop_action: str = 'manual'
    loop_minute: str = ''
    loop_duration: float = 0.0


@dataclass
class Room:
    id: int
    name: str
    ip: str
    port: int
    devices: Dict[str, Device]
    audio_active: bool = False
    mic_enabled: bool = False
    online: bool = False
    last_seen: Optional[float] = None
    rssi: int = -100
    sort_order: int = 0
    intercom_volume: int = 50
    background_music_url: str = ''
    background_music_name: str = ''
    background_music_size: int = 0
    live_url: str = ''
    voice_status: bool = False
    enabled: bool = True
    rssi_history: list = field(default_factory=list)
    online_since: Optional[float] = None
    version: str = ''


class DeviceManager:
    def __init__(self):
        self.logger = get_logger()
        self.config = get_database_manager()
        
        self.rooms: Dict[int, Room] = {}
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []
        self._socketio = None
        
        self.tcp_port = self.config.get('network.tcp_port', 8080)
        self.response_timeout = self.config.get('performance.device_response_timeout', 1.0)
        self.heartbeat_interval = self.config.get('performance.heartbeat_interval', 30)
        self.heartbeat_port = self.config.get('performance.heartbeat_port', 9999)
        self.heartbeat_timeout = self.config.get('performance.heartbeat_timeout', 25)
        self.enable_monitoring = self.config.get('performance.enable_room_monitoring', True)
        self.simulation_mode = self.config.get('system.simulation_mode', False)
        
        self._init_rooms()
        self._load_all_rooms_voice_status()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._offline_check_thread: Optional[threading.Thread] = None
        self._heartbeat_socket: Optional[socket.socket] = None
        self.is_running: bool = False
        self._offline_logger = self._setup_offline_logger()
        
        # 新增：心跳接收监控
        self._heartbeat_recv_logger = self._setup_heartbeat_recv_logger()
        self._heartbeat_stats_logger = self._setup_heartbeat_stats_logger()
        self._server_resource_logger = self._setup_server_resource_logger()
        self._batch_offline_logger = self._setup_batch_offline_logger()
        
        # 新增：网络异常、心跳详细、房间状态变更、ESP32日志接收日志记录器
        self._network_error_logger = self._setup_network_error_logger()
        self._heartbeat_detail_logger = self._setup_heartbeat_detail_logger()
        self._room_state_change_logger = self._setup_room_state_change_logger()
        self._esp32_logs_recv_logger = self._setup_esp32_logs_recv_logger()
        
        # 新增：心跳统计数据
        self._heartbeat_count = 0
        self._heartbeat_count_last_minute = 0
        self._last_stats_time = time.time()
        
        # 新增：批量离线检测
        self._recent_offlines = []
        self._last_heartbeat_times = {}
        
        # 新增：资源监控线程
        self._resource_monitor_thread: Optional[threading.Thread] = None
        
        # 新增：ESP32日志存储目录
        self._esp32_log_dir = self._get_esp32_log_dir()

    def _setup_offline_logger(self):
        try:
            from utils.path_helper import PathHelper
            base_dir = PathHelper.get_base_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        log_path = os.path.join(base_dir, 'offline.log')
        
        logger = logging.getLogger('OTLive.Offline')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _setup_heartbeat_recv_logger(self):
        """设置心跳接收日志记录器"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, 'heartbeat_recv.log')
        
        logger = logging.getLogger('OTLive.HeartbeatRecv')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s.%(msecs)03d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _setup_heartbeat_stats_logger(self):
        """设置心跳统计日志记录器"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, 'heartbeat_stats.log')
        
        logger = logging.getLogger('OTLive.HeartbeatStats')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _setup_server_resource_logger(self):
        """设置服务器资源监控日志记录器"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, 'server_resource.log')
        
        logger = logging.getLogger('OTLive.ServerResource')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=3,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _setup_batch_offline_logger(self):
        """设置批量离线事件日志记录器"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, 'batch_offline.log')
        
        logger = logging.getLogger('OTLive.BatchOffline')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _setup_network_error_logger(self):
        """设置网络异常日志记录器"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, 'network_error.log')
        
        logger = logging.getLogger('OTLive.NetworkError')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _setup_heartbeat_detail_logger(self):
        """设置心跳详细日志记录器"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, 'heartbeat_detail.log')
        
        logger = logging.getLogger('OTLive.HeartbeatDetail')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=20 * 1024 * 1024,
                backupCount=10,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s.%(msecs)03d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _setup_room_state_change_logger(self):
        """设置房间状态变更日志记录器"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, 'room_state_change.log')
        
        logger = logging.getLogger('OTLive.RoomStateChange')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _setup_esp32_logs_recv_logger(self):
        """设置ESP32日志接收日志记录器"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, 'esp32_logs_recv.log')
        
        logger = logging.getLogger('OTLive.ESP32LogsRecv')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        if not logger.handlers:
            handler = RotatingFileHandler(
                log_path,
                maxBytes=20 * 1024 * 1024,
                backupCount=10,
                encoding='utf-8',
                delay=True
            )
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _get_esp32_log_dir(self):
        """获取ESP32日志存储目录"""
        try:
            from utils.path_helper import PathHelper
            log_dir = PathHelper.get_warn_log_dir()
        except ImportError:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, 'log')
        
        esp32_log_dir = os.path.join(log_dir, 'esp32')
        if not os.path.exists(esp32_log_dir):
            os.makedirs(esp32_log_dir)
        
        return esp32_log_dir

    def set_socketio(self, socketio):
        self._socketio = socketio
        self.logger.info("Socket.IO实例已设置")

    def _init_rooms(self):
        rooms_config = self.config.get_rooms_config()
        
        for room_config in rooms_config:
            devices = {}
            for device_config in room_config.get('devices', []):
                default_state = False
                devices[device_config['name']] = Device(
                    id=device_config['id'],
                    name=device_config['name'],
                    label=device_config['label'],
                    pin=device_config['pin'],
                    trigger_on_duration=device_config.get('trigger_on_duration', 3),
                    trigger_off_duration=device_config.get('trigger_off_duration', 1),
                    state=default_state,
                    enabled=device_config.get('enabled', False),
                    gift_event=device_config.get('gift_event', ''),
                    trigger_sound=device_config.get('trigger_sound', False),
                    trigger_sound_delay=device_config.get('trigger_sound_delay', 0),
                    loop_action=device_config.get('loop_action', 'manual'),
                    loop_minute=device_config.get('loop_minute', ''),
                    loop_duration=device_config.get('loop_duration', 0.0)
                )
            
            self.rooms[room_config['id']] = Room(
                id=room_config['id'],
                name=room_config['name'],
                ip=room_config['ip'],
                port=room_config['port'],
                devices=devices,
                online=room_config.get('online', False),
                last_seen=room_config.get('last_seen'),
                rssi=room_config.get('rssi', -100),
                sort_order=room_config.get('sort_order', 0),
                intercom_volume=room_config.get('intercom_volume', 50),
                background_music_url=room_config.get('background_music_url', ''),
                live_url=room_config.get('live_url', ''),
                enabled=room_config.get('enabled', True),
                version=''
            )
        
        self.logger.info(f"初始化{len(self.rooms)}个房间配置")

    def _load_all_rooms_voice_status(self):
        """从远程API加载所有房间的voice_status"""
        try:
            import requests
            license_id = self.config.get_license_id() or 0
            
            for room_id, room in self.rooms.items():
                try:
                    room_ip = room.ip
                    if not room_ip:
                        continue
                        
                    response = requests.get(
                        f'https://live.hzjt.com/api/upload_voice.php?action=get&room={room_ip}&license_id={license_id}',
                        timeout=5
                    )
                    result = response.json()
                    
                    if result.get('code') == 0 and result.get('data'):
                        voice_status = result['data'].get('voice_status', 0)
                        room.voice_status = bool(voice_status == 2)
                        self.logger.info(f"房间{room_id} voice_status已加载: {room.voice_status}")
                except Exception as e:
                    self.logger.warning(f"加载房间{room_id} voice_status失败: {e}")
        except Exception as e:
            self.logger.error(f"加载所有房间voice_status失败: {e}")

    def reload_rooms_config(self):
        rooms_config = self.config.get_rooms_config()
        
        for room_config in rooms_config:
            if room_config['id'] in self.rooms:
                room = self.rooms[room_config['id']]
                room.name = room_config.get('name', room.name)
                room.ip = room_config.get('ip', room.ip)
                room.port = room_config.get('port', room.port)
                room.online = room_config.get('online', room.online)
                room.last_seen = room_config.get('last_seen', room.last_seen)
                room.rssi = room_config.get('rssi', room.rssi)
                room.sort_order = room_config.get('sort_order', room.sort_order)
                room.intercom_volume = room_config.get('intercom_volume', room.intercom_volume)
                room.background_music_url = room_config.get('background_music_url', room.background_music_url)
                room.live_url = room_config.get('live_url', room.live_url)
                room.enabled = room_config.get('enabled', room.enabled)
                
                for device_config in room_config.get('devices', []):
                    device_name = device_config['name']
                    if device_name in room.devices:
                        room.devices[device_name].id = device_config.get('id', room.devices[device_name].id)
                        room.devices[device_name].label = device_config.get('label', room.devices[device_name].label)
                        room.devices[device_name].pin = device_config.get('pin', room.devices[device_name].pin)
                        room.devices[device_name].trigger_on_duration = device_config.get('trigger_on_duration', room.devices[device_name].trigger_on_duration)
                        room.devices[device_name].trigger_off_duration = device_config.get('trigger_off_duration', room.devices[device_name].trigger_off_duration)
                        room.devices[device_name].enabled = device_config.get('enabled', room.devices[device_name].enabled)
                        room.devices[device_name].gift_event = device_config.get('gift_event', room.devices[device_name].gift_event)
                        room.devices[device_name].trigger_sound = device_config.get('trigger_sound', room.devices[device_name].trigger_sound)
                        room.devices[device_name].trigger_sound_delay = device_config.get('trigger_sound_delay', room.devices[device_name].trigger_sound_delay)
                        room.devices[device_name].loop_action = device_config.get('loop_action', room.devices[device_name].loop_action)
                        room.devices[device_name].loop_minute = device_config.get('loop_minute', room.devices[device_name].loop_minute)
                        room.devices[device_name].loop_duration = device_config.get('loop_duration', room.devices[device_name].loop_duration)
        
        self.logger.info(f"重新加载{len(self.rooms)}个房间配置")

    def reload_rooms(self):
        self.config.reload()
        self.reload_rooms_config()

    def start(self):
        if self.is_running:
            self.logger.warning("设备管理器已在运行")
            return
            
        self.is_running = True
        
        if self.enable_monitoring and not self.simulation_mode:
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_listener, daemon=True)
            self._heartbeat_thread.start()
            
            self._offline_check_thread = threading.Thread(target=self._offline_checker, daemon=True)
            self._offline_check_thread.start()
            
            self._resource_monitor_thread = threading.Thread(target=self._resource_monitor_loop, daemon=True)
            self._resource_monitor_thread.start()
        else:
            self.logger.info("房间监控已禁用（模拟模式或配置禁用）")
        
        self.logger.info("设备管理器已启动")

    def stop(self):
        self.is_running = False
        
        if self._heartbeat_socket:
            try:
                self._heartbeat_socket.close()
            except:
                pass
        
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)
        if self._offline_check_thread:
            self._offline_check_thread.join(timeout=2)
        if self._resource_monitor_thread:
            self._resource_monitor_thread.join(timeout=2)
            
        self.logger.info("设备管理器已停止")

    def _heartbeat_listener(self):
        self.logger.info(f"UDP心跳监听线程已启动，端口: {self.heartbeat_port}")
        
        try:
            self._heartbeat_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._heartbeat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._heartbeat_socket.bind(('0.0.0.0', self.heartbeat_port))
            self._heartbeat_socket.settimeout(1.0)
            
            self.logger.info(f"UDP心跳监听已绑定端口 {self.heartbeat_port}")
        except Exception as e:
            self.logger.error(f"UDP心跳监听启动失败: {e}")
            return
        
        while self.is_running:
            try:
                data, addr = self._heartbeat_socket.recvfrom(4096)
                self._process_heartbeat(data, addr)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                if self.is_running:
                    self.logger.error(f"UDP心跳接收错误: {e}")
        
        self.logger.info("UDP心跳监听线程已退出")

    def _process_heartbeat(self, data: bytes, addr: tuple):
        recv_time = time.time()
        try:
            heartbeat = json.loads(data.decode('utf-8'))
            
            if heartbeat.get('type') == 'heartbeat_logs':
                esp_ip = heartbeat.get('ip', addr[0])
                room = self.get_room_by_ip(esp_ip)
                if room and 'logs' in heartbeat:
                    logs_data = heartbeat['logs']
                    self._save_esp32_logs(room.id, logs_data, recv_time)
                    self.logger.info(f"房间{room.id}心跳日志已接收并保存: {len(logs_data)}条")
                return
            
            if heartbeat.get('type') != 'heartbeat':
                return
            
            esp_ip = heartbeat.get('ip', addr[0])
            seq = heartbeat.get('seq', 0)
            ts = heartbeat.get('ts', 0)
            
            room = self.get_room_by_ip(esp_ip)
            if not room:
                self.logger.debug(f"收到未知IP的心跳: {esp_ip}")
                return
            
            if not room.enabled:
                return
            
            latency = (recv_time - room.last_seen) * 1000 if room.last_seen else 0
            
            self._heartbeat_recv_logger.info(
                f"房间{room.id} 心跳接收: seq={seq}, rssi={heartbeat.get('rssi', -100)}, "
                f"audio={heartbeat.get('audio_active', 0)}, heap={heartbeat.get('free_heap', 0)}, "
                f"latency={latency:.0f}ms"
            )
            
            self._heartbeat_detail_logger.info(
                f"房间{room.id} 详细心跳: seq={seq}, ts={ts}, recv_time={recv_time:.3f}, "
                f"rssi={heartbeat.get('rssi', -100)}, audio={heartbeat.get('audio_active', 0)}, "
                f"intercom={heartbeat.get('intercom_enabled', 0)}, heap={heartbeat.get('free_heap', 0)}, "
                f"uptime={heartbeat.get('uptime', 0)}, version={heartbeat.get('version', 'unknown')}, "
                f"latency={latency:.0f}ms, devices={json.dumps(heartbeat.get('devices', {}))}"
            )
            
            if seq > 0 and hasattr(room, '_last_seq'):
                expected_seq = room._last_seq + 1
                if seq != expected_seq:
                    lost_count = seq - expected_seq
                    self._network_error_logger.warning(
                        f"房间{room.id} 心跳丢包: expected_seq={expected_seq}, actual_seq={seq}, "
                        f"lost_count={lost_count}, latency={latency:.0f}ms"
                    )
            
            room._last_seq = seq
            
            if latency > 1000:
                self._network_error_logger.warning(
                    f"房间{room.id} 心跳延迟过高: latency={latency:.0f}ms, seq={seq}, rssi={heartbeat.get('rssi', -100)}"
                )
            
            self._heartbeat_count += 1
            self._last_heartbeat_times[room.id] = recv_time
            
            previous_online = room.online
            previous_rssi = room.rssi
            previous_version = room.version
            
            with self._lock:
                room.online = True
                room.last_seen = recv_time
                room.rssi = heartbeat.get('rssi', -100)
                room.audio_active = heartbeat.get('audio_active', False)
                room.version = heartbeat.get('version', '')
                
                if not previous_online:
                    room.online_since = recv_time
                    room.rssi_history = []
                    self._room_state_change_logger.info(
                        f"房间{room.id} 上线: ip={room.ip}, rssi={room.rssi}, version={room.version}"
                    )
                
                if previous_online and previous_rssi != room.rssi:
                    rssi_change = room.rssi - previous_rssi
                    self._room_state_change_logger.info(
                        f"房间{room.id} RSSI变化: {previous_rssi} -> {room.rssi} (变化{rssi_change}dBm)"
                    )
                
                if previous_version != room.version:
                    self._room_state_change_logger.info(
                        f"房间{room.id} 版本变化: {previous_version} -> {room.version}"
                    )
                
                room.rssi_history.append(room.rssi)
                if len(room.rssi_history) > 10:
                    room.rssi_history = room.rssi_history[-10:]
                
                for device_name, device_state in heartbeat.get('devices', {}).items():
                    if device_name in room.devices:
                        room.devices[device_name].state = device_state
            
            self._save_room_status(room.id, {
                'online': True,
                'last_seen': room.last_seen,
                'rssi': room.rssi
            })
            
            status_changed = (previous_online != room.online or previous_rssi != room.rssi)
            
            if (status_changed or room.version) and self._socketio:
                try:
                    self._socketio.emit('room_status_update', {
                        'room_id': room.id,
                        'online': room.online,
                        'enabled': room.enabled,
                        'rssi': room.rssi,
                        'last_seen': room.last_seen,
                        'version': room.version,
                        'audio_active': room.audio_active
                    }, namespace='/')
                    self.logger.info(f"房间{room.id}状态变化已推送: online={room.online}, rssi={room.rssi}, version={room.version}")
                except Exception as e:
                    self.logger.error(f"推送房间{room.id}状态更新失败: {e}")
            
            self.logger.debug(f"房间{room.id}心跳: RSSI={room.rssi}, audio={room.audio_active}")
            
        except json.JSONDecodeError:
            self.logger.warning(f"收到无效的心跳JSON数据: {addr}")
        except Exception as e:
            self.logger.error(f"处理心跳数据失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _offline_checker(self):
        self.logger.info(f"离线检测线程已启动，超时: {self.heartbeat_timeout}秒")
        
        while self.is_running:
            try:
                self.heartbeat_timeout = self.config.get('performance.heartbeat_timeout', 15)
                self._check_offline_rooms()
                time.sleep(3)
            except Exception as e:
                self.logger.error(f"离线检测错误: {e}")
    
    def _check_offline_rooms(self):
        if self.simulation_mode:
            return
        
        now = time.time()
        
        # 心跳统计（每分钟）
        if now - self._last_stats_time >= 60:
            self._heartbeat_stats_logger.info(
                f"心跳统计: 过去1分钟收到{self._heartbeat_count}个心跳, "
                f"上一分钟{self._heartbeat_count_last_minute}个"
            )
            self._heartbeat_count_last_minute = self._heartbeat_count
            self._heartbeat_count = 0
            self._last_stats_time = now
        
        offline_rooms = []
        
        for room_id, room in self.rooms.items():
            if not room.enabled:
                continue
            
            if not room.online:
                continue
            
            if room.last_seen is None:
                with self._lock:
                    room.online = False
                
                self._save_room_status(room_id, {'online': False, 'rssi': -100})
                
                if self._socketio:
                    try:
                        self._socketio.emit('room_status_update', {
                            'room_id': room_id,
                            'online': False,
                            'enabled': room.enabled,
                            'rssi': -100,
                            'last_seen': None
                        }, namespace='/')
                    except Exception as e:
                        self.logger.error(f"推送房间{room_id}离线状态失败: {e}")
                
                self._write_offline_log(room, 'no_heartbeat_ever', 0, {})
                self.logger.info(f"房间{room_id}无心跳记录，标记为离线")
                continue
            
            elapsed = now - room.last_seen
            
            if elapsed > self.heartbeat_timeout:
                previous_online = room.online
                
                with self._lock:
                    room.online = False
                
                snapshot = {
                    'rssi': room.rssi,
                    'audio_active': room.audio_active,
                    'online_since': room.online_since,
                    'rssi_history': list(room.rssi_history),
                    'last_seen': room.last_seen,
                    'devices': {name: dev.state for name, dev in room.devices.items()}
                }
                
                self._save_room_status(room_id, {'online': False, 'rssi': -100})
                
                with self._lock:
                    room.rssi_history = []
                    room.online_since = None
                
                if previous_online and self._socketio:
                    try:
                        self._socketio.emit('room_status_update', {
                            'room_id': room_id,
                            'online': False,
                            'enabled': room.enabled,
                            'rssi': -100,
                            'last_seen': room.last_seen
                        }, namespace='/')
                        self.logger.info(f"房间{room_id}心跳超时({elapsed:.1f}s>{self.heartbeat_timeout}s)，标记为离线")
                    except Exception as e:
                        self.logger.error(f"推送房间{room_id}离线状态失败: {e}")
                
                self._write_offline_log(room, 'heartbeat_timeout', elapsed, snapshot)
                
                # 记录离线事件用于批量检测
                offline_rooms.append(room_id)
        
        # 批量离线检测
        if offline_rooms:
            self._check_batch_offline(offline_rooms, now)

    def _check_batch_offline(self, offline_rooms: list, now: float):
        """检测批量离线事件"""
        try:
            # 添加到最近离线列表
            self._recent_offlines.extend([(room_id, now) for room_id in offline_rooms])
            
            # 清理10秒前的记录
            cutoff = now - 10
            self._recent_offlines = [(rid, t) for rid, t in self._recent_offlines if t >= cutoff]
            
            # 统计10秒内离线的房间数
            recent_offline_rooms = set(rid for rid, t in self._recent_offlines)
            offline_count = len(recent_offline_rooms)
            
            # 获取服务器资源使用情况
            cpu_usage, mem_usage = self._get_server_resources()
            
            # 获取过去10秒的心跳接收情况
            heartbeat_count_last_10s = 0
            ten_seconds_ago = now - 10
            for room_id, last_time in self._last_heartbeat_times.items():
                if last_time >= ten_seconds_ago:
                    heartbeat_count_last_10s += 1
            
            # 判断是否为批量离线
            if offline_count >= 3:
                self._batch_offline_logger.info(
                    f"[批量离线事件] 10秒内离线房间数: {offline_count}, "
                    f"离线房间: {sorted(list(recent_offline_rooms))}, "
                    f"服务器CPU: {cpu_usage:.1f}%, 内存: {mem_usage:.1f}%, "
                    f"过去10秒心跳数: {heartbeat_count_last_10s}"
                )
                
                # 判断是服务器问题还是网络问题
                if cpu_usage > 80 or mem_usage > 85:
                    self._batch_offline_logger.info(
                        f"[疑似原因] 服务器资源使用过高 - CPU: {cpu_usage:.1f}%, 内存: {mem_usage:.1f}%"
                    )
                elif heartbeat_count_last_10s < 3:
                    self._batch_offline_logger.info(
                        f"[疑似原因] 网络中断 - 过去10秒仅收到{heartbeat_count_last_10s}个心跳"
                    )
                else:
                    self._batch_offline_logger.info(
                        f"[疑似原因] 需要进一步分析 - 服务器资源正常, 但有{offline_count}个房间同时离线"
                    )
        except Exception as e:
            self.logger.error(f"批量离线检测错误: {e}")

    def _get_server_resources(self):
        """获取服务器资源使用情况"""
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=0.1)
            mem_usage = psutil.virtual_memory().percent
            return cpu_usage, mem_usage
        except ImportError:
            return 0.0, 0.0
        except Exception as e:
            return 0.0, 0.0

    def _resource_monitor_loop(self):
        """资源监控循环"""
        while self.is_running:
            try:
                cpu_usage, mem_usage = self._get_server_resources()
                self._server_resource_logger.info(
                    f"CPU: {cpu_usage:.1f}%, 内存: {mem_usage:.1f}%"
                )
                time.sleep(5)
            except Exception as e:
                if self.is_running:
                    self.logger.error(f"资源监控错误: {e}")
                time.sleep(5)

    def _infer_offline_cause(self, snapshot, elapsed):
        causes = []
        
        rssi_history = snapshot.get('rssi_history', [])
        last_rssi = snapshot.get('rssi', -100)
        audio_active = snapshot.get('audio_active', False)
        
        if len(rssi_history) >= 3:
            recent = rssi_history[-3:]
            declining = all(recent[i] < recent[i - 1] for i in range(1, len(recent)))
            if declining and recent[-1] < -70:
                causes.append("WiFi信号弱化")
        
        if last_rssi < -80:
            causes.append("WiFi信号极弱")
        
        if audio_active:
            causes.append("音频播放中(可能阻塞)")
        
        if elapsed < self.heartbeat_timeout + 5:
            causes.append("突然断连")
        elif elapsed > self.heartbeat_timeout * 2:
            causes.append("长时间无响应")
        
        if not causes:
            causes.append("未知原因")
        
        return " + ".join(causes)

    def _get_event_type_string(self, event_type: int) -> str:
        """获取事件类型字符串"""
        event_map = {
            1: 'HEARTBEAT_ATTEMPT',
            2: 'HEARTBEAT_SUCCESS',
            3: 'HEARTBEAT_FAILED',
            4: 'WIFI_DISCONNECTED',
            5: 'WIFI_CONNECTING',
            6: 'WIFI_CONNECTED',
            7: 'WIFI_RECONNECT_START',
            8: 'WIFI_RECONNECT_SUCCESS',
            9: 'WIFI_RECONNECT_FAILED',
            10: 'LOOP_BLOCKED',
            11: 'AUDIO_START',
            12: 'AUDIO_STOP',
            13: 'RESET_DETECTED',
            14: 'MEMORY_LOW',
            15: 'LOGS_UPLOAD_START',
            16: 'LOGS_UPLOAD_SUCCESS',
            17: 'LOGS_UPLOAD_FAILED'
        }
        return event_map.get(event_type, f'UNKNOWN_{event_type}')

    def _rotate_log_file(self, log_file: str, room_id: int):
        """轮转日志文件"""
        try:
            log_dir = os.path.dirname(log_file)
            base_name = os.path.basename(log_file)
            name_without_ext = os.path.splitext(base_name)[0]
            
            old_log3 = os.path.join(log_dir, f'{name_without_ext}.3.txt')
            if os.path.exists(old_log3):
                os.remove(old_log3)
            
            old_log2 = os.path.join(log_dir, f'{name_without_ext}.2.txt')
            old_log1 = os.path.join(log_dir, f'{name_without_ext}.1.txt')
            
            if os.path.exists(old_log2):
                os.rename(old_log2, old_log3)
            if os.path.exists(old_log1):
                os.rename(old_log1, old_log2)
            
            os.rename(log_file, old_log1)
            
            self.logger.info(f"房间{room_id}日志文件已轮转")
        except Exception as e:
            self.logger.error(f"轮转房间{room_id}日志文件失败: {e}")

    def _save_warn_log(self, room_id: int, logs_data: list):
        """保存设备心跳警告日志（带轮转）"""
        try:
            from utils.path_helper import PathHelper
            
            log_dir = PathHelper.get_warn_log_dir()
            log_file = os.path.join(log_dir, f'warn_{room_id}.txt')
            
            if os.path.exists(log_file):
                file_size = os.path.getsize(log_file)
                max_size = 5 * 1024 * 1024
                
                if file_size >= max_size:
                    self._rotate_log_file(log_file, room_id)
            
            with open(log_file, 'a', encoding='utf-8') as f:
                for log_entry in logs_data:
                    timestamp = datetime.fromtimestamp(log_entry.get('timestamp', 0) / 1000)
                    event_type = log_entry.get('event_type', 0)
                    error_code = log_entry.get('error_code', 0)
                    error_msg = log_entry.get('error_msg', '')
                    rssi = log_entry.get('rssi', -100)
                    free_heap = log_entry.get('free_heap', 0)
                    max_alloc = log_entry.get('max_alloc_heap', 0)
                    loop_duration = log_entry.get('loop_duration', 0)
                    audio_active = log_entry.get('audio_active', False)
                    
                    event_type_str = self._get_event_type_string(event_type)
                    status_str = 'OK' if event_type in [2, 6, 8, 12, 16] else 'ERROR' if event_type in [3, 4, 9, 10, 13, 14, 17] else 'INFO'
                    
                    log_line = (
                        f"{timestamp.strftime('%Y-%m-%d %H:%M:%S'):<22} "
                        f"{event_type_str:<20} "
                        f"{status_str:<8} "
                        f"RSSI={rssi:>4}dBm, "
                        f"Heap={free_heap:>6}, "
                        f"MaxAlloc={max_alloc:>6}, "
                        f"Loop={loop_duration:>4}ms, "
                        f"Audio={'Y' if audio_active else 'N'}, "
                        f"Msg={error_msg}\n"
                    )
                    f.write(log_line)
            
            self.logger.info(f"房间{room_id}警告日志已保存: {len(logs_data)}条")
        except Exception as e:
            self.logger.error(f"保存房间{room_id}警告日志失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _save_esp32_logs(self, room_id: int, logs_data: list, recv_time: float):
        """保存ESP32上传的详细日志到JSON文件"""
        try:
            timestamp_str = datetime.fromtimestamp(recv_time).strftime('%Y%m%d_%H%M%S')
            log_filename = f'room_{room_id}_{timestamp_str}.json'
            log_filepath = os.path.join(self._esp32_log_dir, log_filename)
            
            log_entry = {
                'room_id': room_id,
                'recv_time': recv_time,
                'recv_time_str': datetime.fromtimestamp(recv_time).strftime('%Y-%m-%d %H:%M:%S.%f'),
                'logs_count': len(logs_data),
                'logs': logs_data
            }
            
            with open(log_filepath, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2)
            
            self._esp32_logs_recv_logger.info(
                f"房间{room_id} ESP32日志已保存: file={log_filename}, count={len(logs_data)}, "
                f"recv_time={datetime.fromtimestamp(recv_time).strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            self._cleanup_old_esp32_logs(room_id)
            
        except Exception as e:
            self.logger.error(f"保存房间{room_id} ESP32日志失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _cleanup_old_esp32_logs(self, room_id: int, max_files: int = 50):
        """清理旧的ESP32日志文件，每个房间最多保留max_files个"""
        try:
            room_log_files = []
            for filename in os.listdir(self._esp32_log_dir):
                if filename.startswith(f'room_{room_id}_') and filename.endswith('.json'):
                    filepath = os.path.join(self._esp32_log_dir, filename)
                    room_log_files.append((filepath, os.path.getmtime(filepath)))
            
            if len(room_log_files) > max_files:
                room_log_files.sort(key=lambda x: x[1])
                files_to_delete = room_log_files[:len(room_log_files) - max_files]
                for filepath, _ in files_to_delete:
                    os.remove(filepath)
                    self.logger.info(f"已删除旧ESP32日志: {os.path.basename(filepath)}")
        except Exception as e:
            self.logger.error(f"清理房间{room_id}旧ESP32日志失败: {e}")

    def _write_offline_log(self, room, reason, elapsed, snapshot):
        try:
            if reason == 'no_heartbeat_ever':
                self._offline_logger.info(
                    f"[OFFLINE] 房间ID={room.id} | 名称={room.name} | IP={room.ip}\n"
                    f"  原因: no_heartbeat_ever (系统启动后从未收到心跳)\n"
                    f"  疑似原因: 设备未开机或网络未连通"
                )
                return
            
            rssi_history = snapshot.get('rssi_history', [])
            last_rssi = snapshot.get('rssi', -100)
            audio_active = snapshot.get('audio_active', False)
            online_since = snapshot.get('online_since')
            devices = snapshot.get('devices', {})
            last_seen = snapshot.get('last_seen')
            
            online_duration = ''
            if online_since and last_seen:
                duration = last_seen - online_since
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                seconds = int(duration % 60)
                online_duration = f"{hours}时{minutes}分{seconds}秒"
            else:
                online_duration = "未知"
            
            rssi_trend = ''
            if rssi_history:
                recent = rssi_history[-4:]
                rssi_trend = str(recent)
            
            devices_str = ', '.join(f"{name}={'ON' if state else 'OFF'}" for name, state in devices.items())
            
            suspected = self._infer_offline_cause(snapshot, elapsed)
            
            diagnosis_type, diagnosis_desc, diagnosis_logs = self._diagnose_offline_reason(room.id, last_seen if last_seen else time.time())
            
            diagnosis_logs_str = ''
            if diagnosis_logs:
                diagnosis_logs_str = '\n  相关日志:\n'
                for log in diagnosis_logs[-5:]:
                    if isinstance(log, dict):
                        diagnosis_logs_str += f"    {log}\n"
                    else:
                        diagnosis_logs_str += f"    {log}\n"
            
            self._offline_logger.info(
                f"[OFFLINE] 房间ID={room.id} | 名称={room.name} | IP={room.ip}\n"
                f"  原因: {reason}\n"
                f"  超时详情: 最后心跳距今{elapsed:.1f}秒, 超时阈值{self.heartbeat_timeout}秒\n"
                f"  离线前状态: RSSI={last_rssi}dBm, audio_active={audio_active}, 在线持续={online_duration}\n"
                f"  离线前RSSI趋势: {rssi_trend}\n"
                f"  离线前设备状态: {devices_str}\n"
                f"  疑似原因: {suspected}\n"
                f"  诊断结果: [{diagnosis_type}] {diagnosis_desc}{diagnosis_logs_str}"
            )
            
            self._room_state_change_logger.info(
                f"房间{room.id} 离线: reason={reason}, diagnosis={diagnosis_type}, desc={diagnosis_desc}"
            )
        except Exception as e:
            self.logger.error(f"写入离线日志失败: {e}")

    def _diagnose_offline_reason(self, room_id: int, offline_time: float):
        """
        根据ESP32日志自动诊断离线原因
        返回: (原因类型, 详细描述, 相关日志片段)
        """
        try:
            esp32_logs = self._get_esp32_logs_before_offline(room_id, offline_time)
            
            if esp32_logs:
                logs = esp32_logs.get('logs', [])
                if logs:
                    last_log = logs[-1]
                    event_type = last_log.get('event_type', 0)
                    error_msg = last_log.get('error_msg', '')
                    rssi = last_log.get('rssi', -100)
                    free_heap = last_log.get('free_heap', 0)
                    uptime = last_log.get('uptime', 0)
                    
                    EVENT_WIFI_DISCONNECTED = 4
                    EVENT_WIFI_RECONNECT_FAILED = 9
                    EVENT_MEMORY_LOW = 14
                    EVENT_RESET_DETECTED = 13
                    EVENT_LOOP_BLOCKED = 10
                    EVENT_WIFI_SIGNAL_WEAK = 30
                    EVENT_SPIFFS_FULL = 18
                    EVENT_HEARTBEAT_FAILED = 3
                    
                    if event_type == EVENT_WIFI_DISCONNECTED:
                        return ('WIFI_DISCONNECT', 
                                f"WiFi断开: {error_msg}, RSSI={rssi}dBm",
                                logs[-5:])
                    
                    if event_type == EVENT_WIFI_RECONNECT_FAILED:
                        return ('WIFI_RECONNECT_FAILED',
                                f"WiFi重连失败: {error_msg}, 尝试次数={last_log.get('error_code', 0)}",
                                logs[-5:])
                    
                    if event_type == EVENT_MEMORY_LOW:
                        return ('MEMORY_LOW',
                                f"内存不足: freeHeap={free_heap}, {error_msg}",
                                logs[-3:])
                    
                    if event_type == EVENT_RESET_DETECTED:
                        reset_reason = last_log.get('reset_reason', 'unknown')
                        return ('SYSTEM_RESET',
                                f"系统重启: {reset_reason}, uptime={uptime}s",
                                logs[-10:])
                    
                    if event_type == EVENT_LOOP_BLOCKED:
                        loop_duration = last_log.get('loop_duration', 0)
                        return ('LOOP_BLOCKED',
                                f"Loop阻塞: duration={loop_duration}ms, {error_msg}",
                                logs[-5:])
                    
                    if event_type == EVENT_WIFI_SIGNAL_WEAK:
                        return ('WIFI_SIGNAL_WEAK',
                                f"WiFi信号弱: RSSI={rssi}dBm, {error_msg}",
                                logs[-5:])
                    
                    if event_type == EVENT_SPIFFS_FULL:
                        spiffs_free = last_log.get('error_code', 0)
                        return ('SPIFFS_FULL',
                                f"SPIFFS空间不足: free={spiffs_free}bytes",
                                logs[-3:])
                    
                    if event_type == EVENT_HEARTBEAT_FAILED:
                        return ('HEARTBEAT_FAILED',
                                f"心跳发送失败: {error_msg}",
                                logs[-3:])
                    
                    for log in reversed(logs[-10:]):
                        if log.get('event_type') in [EVENT_WIFI_DISCONNECTED, EVENT_WIFI_RECONNECT_FAILED, 
                                                     EVENT_MEMORY_LOW, EVENT_RESET_DETECTED]:
                            return ('ESP32_ERROR',
                                    f"ESP32异常事件: event_type={log.get('event_type')}, {log.get('error_msg')}",
                                    logs[-10:])
            
            heartbeat_logs = self._get_recent_heartbeat_logs(room_id, offline_time)
            if heartbeat_logs:
                last_heartbeat = heartbeat_logs[-1] if heartbeat_logs else None
                if last_heartbeat:
                    latency = last_heartbeat.get('latency', 0)
                    rssi = last_heartbeat.get('rssi', -100)
                    
                    if latency > 1000:
                        return ('HEARTBEAT_DELAY',
                                f"心跳延迟过高: latency={latency}ms, RSSI={rssi}dBm",
                                heartbeat_logs[-5:])
                    
                    rssi_values = [log.get('rssi', -100) for log in heartbeat_logs[-10:]]
                    if rssi_values and all(rssi < -70 for rssi in rssi_values):
                        avg_rssi = sum(rssi_values) / len(rssi_values)
                        return ('WIFI_SIGNAL_WEAK',
                                f"WiFi信号持续弱: 平均RSSI={avg_rssi:.1f}dBm",
                                heartbeat_logs[-10:])
            
            return ('HEARTBEAT_TIMEOUT',
                    f"心跳超时: 最后心跳时间={offline_time - self.heartbeat_timeout:.1f}s前",
                    [])
                    
        except Exception as e:
            self.logger.error(f"诊断房间{room_id}离线原因失败: {e}")
            return ('UNKNOWN', f"诊断失败: {str(e)}", [])

    def _get_esp32_logs_before_offline(self, room_id: int, offline_time: float):
        """获取离线前的ESP32日志"""
        try:
            if not os.path.exists(self._esp32_log_dir):
                return None
            
            room_log_files = []
            for filename in os.listdir(self._esp32_log_dir):
                if filename.startswith(f'room_{room_id}_') and filename.endswith('.json'):
                    filepath = os.path.join(self._esp32_log_dir, filename)
                    file_mtime = os.path.getmtime(filepath)
                    if file_mtime <= offline_time:
                        room_log_files.append((filepath, file_mtime))
            
            if not room_log_files:
                return None
            
            room_log_files.sort(key=lambda x: x[1], reverse=True)
            latest_log_file = room_log_files[0][0]
            
            with open(latest_log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.error(f"获取房间{room_id}离线前ESP32日志失败: {e}")
            return None

    def _get_recent_heartbeat_logs(self, room_id: int, offline_time: float):
        """获取最近的心跳日志（从heartbeat_detail.log）"""
        try:
            log_dir = self._esp32_log_dir.replace('esp32', '')
            heartbeat_detail_log = os.path.join(log_dir, 'heartbeat_detail.log')
            
            if not os.path.exists(heartbeat_detail_log):
                return []
            
            heartbeat_logs = []
            with open(heartbeat_detail_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[-100:]:
                    if f'房间{room_id}' in line:
                        try:
                            parts = line.split(' - ')
                            if len(parts) >= 2:
                                timestamp_str = parts[0]
                                log_content = parts[1]
                                
                                import re
                                latency_match = re.search(r'latency=(\d+)ms', log_content)
                                rssi_match = re.search(r'rssi=(-?\d+)', log_content)
                                
                                latency = int(latency_match.group(1)) if latency_match else 0
                                rssi = int(rssi_match.group(1)) if rssi_match else -100
                                
                                heartbeat_logs.append({
                                    'timestamp': timestamp_str,
                                    'latency': latency,
                                    'rssi': rssi,
                                    'content': log_content
                                })
                        except Exception:
                            continue
            
            return heartbeat_logs[-20:]
            
        except Exception as e:
            self.logger.error(f"获取房间{room_id}最近心跳日志失败: {e}")
            return []

    def control_device(self, room_id: int, device_name: str, action: str, duration: float = None, play_sound: bool = False, sound_delay: float = 0) -> bool:
        try:
            if room_id not in self.rooms:
                self.logger.error(f"房间{room_id}不存在")
                return False
                
            room = self.rooms[room_id]
            
            if device_name not in room.devices:
                self.logger.error(f"房间{room_id}设备{device_name}不存在")
                return False
                
            if action not in ['on', 'off', 'toggle']:
                self.logger.error(f"无效的操作: {action}")
                return False
            
            was_offline = not room.online
            if was_offline:
                self.logger.info(f"房间{room_id}当前显示离线，尝试发送控制命令: {device_name} {action}")
            
            # 获取设备的trigger_on_duration，如果没有传入duration参数
            device_duration = duration if duration is not None else room.devices[device_name].trigger_on_duration
            
            command = {
                'type': 'control',
                'device': device_name,
                'action': action,
                'duration': device_duration,
                'timestamp': time.time(),
                'play_sound': play_sound,
                'sound_delay': sound_delay
            }
            
            success = self._send_command(room, command)
            
            if success:
                with self._lock:
                    if action == 'toggle':
                        room.devices[device_name].state = not room.devices[device_name].state
                    else:
                        room.devices[device_name].state = (action == 'on')
                    
                    if was_offline:
                        room.online = True
                        room.last_seen = time.time()
                
                if was_offline:
                    self.logger.info(f"房间{room_id}控制成功，已更新为在线状态")
                    self._save_room_status(room_id, {
                        'online': True,
                        'last_seen': room.last_seen,
                        'rssi': room.rssi
                    })
                    if self._socketio:
                        try:
                            self._socketio.emit('room_status_update', {
                                'room_id': room_id,
                                'online': True,
                                'enabled': room.enabled,
                                'rssi': room.rssi,
                                'last_seen': room.last_seen
                            }, namespace='/')
                        except Exception as emit_error:
                            self.logger.error(f"推送房间{room_id}在线状态失败: {emit_error}")
                
                self._notify_callbacks('device_control', {
                    'room_id': room_id,
                    'device': device_name,
                    'action': action,
                    'state': room.devices[device_name].state
                })
                
                self.logger.info(f"房间{room_id}设备{device_name}{action}成功")
                return True
            else:
                self.logger.error(f"房间{room_id}设备{device_name}{action}失败")
                return False
                
        except Exception as e:
            self.logger.error(f"控制设备失败: {e}")
            return False

    def _send_command(self, room: Room, command: Dict) -> bool:
        if self.simulation_mode:
            self.logger.info(f"模拟模式：房间{room.id}命令 {command}")
            return True
            
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.response_timeout)
            
            sock.connect((room.ip, room.port))
            sock.sendall((json.dumps(command) + '\n').encode())
            
            response = sock.recv(1024).decode()
            
            result = json.loads(response)
            return result.get('status') == 'success'
            
        except Exception as e:
            self.logger.error(f"发送命令到房间{room.id}失败: {e}")
            return False
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def get_all_rooms(self) -> List[Dict]:
        with self._lock:
            rooms_data = []
            for room in self.rooms.values():
                room_dict = asdict(room)
                room_dict['devices'] = [asdict(device) for device in room.devices.values() 
                                       if not device.name.startswith('prog') or device.enabled]
                rooms_data.append(room_dict)
            return rooms_data

    def get_room(self, room_id):
        with self._lock:
            if room_id in self.rooms:
                room_dict = asdict(self.rooms[room_id])
                room_dict['devices'] = [asdict(device) for device in self.rooms[room_id].devices.values()
                                       if not device.name.startswith('prog') or device.enabled]
                return room_dict
            return None

    def get_room_with_all_devices(self, room_id):
        with self._lock:
            if room_id in self.rooms:
                room_dict = asdict(self.rooms[room_id])
                room_dict['devices'] = [asdict(device) for device in self.rooms[room_id].devices.values()]
                return room_dict
            return None

    def get_room_by_ip(self, ip):
        with self._lock:
            for room in self.rooms.values():
                if room.ip == ip:
                    return room
            return None

    def get_room_devices(self, room_id: int) -> Optional[List[Dict]]:
        with self._lock:
            if room_id in self.rooms:
                return [asdict(device) for device in self.rooms[room_id].devices.values()]
            return None

    def set_audio_active(self, room_id: int, active: bool) -> bool:
        try:
            if room_id not in self.rooms:
                return False
                
            with self._lock:
                self.rooms[room_id].audio_active = active
            
            self._notify_callbacks('audio_status', {
                'room_id': room_id,
                'active': active
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"设置音频状态失败: {e}")
            return False

    def set_room_intercom_enabled(self, room_id: int, enabled: bool) -> bool:
        try:
            if room_id not in self.rooms:
                return False
                
            with self._lock:
                self.rooms[room_id].mic_enabled = enabled
            
            self._notify_callbacks('intercom_status', {
                'room_id': room_id,
                'enabled': enabled
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"设置房间对讲状态失败: {e}")
            return False

    def get_all_intercom_status(self) -> Dict[int, bool]:
        with self._lock:
            return {room_id: room.mic_enabled for room_id, room in self.rooms.items()}

    def register_callback(self, callback: Callable):
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, event_type: str, data: Dict):
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                self.logger.error(f"回调函数执行失败: {e}")

    def update_room_name(self, room_id: int, new_name: str) -> bool:
        try:
            if room_id not in self.rooms:
                self.logger.error(f"房间{room_id}不存在")
                return False
                
            with self._lock:
                self.rooms[room_id].name = new_name
                
            self._save_room_config(room_id, 'name', new_name)
            self.logger.info(f"房间{room_id}名称已更新为: {new_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新房间名称失败: {e}")
            return False

    def update_room_sort(self, room_id: int, sort_order: int) -> bool:
        try:
            if room_id not in self.rooms:
                self.logger.error(f"房间{room_id}不存在")
                return False
                
            with self._lock:
                self.rooms[room_id].sort_order = sort_order
                
            self._save_room_config(room_id, 'sort_order', sort_order)
            self.logger.info(f"房间{room_id}排序已更新为: {sort_order}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新房间排序失败: {e}")
            return False

    def update_room_live_url(self, room_id: int, live_url: str) -> bool:
        try:
            if room_id not in self.rooms:
                self.logger.error(f"房间{room_id}不存在")
                return False
                
            with self._lock:
                self.rooms[room_id].live_url = live_url
                
            self._save_room_config(room_id, 'live_url', live_url)
            self.logger.info(f"房间{room_id}直播地址已更新为: {live_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新房间直播地址失败: {e}")
            return False

    def update_room_intercom_volume(self, room_id: int, volume: int) -> bool:
        try:
            if room_id not in self.rooms:
                self.logger.error(f"房间{room_id}不存在")
                return False
                
            with self._lock:
                self.rooms[room_id].intercom_volume = volume
                
            self._save_room_config(room_id, 'intercom_volume', volume)
            self.config.reload()
            self.reload_rooms_config()
            self.logger.info(f"房间{room_id}对讲音量已更新为: {volume}%")
            return True
            
        except Exception as e:
            self.logger.error(f"更新房间对讲音量失败: {e}")
            return False

    def update_room_background_music_url(self, room_id: int, url: str, music_name: str = '', size: int = 0) -> bool:
        try:
            if room_id not in self.rooms:
                self.logger.error(f"房间{room_id}不存在")
                return False
                
            with self._lock:
                self.rooms[room_id].background_music_url = url
                self.rooms[room_id].background_music_name = music_name
                self.rooms[room_id].background_music_size = size
                
            self._save_room_config(room_id, 'background_music_url', url)
            if music_name:
                self._save_room_config(room_id, 'background_music_name', music_name)
            if size > 0:
                self._save_room_config(room_id, 'background_music_size', size)
            self.config.reload()
            self.reload_rooms_config()
            self.logger.info(f"房间{room_id}背景音乐URL已更新为: {url}, 音乐名称: {music_name}, 大小: {size}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新房间背景音乐URL失败: {e}")
            return False

    def _save_room_config(self, room_id: int, key: str, value):
        try:
            self.logger.info(f"准备保存房间{room_id}配置: {key}={value}")
            
            # 使用数据库更新房间配置
            if key == 'background_music_url':
                self.config.update_room(room_id, background_music_url=value)
            elif key == 'background_music_name':
                pass  # 这个值不需要单独保存
            elif key == 'background_music_size':
                pass  # 这个值不需要单独保存
            elif key == 'intercom_volume':
                self.config.update_room(room_id, intercom_volume=value)
            elif key == 'name':
                self.config.update_room(room_id, name=value)
            elif key == 'sort_order':
                self.config.update_room(room_id, sort_order=value)
            elif key == 'live_url':
                self.config.update_room(room_id, live_url=value)
            else:
                self.logger.warning(f"未知的配置键: {key}")
            
            self.logger.info(f"房间{room_id}配置已更新: {key}={value}")
            
        except Exception as e:
            self.logger.error(f"保存房间配置失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def save_trigger_device_config(self, room_id: int, trigger_on_duration: float, trigger_off_duration: float):
        try:
            self.logger.info(f"准备保存房间{room_id}的trigger设备配置: on_duration={trigger_on_duration}, off_duration={trigger_off_duration}")
            
            # 添加详细的参数验证调试信息
            self.logger.debug(f"参数验证 - room_id: {room_id}, type: {type(room_id)}")
            self.logger.debug(f"参数验证 - trigger_on_duration: {trigger_on_duration}, type: {type(trigger_on_duration)}")
            self.logger.debug(f"参数验证 - trigger_off_duration: {trigger_off_duration}, type: {type(trigger_off_duration)}")
            
            # 从数据库获取房间
            room = self.config.get_room(room_id)
            if not room:
                self.logger.warning(f"房间{room_id}不存在")
                return False
            
            self.logger.debug(f"获取到房间信息: {room}")
            self.logger.debug(f"房间设备列表: {room.get('devices', [])}")
            
            # 查找trigger设备
            device_found = False
            for device in room.get('devices', []):
                self.logger.debug(f"检查设备: {device.get('name')} (ID: {device.get('id')})")
                if device.get('name') == 'trigger':
                    device_id = device.get('id')
                    old_on = device.get('trigger_on_duration')
                    old_off = device.get('trigger_off_duration')
                    
                    self.logger.info(f"找到trigger设备: ID={device_id}, 原配置: on_duration={old_on}, off_duration={old_off}")
                    
                    # 更新数据库
                    try:
                        self.logger.debug(f"调用config.update_device - device_id: {device_id}")
                        update_result = self.config.update_device(
                            device_id,
                            trigger_on_duration=trigger_on_duration,
                            trigger_off_duration=trigger_off_duration
                        )
                        self.logger.debug(f"db.update_device返回结果: {update_result}")
                        
                        if update_result:
                            self.logger.info(f"房间{room_id}的trigger设备配置已更新: on_duration {old_on}->{trigger_on_duration}, off_duration {old_off}->{trigger_off_duration}")
                            device_found = True
                        else:
                            self.logger.error(f"db.update_device返回False，更新失败")
                            return False
                            
                    except Exception as db_error:
                        self.logger.error(f"调用config.update_device时发生异常: {db_error}")
                        import traceback
                        self.logger.error(traceback.format_exc())
                        return False
                    
                    break
            
            if not device_found:
                self.logger.warning(f"房间{room_id}未找到trigger设备")
                return False
            else:
                # 重新加载房间配置
                self.logger.debug("开始重新加载房间配置...")
                reload_result = self.reload_rooms_config()
                self.logger.debug(f"reload_rooms_config返回结果: {reload_result}")
                self.logger.info("房间配置已重新加载")
            
            return device_found
            
        except Exception as e:
            self.logger.error(f"保存trigger设备配置失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _save_room_status(self, room_id: int, status_data: Dict):
        try:
            self.logger.debug(f"准备保存房间{room_id}状态: {status_data}")
            
            update_data = {}
            if 'online' in status_data:
                update_data['online'] = status_data['online']
            if 'last_seen' in status_data:
                update_data['last_seen'] = status_data['last_seen']
            if 'rssi' in status_data:
                update_data['rssi'] = status_data['rssi']
            
            if update_data:
                self.config.update_room(room_id, **update_data)
                self.logger.debug(f"房间{room_id}状态已保存: {update_data}")
            
        except Exception as e:
            self.logger.error(f"保存房间状态失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def set_room_voice_status(self, room_id: int, enabled: bool) -> bool:
        """设置房间的voice_status"""
        try:
            with self._lock:
                if room_id in self.rooms:
                    self.rooms[room_id].voice_status = enabled
                    self.logger.info(f"房间{room_id} voice_status已设置为: {enabled}")
                    return True
                else:
                    self.logger.warning(f"房间{room_id}不存在")
                    return False
        except Exception as e:
            self.logger.error(f"设置房间voice_status失败: {e}")
            return False

    def update_device(self, device_id: int, **kwargs):
        try:
            self.logger.info(f"准备更新设备{device_id}: {kwargs}")
            
            self.config.update_device(device_id, **kwargs)
            
            self.logger.info(f"设备{device_id}已更新")
            
            self.reload_rooms_config()
            self.logger.info("房间配置已重新加载")
            
            return True
            
        except Exception as e:
            self.logger.error(f"更新设备{device_id}失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def get_system_status(self) -> Dict:
        with self._lock:
            online_count = sum(1 for room in self.rooms.values() if room.online)
            total_count = len(self.rooms)
            
            rooms_data = []
            for room in self.rooms.values():
                room_dict = asdict(room)
                room_dict['devices'] = [asdict(device) for device in room.devices.values()]
                rooms_data.append(room_dict)
            
            return {
                'total_rooms': total_count,
                'online_rooms': online_count,
                'offline_rooms': total_count - online_count,
                'patrol_dialog_enabled': self.config.get_patrol_dialog_enabled(),
                'current_intercom_room_id': self.config.get_current_intercom_room_id(),
                'rooms': rooms_data
            }