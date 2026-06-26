import configparser
import os


class ConfigLoader:
    _instance = None
    _config = {}
    _config_dir = None

    def __new__(cls, config_dir=None):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_dir=None):
        if config_dir is None:
            config_dir = self._find_config_dir()
        
        if self._config_dir is None:
            self._config_dir = config_dir
        
        if not self._config:
            self._load_configs(self._config_dir)

    def _find_config_dir(self):
        """自动查找配置目录 - 仅Windows平台"""
        # 尝试导入路径助手
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'iot_pc'))
            from utils.path_helper import PathHelper
            config_ini_path = PathHelper.get_config_ini_path()
            config_dir = os.path.dirname(config_ini_path)
            if os.path.exists(os.path.join(config_dir, 'system.ini')):
                return config_dir
        except ImportError:
            pass

        # 可能的配置目录列表 - 仅Windows平台
        possible_dirs = [
            'config',
            'iot/config',
            '../config',
            os.path.dirname(os.path.abspath(__file__)),  # 当前目录
        ]

        for dir_path in possible_dirs:
            if dir_path and os.path.exists(os.path.join(dir_path, 'system.ini')):
                return dir_path

        return 'config'

    def _load_configs(self, config_dir):
        self._config = {}
        config_files = ['system.ini', 'rooms.ini', 'network.ini']

        for config_file in config_files:
            file_path = os.path.join(config_dir, config_file)
            
            if not os.path.exists(file_path):
                print(f"配置文件 {file_path} 不存在")
                continue
            
            try:
                config = configparser.ConfigParser()
                config.read(file_path, encoding='utf-8')
                config_name = config_file.replace('.ini', '')
                
                if config_name == 'system':
                    self._load_system_config(config)
                elif config_name == 'rooms':
                    self._load_rooms_config(config)
                elif config_name == 'network':
                    self._load_network_config(config)
                    
                print(f"已加载配置文件: {config_file}")
            except Exception as e:
                print(f"加载配置文件 {config_file} 失败: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"配置加载完成，共加载 {len(self._config)} 个配置文件")

    def _load_system_config(self, config):
        sections = ['system', 'server', 'audio', 'network', 'logging', 'performance']
        for section in sections:
            if config.has_section(section):
                self._config[section] = {}
                for key, value in config.items(section):
                    value = value.split('#')[0].strip()
                    self._config[section][key] = self._convert_value(key, value, section)
    
    def _convert_value(self, key, value, section):
        """根据配置项类型转换值"""
        # 布尔值
        if key in ['debug', 'simulation_mode', 'patrol_dialog_enabled', 'enabled', 'enable_room_monitoring', 'online']:
            return value.lower() == 'true'
        
        # 整数
        if key in ['port', 'sample_rate', 'channels', 'chunk_size', 'format', 'buffer_size', 
                  'input_device_index', 'output_device_index', 'udp_port', 'tcp_port', 
                  'websocket_port', 'max_bytes', 'backup_count', 'max_concurrent_rooms', 
                  'heartbeat_interval', 'current_intercom_room_id']:
            try:
                return int(value)
            except ValueError:
                return value
        
        # 浮点数
        if key in ['broadcast_interval', 'audio_buffer_timeout', 'attack_time', 'release_time', 'hold_time', 'threshold', 'device_response_timeout']:
            try:
                return float(value)
            except ValueError:
                return value
        
        # 其他保持字符串
        return value

    def _load_rooms_config(self, config):
        if not config.has_section('rooms'):
            return
        
        rooms_count = int(config.get('rooms', 'count', fallback=0))
        rooms_list = []
        
        for i in range(1, rooms_count + 1):
            room_section = f'room_{i}'
            if not config.has_section(room_section):
                continue
            
            room = {
                'id': int(config.get(room_section, 'id', fallback=i)),
                'name': config.get(room_section, 'name', fallback=''),
                'ip': config.get(room_section, 'ip', fallback=''),
                'port': int(config.get(room_section, 'port', fallback=8080)),
                'online': config.getboolean(room_section, 'online', fallback=False),
                'rssi': int(config.get(room_section, 'rssi', fallback=-100)),
                'sort_order': int(config.get(room_section, 'sort_order', fallback=0)),
                'intercom_volume': int(config.get(room_section, 'intercom_volume', fallback=50)),
                'devices': []
            }
            
            if config.has_option(room_section, 'last_seen'):
                room['last_seen'] = float(config.get(room_section, 'last_seen'))
            
            device_count = int(config.get(room_section, 'device_count', fallback=0))
            for j in range(1, device_count + 1):
                device_section = f'room_{i}_device_{j}'
                if not config.has_section(device_section):
                    continue
                
                device = {
                    'name': config.get(device_section, 'name', fallback=''),
                    'label': config.get(device_section, 'label', fallback=''),
                    'pin': int(config.get(device_section, 'pin', fallback=0)),
                    'trigger_on_duration': int(config.get(device_section, 'trigger_on_duration', fallback=3)),
                    'trigger_off_duration': int(config.get(device_section, 'trigger_off_duration', fallback=1))
                }
                
                if config.has_option(device_section, 'enabled'):
                    device['enabled'] = config.getboolean(device_section, 'enabled')
                
                if config.has_option(device_section, 'gift_event'):
                    device['gift_event'] = config.get(device_section, 'gift_event', fallback='')
                
                room['devices'].append(device)
            
            rooms_list.append(room)
        
        self._config['rooms'] = {'rooms': rooms_list}

    def _load_network_config(self, config):
        for section in config.sections():
            self._config[section] = {}
            for key, value in config.items(section):
                if ',' in value:
                    self._config[section][key] = [v.strip() for v in value.split(',')]
                else:
                    self._config[section][key] = value

    def get(self, key, default=None):
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_system_config(self):
        return self._config.get('system', {})

    def get_server_config(self):
        return self._config.get('server', {})

    def get_audio_config(self):
        return self._config.get('audio', {})

    def get_network_config(self):
        return self._config.get('network', {})

    def get_rooms_config(self):
        rooms_config = self._config.get('rooms', {})
        if isinstance(rooms_config, dict) and 'rooms' in rooms_config:
            return rooms_config['rooms']
        return []

    def get_logging_config(self):
        return self._config.get('logging', {})

    def get_performance_config(self):
        return self._config.get('performance', {})

    def get_patrol_dialog_enabled(self):
        value = self.get_system_config().get('patrol_dialog_enabled', 'true')
        return value.lower() == 'true' if isinstance(value, str) else bool(value)

    def get_current_intercom_room_id(self):
        value = self.get_system_config().get('current_intercom_room_id', '0')
        return int(value) if value else 0

    def debug_print(self):
        print(f"=== 配置调试信息 ===")
        print(f"配置键: {list(self._config.keys())}")
        if 'system' in self._config:
            print(f"system配置: {self._config['system']}")
        print(f"===================")

    def reload(self, config_dir=None):
        if config_dir is None:
            config_dir = self._config_dir
        self._config = {}
        self._load_configs(config_dir)


def get_config(config_dir=None):
    return ConfigLoader(config_dir)
