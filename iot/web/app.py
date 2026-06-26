from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO, emit
from core.device import DeviceManager
from core.audio import AudioRouter, AIVoicePlayer, TriggerSoundPlayer
from core.network import NetworkServer
from core.ota_manager import OTAManager
from common.logger import get_logger
from common.database_manager import get_database_manager
from common.license_verifier import LicenseVerifier
from web.gift_config import GiftConfigManager
import socket
import json
import time
import os
import hashlib
import configparser
import zipfile
import io
from werkzeug.utils import secure_filename
from configparser import ConfigParser
import pymysql
import sqlite3
from datetime import datetime
import sys
import subprocess

# 尝试导入路径助手
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'iot_pc'))
    from utils.path_helper import PathHelper
    HAS_PATH_HELPER = True
except ImportError:
    HAS_PATH_HELPER = False

# 添加ai目录到Python路径，用于导入语音复刻服务
if getattr(sys, 'frozen', False):
    # 打包后的环境
    base_path = os.path.dirname(sys.executable)
    ai_path = os.path.join(base_path, '_internal', 'ai')
else:
    # 开发环境
    ai_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'ai')

if os.path.exists(ai_path) and ai_path not in sys.path:
    sys.path.insert(0, ai_path)
    print(f"已添加 AI 模块路径: {ai_path}")

try:
    # 先尝试从 ai.aiwav 导入（标准包结构）
    from ai.aiwav.voice_cloning import VoiceCloningService
    HAS_VOICE_CLONING = True
except ImportError:
    try:
        # 再尝试从 aiwav 导入（兼容旧结构）
        from aiwav.voice_cloning import VoiceCloningService
        HAS_VOICE_CLONING = True
    except ImportError as e:
        print(f"VoiceCloningService 导入失败: {e}")
        HAS_VOICE_CLONING = False

# 添加trigger目录到Python路径
trigger_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'trigger')
sys.path.insert(0, trigger_path)
from trigger.room_worker_manager import RoomWorkerManager

class WebApp:
    def __init__(self):
        self.logger = get_logger()
        self.config = get_database_manager()
        self.config.reload()
        self.license_id = self._get_license_id()

        server_config = self.config.get_server_config()
        
        self.app = Flask(__name__, 
                        template_folder='templates',
                        static_folder='static')
        self.app.config['SECRET_KEY'] = server_config.get('secret_key', 'dev-secret-key')
        self.app.config['TEMPLATES_AUTO_RELOAD'] = True
        self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        self.app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size
        
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)
        
        self.device_manager = DeviceManager()
        self.device_manager.set_socketio(self.socketio)
        self.audio_router = AudioRouter(self.device_manager, self.socketio)
        self.ai_voice_player = AIVoicePlayer(self.audio_router, self.device_manager, self.socketio)
        self.trigger_sound_player = TriggerSoundPlayer(self.audio_router, self.device_manager)
        self.network_server = NetworkServer()
        
        self.audio_upload_dir = os.path.join(os.path.dirname(__file__), 'static', 'audio')
        self.audio_metadata_file = os.path.join(os.path.dirname(__file__), 'static', 'audio', 'metadata.json')
        self.allowed_extensions = {'wav'}
        self._ensure_audio_directory()
        self._load_audio_metadata()
        
        self.server_host = '0.0.0.0'
        self.server_port = 5000
        
        self.raspberry_pi_ip = self._load_raspberry_pi_ip()
        self.logger.info(f"初始化本机IP: {self.raspberry_pi_ip}")
        
        # 初始化礼物配置管理器
        try:
            self.gift_config_manager = GiftConfigManager()
            self.logger.info("礼物配置管理器初始化完成")
        except Exception as e:
            self.logger.error(f"礼物配置管理器初始化失败: {e}")
            self.gift_config_manager = None
        
        try:
            self.room_worker_manager = RoomWorkerManager()
            self.room_worker_manager.configure(
                device_manager=self.device_manager,
                trigger_sound_player=self.trigger_sound_player,
                socketio=self.socketio,
                db_manager=self.config
            )
            self.logger.info("RoomWorkerManager初始化完成")
        except Exception as e:
            self.logger.error(f"RoomWorkerManager初始化失败: {e}")
            self.room_worker_manager = None
        self.ai_manager = None

        try:
            from trigger.ws_message_receiver import WSMessageReceiver
            self.ws_message_receiver = WSMessageReceiver()
            self.ws_message_receiver.configure(
                db_manager=self.config,
                ws_url="ws://localhost:8888",
                on_data_flushed=self._on_ws_data_flushed,
                config=self.config
            )
            self.logger.info("WSMessageReceiver初始化完成")
        except Exception as e:
            self.logger.error(f"WSMessageReceiver初始化失败: {e}")
            self.ws_message_receiver = None
        
        # 初始化语音复刻服务
        self.voice_cloning_service = self._init_voice_cloning_service()
        
        # 初始化OTA管理器
        try:
            self.ota_manager = OTAManager(os.path.join(os.path.dirname(__file__), '..', '..', 'firmware'))
            self.logger.info("OTA管理器初始化完成")
        except Exception as e:
            self.logger.error(f"OTA管理器初始化失败: {e}")
            self.ota_manager = None
        
        self._setup_routes()
        self._setup_socketio()
        self._setup_network_handlers()
    
    def _init_voice_cloning_service(self):
        """初始化语音复刻服务"""
        if not HAS_VOICE_CLONING:
            self.logger.warning("语音复刻服务不可用: VoiceCloningService 导入失败")
            return None
        
        try:
            # 从 config.ini 创建语音复刻服务
            config_ini_path = self._find_config_ini()
            self.logger.info(f"尝试从配置文件初始化语音复刻服务: {config_ini_path}")
            
            if not os.path.exists(config_ini_path):
                self.logger.error(f"配置文件不存在: {config_ini_path}")
                return None
            
            config = ConfigParser()
            config.read(config_ini_path, encoding='utf-8')
            
            if not config.has_section('aiwav'):
                self.logger.error("配置文件中缺少 [aiwav] 节点")
                return None
            
            service = VoiceCloningService.from_config_parser(config)
            
            if service and service.is_enabled():
                self.logger.info("语音复刻服务初始化成功")
            else:
                self.logger.warning("语音复刻服务初始化成功但未启用，请检查配置")
            
            return service
            
        except Exception as e:
            self.logger.error(f"语音复刻服务初始化失败: {e}", exc_info=True)
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def get_ai_voice_player(self):
        return self.ai_voice_player
    
    @staticmethod
    def _parse_viewer_count(text: str):
        if not text:
            return None
        text = text.strip()
        import re
        m = re.match(r'(\d+(?:\.\d+)?)\s*万\+', text)
        if m:
            return int(float(m.group(1)) * 10000)
        m = re.match(r'(\d+(?:\.\d+)?)\s*万人?', text)
        if m:
            return int(float(m.group(1)) * 10000)
        m = re.search(r'\d+(?:\.\d+)?', text)
        if m:
            return int(float(m.group(0)))
        return None

    def _on_ws_data_flushed(self, flushed_data: dict):
        try:
            for room_id, data in flushed_data.items():
                # 检查房间是否已关闭
                room = self.device_manager.rooms.get(room_id)
                if room and not room.enabled:
                    continue

                gifts = data.get('gifts', [])
                messages = data.get('messages', [])
                stats = data.get('stats', [])

                if gifts:
                    gift_list = []
                    for item in gifts:
                        d = item['data']
                        gift_list.append({
                            'id': d.get('db_id', 0),
                            'type': d.get('type', 'gif'),
                            'nickname': d.get('nickname', ''),
                            'content': d.get('content', ''),
                            'gift_name': d.get('gift_name', ''),
                            'gift_count': d.get('gift_count', 0),
                            'gift_price': d.get('gift_price', 0),
                            'created_at': d.get('created_at', ''),
                            'room_id': room_id
                        })
                    self.socketio.emit('new_gifts', {
                        'room_id': room_id,
                        'gifts': gift_list
                    })

                    if self.room_worker_manager:
                        try:
                            worker = self.room_worker_manager.workers.get(room_id)
                            if worker:
                                worker.notify_new_gifts()
                        except Exception:
                            pass

                    if self.ai_manager:
                        try:
                            self.ai_manager.notify_new_gifts()
                        except Exception:
                            pass

                if messages:
                    msg_list = []
                    for item in messages:
                        d = item['data']
                        msg_list.append({
                            'id': d.get('db_id', 0),
                            'type': d.get('type', 'msg'),
                            'nickname': d.get('nickname', ''),
                            'content': d.get('content', ''),
                            'created_at': d.get('created_at', ''),
                            'room_id': room_id
                        })
                    self.socketio.emit('new_messages', {
                        'room_id': room_id,
                        'messages': msg_list
                    })

                if stats:
                    for item in stats:
                        d = item['data']
                        online_count = d.get('online_count', '')
                        if online_count:
                            try:
                                count = self._parse_viewer_count(str(online_count))
                                if count is not None:
                                    rooms = self.config.get_all_rooms()
                                    for room in rooms:
                                        if room['id'] == room_id:
                                            self.socketio.emit('viewer_count_update', {
                                                'room_id': room_id,
                                                'room_ip': room.get('ip', ''),
                                                'viewer_count': count
                                            })
                                            break
                            except (ValueError, TypeError):
                                pass
        except Exception as e:
            self.logger.error(f"WS数据刷新回调失败: {e}")
    
    def _get_license_id(self):
        """获取当前机器的license_id"""
        try:
            mysql_config = {
                'host': 'YOUR_MYSQL_HOST',
                'port': 3306,
                'db': 'YOUR_MYSQL_DB',
                'user': 'YOUR_MYSQL_USER',
                'password': 'YOUR_MYSQL_PASSWORD'
            }
            
            conn = self._get_mysql_connection()
            if not conn:
                self.logger.warning("无法连接MySQL数据库，使用默认license_id=1")
                return 1
            
            # 首先尝试通过LicenseVerifier获取
            try:
                verifier = LicenseVerifier(mysql_config)
                machine_code = verifier.get_machine_code()
                
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM license WHERE machine_code = %s AND status = 1", (machine_code,))
                    result = cursor.fetchone()
                    if result:
                        self.logger.info(f"通过机器码获取到license_id: {result['id']}")
                        return result['id']
            except Exception as e:
                self.logger.warning(f"通过机器码获取license_id失败: {e}")
            
            # 如果失败，尝试返回第一个可用的license_id
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM license WHERE status = 1 ORDER BY id LIMIT 1")
                result = cursor.fetchone()
                if result:
                    self.logger.info(f"使用第一个可用license_id: {result['id']}")
                    return result['id']
            
            # 如果还是失败，返回默认值1
            self.logger.warning("未找到可用license，使用默认license_id=1")
            return 1
        except Exception as e:
            self.logger.warning(f"获取license_id失败: {e}，使用默认license_id=1")
            return 1

    def _ensure_audio_directory(self):
        if not os.path.exists(self.audio_upload_dir):
            os.makedirs(self.audio_upload_dir)
            self.logger.info(f"创建音频目录: {self.audio_upload_dir}")

    def _allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def _generate_secure_filename(self, original_filename):
        ext = os.path.splitext(original_filename)[1]
        timestamp = str(int(time.time()))
        md5_hash = hashlib.md5(original_filename.encode('utf-8')).hexdigest()[:8]
        return f"{md5_hash}_{timestamp}{ext}"

    def _load_audio_metadata(self):
        try:
            if os.path.exists(self.audio_metadata_file):
                with open(self.audio_metadata_file, 'r', encoding='utf-8') as f:
                    self.audio_metadata = json.load(f)
            else:
                self.audio_metadata = {}
            self.logger.info(f"加载音频元数据: {len(self.audio_metadata)} 条记录")
        except Exception as e:
            self.logger.error(f"加载音频元数据失败: {e}")
            self.audio_metadata = {}

    def _save_audio_metadata(self):
        try:
            with open(self.audio_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.audio_metadata, f, ensure_ascii=False, indent=2)
            self.logger.info(f"保存音频元数据: {len(self.audio_metadata)} 条记录")
        except Exception as e:
            self.logger.error(f"保存音频元数据失败: {e}")

    def _validate_wav_file(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                header = f.read(12)
                if len(header) < 12:
                    return False
                if header[:4] != b'RIFF' or header[8:12] != b'WAVE':
                    return False
            return True
        except Exception as e:
            self.logger.error(f"验证WAV文件失败: {e}")
            return False

    def _load_raspberry_pi_ip(self):
        """加载本机IP - Windows模式下使用本机IP"""
        # 检查是否有路径助手
        if HAS_PATH_HELPER:
            # PC模式：获取本机IP
            return PathHelper.get_local_ip()

        # Windows模式：默认返回localhost
        return 'localhost'

    def _load_voice_config(self):
        """加载语音配置（从voice/config.json）"""
        voice_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'voice', 'config.json')
        
        if not os.path.exists(voice_config_path):
            self.logger.warning(f"语音配置文件不存在: {voice_config_path}")
            return None
        
        try:
            with open(voice_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.logger.info(f"加载语音配置成功，当前提供商: {config.get('provider', 'unknown')}")
                return config
        except Exception as e:
            self.logger.error(f"加载语音配置失败: {e}")
            return None

    def _get_mysql_connection(self):
        """获取MySQL连接"""
        # 使用路径助手获取config.ini路径
        if HAS_PATH_HELPER:
            config_path = PathHelper.get_config_ini_path()
        else:
            config_path = 'config.ini'

        if not os.path.exists(config_path):
            self.logger.warning(f"config.ini文件不存在: {config_path}")
            return None

        try:
            config = ConfigParser()
            config.read(config_path, encoding='utf-8')
            
            db_host = 'YOUR_MYSQL_HOST'
            db_port = 3306
            db_db = 'YOUR_MYSQL_DB'
            db_user = 'YOUR_MYSQL_USER'
            db_pass = 'YOUR_MYSQL_PASSWORD'
            
            conn = pymysql.connect(
                host=db_host,
                port=db_port,
                user=db_user,
                password=db_pass,
                database=db_db,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            
            self.logger.debug(f"MySQL连接成功: {db_host}:{db_port}/{db_db}")
            return conn
            
        except Exception as e:
            self.logger.error(f"MySQL连接失败: {e}")
            return None

    def _get_full_url(self, relative_url):
        if relative_url.startswith('http://') or relative_url.startswith('https://'):
            return relative_url
        
        return f"http://{self.raspberry_pi_ip}:{self.server_port}{relative_url}"

    def _get_db_path(self):
        """获取数据库路径"""
        # 检查是否有路径助手
        if HAS_PATH_HELPER:
            return PathHelper.get_config_db_path()

        # Windows模式
        return os.path.join(os.path.dirname(__file__), '..', 'config', 'config.db')

    def _find_config_ini(self):
        """查找config.ini文件路径"""
        # 检查是否有路径助手
        if HAS_PATH_HELPER:
            return PathHelper.get_config_ini_path()

        # Windows模式 - 检查项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(current_dir, '..', '..', 'config.ini'),
            os.path.join(current_dir, '..', 'config.ini'),
            'config.ini'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        
        return 'config.ini'  # 默认返回项目根目录

    def _setup_routes(self):
        @self.app.route('/favicon.ico')
        def favicon():
            return '', 204

        @self.app.route('/')
        def index():
            config_path = self._find_config_ini()
            version = '1.0.0'
            system_name = '规模化直播矩阵系统'
            try:
                config = ConfigParser()
                config.read(config_path, encoding='utf-8')
                version = config.get('system', 'version', fallback='1.0.0')
                version = version.split('#')[0].strip()
                system_name = config.get('system', 'name', fallback='规模化直播矩阵系统')
            except Exception as e:
                self.logger.error(f"读取配置失败: {e}")
            return render_template('control_panel.html', version=version, system_name=system_name, now=int(time.time()), license_id=self.license_id or 0)

        @self.app.route('/api/rooms')
        def get_rooms():
            rooms = self.device_manager.get_all_rooms()
            for room in rooms:
                room_id = room['id']
                db_path = self.config.get_room_db_path(room_id)
                if db_path and os.path.exists(db_path):
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT online_count, created_at FROM room_stats
                            ORDER BY created_at DESC LIMIT 1
                        """)
                        row = cursor.fetchone()
                        conn.close()
                        if row and row['online_count'] and row['created_at']:
                            try:
                                stats_time = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S')
                                if (datetime.now() - stats_time).total_seconds() <= 60:
                                    parsed = self._parse_viewer_count(str(row['online_count']))
                                    if parsed is not None:
                                        room['viewer_count'] = parsed
                            except (ValueError, TypeError):
                                pass
                    except Exception:
                        pass
            return jsonify({'rooms': rooms})

        @self.app.route('/api/rooms/<int:room_id>')
        def get_room(room_id):
            room = self.device_manager.get_room(room_id)
            if room:
                return jsonify(room)
            return jsonify({'error': 'Room not found'}), 404

        @self.app.route('/api/rooms/<int:room_id>/enabled', methods=['POST'])
        def set_room_enabled(room_id):
            """设置房间启用/关闭状态"""
            try:
                data = request.get_json()
                enabled = data.get('enabled', True)
                
                # 1. 更新数据库
                self.config.update_room(room_id, enabled=1 if enabled else 0)
                
                # 2. 更新内存中的Room对象
                room = self.device_manager.rooms.get(room_id)
                if room:
                    room.enabled = enabled
                    # 如果关闭房间，强制设为离线状态
                    if not enabled:
                        room.online = False
                
                # 3. 如果关闭，停止该房间的Worker
                if not enabled and self.room_worker_manager:
                    self.room_worker_manager.stop_room(room_id)
                
                # 4. 如果启用，启动该房间的Worker
                if enabled and self.room_worker_manager:
                    room_data = self.config.get_room(room_id)
                    if room_data and room_data.get('ip'):
                        self.room_worker_manager.start_room(room_id, room_data['ip'], room_data.get('port', 8080))
                
                # 5. 推送状态更新到前端
                if self.socketio:
                    self.socketio.emit('room_status_update', {
                        'room_id': room_id,
                        'online': room.online if room else False,
                        'enabled': enabled,
                        'rssi': room.rssi if room else -100,
                        'last_seen': room.last_seen if room else None
                    }, namespace='/')
                
                self.logger.info(f"房间{room_id}启用状态已更新: enabled={enabled}")
                return jsonify({'success': True, 'enabled': enabled})
                
            except Exception as e:
                self.logger.error(f"设置房间启用状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/devices')
        def get_room_devices(room_id):
            devices = self.device_manager.get_room_devices(room_id)
            if devices:
                return jsonify({'devices': devices})
            return jsonify({'error': 'Room not found'}), 404

        @self.app.route('/api/rooms/<int:room_id>/voice_prompt', methods=['GET', 'POST'])
        def room_voice_prompt(room_id):
            """获取或设置房间专属AI语音提示词 - 从远程MySQL表获取"""
            try:
                # 获取房间IP
                room = self.device_manager.get_room(room_id)
                if not room:
                    return jsonify({'voice_prompt': ''}), 404
                
                room_ip = room.get('ip', '')
                if not room_ip:
                    return jsonify({'voice_prompt': ''}), 404
                
                if request.method == 'GET':
                    # 从远程API获取AI提示词
                    import requests
                    response = requests.get(f'https://live.hzjt.com/api/upload_voice.php?action=get&room={room_ip}&license_id={self.license_id or 0}')
                    result = response.json()
                    
                    if result.get('code') == 0 and result.get('data'):
                        ai_prompt = result['data'].get('ai_prompt', '')
                        return jsonify({'voice_prompt': ai_prompt})
                    return jsonify({'voice_prompt': ''})
                
                elif request.method == 'POST':
                    # 设置AI提示词到远程API
                    data = request.get_json()
                    ai_prompt = data.get('voice_prompt', '')
                    
                    import requests
                    response = requests.post(
                        'https://live.hzjt.com/api/upload_voice.php?action=update_ai_prompt',
                        json={'room': room_ip, 'license_id': self.license_id or 0, 'ai_prompt': ai_prompt}
                    )
                    result = response.json()
                    
                    if result.get('code') == 0:
                        self.logger.info(f"更新房间{room_id}的AI提示词成功")
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': result.get('msg', '更新失败')}), 500
            
            except Exception as e:
                self.logger.error(f"处理房间AI提示词失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/voice_status', methods=['GET', 'POST'])
        def room_voice_status(room_id):
            """获取或设置房间AI语音回复状态 - 从远程MySQL表获取"""
            try:
                # 获取房间IP
                room = self.device_manager.get_room(room_id)
                if not room:
                    return jsonify({'voice_status': False}), 404
                
                room_ip = room.get('ip', '')
                if not room_ip:
                    return jsonify({'voice_status': False}), 404
                
                if request.method == 'GET':
                    # 从远程API获取语音状态
                    import requests
                    response = requests.get(f'https://live.hzjt.com/api/upload_voice.php?action=get&room={room_ip}&license_id={self.license_id or 0}')
                    result = response.json()
                    
                    if result.get('code') == 0 and result.get('data'):
                        voice_status = result['data'].get('voice_status', 0)
                        return jsonify({'voice_status': bool(voice_status)})
                    return jsonify({'voice_status': False})
                
                elif request.method == 'POST':
                    data = request.get_json()
                    voice_status = data.get('voice_status', False)
                    
                    import requests
                    
                    get_resp = requests.get(f'https://live.hzjt.com/api/upload_voice.php?action=get&room={room_ip}&license_id={self.license_id or 0}')
                    get_result = get_resp.json()
                    current_voice_id = None
                    if get_result.get('code') == 0 and get_result.get('data'):
                        current_voice_id = get_result['data'].get('voice_id')
                    
                    update_data = {
                        'room': room_ip,
                        'license_id': self.license_id or 0,
                        'voice_status': 2 if voice_status else 0
                    }
                    if current_voice_id:
                        update_data['voice_id'] = current_voice_id
                    
                    response = requests.post(
                        'https://live.hzjt.com/api/upload_voice.php?action=update_voice_id',
                        json=update_data
                    )
                    result = response.json()
                    
                    if result.get('code') == 0:
                        self.logger.info(f"更新房间{room_id}的AI语音回复状态: {voice_status}")
                        self.device_manager.set_room_voice_status(room_id, voice_status)

                        if self.ai_manager:
                            if voice_status:
                                self.ai_manager.refresh_room_config(room_ip)
                                self.ai_manager.notify_new_gifts()
                            else:
                                self.ai_manager.cancel_room_tasks(room_ip)

                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': result.get('msg', '更新失败')}), 500
            
            except Exception as e:
                self.logger.error(f"处理房间语音状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/live_url', methods=['GET', 'POST'])
        def room_live_url(room_id):
            """获取或设置房间直播地址"""
            try:
                if request.method == 'GET':
                    # 获取房间直播地址
                    rooms = self.config.get_all_rooms()
                    room = next((r for r in rooms if r['id'] == room_id), None)

                    if room:
                        return jsonify({
                            'live_url': room.get('live_url', '')
                        })
                    return jsonify({'error': 'Room not found'}), 404

                elif request.method == 'POST':
                    # 设置房间直播地址
                    data = request.get_json()
                    live_url = data.get('live_url', '')

                    # 更新数据库中的房间直播地址
                    self.config.update_room(room_id, live_url=live_url)

                    self.logger.info(f"更新房间{room_id}的直播地址")
                    return jsonify({'success': True})

            except Exception as e:
                self.logger.error(f"处理房间直播地址失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/interaction_monitor', methods=['POST'])
        def toggle_interaction_monitor(room_id):
            """启动或停止房间互动监控 - 已改为本地WebSocket接收，此接口保留UI兼容"""
            try:
                data = request.get_json()
                enabled = data.get('enabled', False)
                action_text = '启动' if enabled else '停止'
                self.logger.info(f"房间{room_id} {action_text}互动监控（本地模式，无需远程命令）")
                return jsonify({'success': True, 'enabled': enabled})
            except Exception as e:
                self.logger.error(f"切换互动监控失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/collector_status', methods=['GET'])
        def get_collector_status(room_id):
            """获取采集器状态 - 从本地SQLite检查最近消息"""
            try:
                db_path = self.config.get_room_db_path(room_id)
                if not db_path:
                    return jsonify({'success': False, 'error': f'房间{room_id}数据库不存在'}), 404

                ws_running = False
                ws_message_count = 0
                if self.ws_message_receiver:
                    ws_running = self.ws_message_receiver.running
                    ws_message_count = self.ws_message_receiver.message_count

                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                try:
                    cursor.execute("""
                        SELECT COUNT(*) as count, MAX(created_at) as last_time
                        FROM messages
                        WHERE created_at >= datetime('now', 'localtime', '-30 seconds')
                    """)
                    msg_result = cursor.fetchone()

                    cursor.execute("""
                        SELECT COUNT(*) as count, MAX(created_at) as last_time
                        FROM gifts
                        WHERE created_at >= datetime('now', 'localtime', '-30 seconds')
                    """)
                    gift_result = cursor.fetchone()

                    msg_count = msg_result['count'] if msg_result else 0
                    gift_count = gift_result['count'] if gift_result else 0
                    total_count = msg_count + gift_count

                    last_msg_time = msg_result['last_time'] if msg_result and msg_result['last_time'] else None
                    last_gift_time = gift_result['last_time'] if gift_result and gift_result['last_time'] else None
                    last_time = max(last_msg_time or '', last_gift_time or '') if last_msg_time or last_gift_time else None

                    return jsonify({
                        'success': True,
                        'has_messages': total_count > 0,
                        'message_count': total_count,
                        'last_message_time': last_time,
                        'ws_receiver_running': ws_running,
                        'ws_total_messages': ws_message_count
                    })
                finally:
                    conn.close()

            except Exception as e:
                self.logger.error(f"获取采集器状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/voice', methods=['GET', 'POST'])
        def room_voice(room_id):
            """获取或设置房间语音配置 - 从远程MySQL表获取"""
            try:
                # 获取房间IP
                room = self.device_manager.get_room(room_id)
                if not room:
                    return jsonify({'error': 'Room not found'}), 404
                
                room_ip = room.get('ip', '')
                if not room_ip:
                    return jsonify({'error': 'Room IP not configured'}), 400
                
                if request.method == 'GET':
                    # 从远程API获取语音配置
                    import requests
                    response = requests.get(f'https://live.hzjt.com/api/upload_voice.php?action=get&room={room_ip}&license_id={self.license_id or 0}')
                    result = response.json()
                    
                    if result.get('code') == 0 and result.get('data'):
                        voice_data = result['data']
                        return jsonify({
                            'voice_sample': voice_data.get('voice_sample', ''),
                            'voice_id': voice_data.get('voice_id', '')
                        })
                    return jsonify({
                        'voice_sample': '',
                        'voice_id': ''
                    })
                
                elif request.method == 'POST':
                    # 设置语音配置到远程API
                    data = request.get_json()
                    voice_sample = data.get('voice_sample', '')
                    voice_id = data.get('voice_id', '')
                    
                    import requests
                    # 先获取现有数据
                    get_response = requests.get(f'https://live.hzjt.com/api/upload_voice.php?action=get&room={room_ip}&license_id={self.license_id or 0}')
                    get_result = get_response.json()
                    
                    existing_data = get_result.get('data', {}) if get_result.get('code') == 0 else {}
                    
                    # 调用update_ai_prompt来更新（这个接口可以更新多个字段）
                    response = requests.post(
                        'https://live.hzjt.com/api/upload_voice.php?action=update_ai_prompt',
                        json={
                            'room': room_ip, 
                            'license_id': self.license_id or 0,
                            'ai_prompt': existing_data.get('ai_prompt', ''),
                            'voice_text': existing_data.get('voice_text', ''),
                            'voice_prompt': existing_data.get('voice_prompt', '')
                        }
                    )
                    result = response.json()
                    
                    # 如果有voice_id，单独更新
                    if voice_id:
                        requests.post(
                            'https://live.hzjt.com/api/upload_voice.php?action=update_voice_id',
                            json={'room': room_ip, 'license_id': self.license_id or 0, 'voice_id': voice_id, 'voice_status': 2}
                        )
                    
                    if result.get('code') == 0:
                        self.logger.info(f"更新房间{room_id}的语音配置")
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': result.get('msg', '更新失败')}), 500
            
            except Exception as e:
                self.logger.error(f"处理房间语音配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/voice/upload', methods=['POST'])
        def upload_voice_sample(room_id):
            """上传房间语音样本文件 - 上传到远程服务器"""
            try:
                if 'file' not in request.files:
                    return jsonify({'success': False, 'error': 'No file part'}), 400
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'success': False, 'error': 'No selected file'}), 400
                
                # 获取房间IP
                room = self.device_manager.get_room(room_id)
                if not room:
                    return jsonify({'error': 'Room not found'}), 404
                
                room_ip = room.get('ip', '')
                if not room_ip:
                    return jsonify({'error': 'Room IP not configured'}), 400
                
                # 准备上传到远程API
                import requests
                
                files = {'file': (file.filename, file.stream, file.content_type)}
                data = {
                    'room': room_ip,
                    'license_id': self.license_id or 0
                }
                
                # 上传到远程API
                response = requests.post(
                    'https://live.hzjt.com/api/upload_voice.php?action=upload',
                    files=files,
                    data=data
                )
                result = response.json()
                
                if result.get('code') == 0:
                    self.logger.info(f"房间{room_id}上传语音样本成功")
                    return jsonify({
                        'success': True,
                        'data': result.get('data', {})
                    })
                else:
                    return jsonify({'success': False, 'error': result.get('msg', '上传失败')}), 500
            
            except Exception as e:
                self.logger.error(f"上传语音样本失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/voice/clone', methods=['POST'])
        def clone_voice(room_id):
            """克隆房间语音 - 已弃用，请使用 /api/rooms/<room_id>/voice_clone"""
            return jsonify({
                'success': False,
                'error': '此接口已弃用，请使用 /api/rooms/<room_id>/voice_clone'
            }), 410

        @self.app.route('/api/rooms/<int:room_id>/voice_clone', methods=['POST'])
        def voice_clone_cosyvoice(room_id):
            """使用阿里云百炼CosyVoice进行语音复刻"""
            try:
                # 检查语音复刻服务是否可用
                if not self.voice_cloning_service:
                    return jsonify({'success': False, 'error': '语音复刻服务未初始化'}), 500
                
                if not self.voice_cloning_service.is_enabled():
                    return jsonify({'success': False, 'error': '语音复刻服务未启用'}), 500
                
                data = request.get_json() or {}
                room_ip = data.get('room', '')
                
                if not room_ip:
                    room = self.device_manager.get_room(room_id)
                    if room:
                        room_ip = room.get('ip', '')
                
                if not room_ip:
                    return jsonify({'success': False, 'error': '房间IP未配置'}), 400
                
                import requests
                response = requests.get(f'https://live.hzjt.com/api/upload_voice.php?action=get&room={room_ip}&license_id={self.license_id or 0}')
                result = response.json()
                
                if result.get('code') != 0 or not result.get('data'):
                    return jsonify({'success': False, 'error': '请先上传音频样本'}), 400
                
                voice_data = result['data']
                audio_url = voice_data.get('voice_sample_url')
                
                if not audio_url:
                    return jsonify({'success': False, 'error': '请先上传音频样本'}), 400
                
                requests.post('https://live.hzjt.com/api/upload_voice.php?action=update_voice_id', 
                    json={'room': room_ip, 'license_id': self.license_id or 0, 'voice_status': 1})
                
                # 使用语音复刻服务
                voice_id = self.voice_cloning_service.create_voice(
                    prefix=f'room{room_id}',
                    audio_url=audio_url
                )
                
                if voice_id:
                    requests.post('https://live.hzjt.com/api/upload_voice.php?action=update_voice_id', 
                        json={'room': room_ip, 'license_id': self.license_id or 0, 'voice_id': voice_id, 'voice_status': 2})
                    
                    self.logger.info(f"房间{room_id}语音复刻成功: {voice_id}")
                    return jsonify({
                        'success': True,
                        'voice_id': voice_id
                    })
                else:
                    requests.post('https://live.hzjt.com/api/upload_voice.php?action=update_voice_id', 
                        json={'room': room_ip, 'license_id': self.license_id or 0, 'voice_status': 3, 'voice_error': '复刻返回空ID'})
                    
                    return jsonify({'success': False, 'error': '语音复刻失败，返回空ID'}), 500
            
            except Exception as e:
                self.logger.error(f"语音复刻失败: {e}")
                try:
                    data = request.get_json() or {}
                    room_ip = data.get('room', '')
                    if room_ip:
                        import requests
                        requests.post('https://live.hzjt.com/api/upload_voice.php?action=update_voice_id', 
                            json={'room': room_ip, 'license_id': self.license_id or 0, 'voice_status': 3, 'voice_error': str(e)[:500]})
                except:
                    pass
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/upload_voice.php', methods=['GET', 'POST', 'OPTIONS'])
        def upload_voice():
            if request.method == 'OPTIONS':
                return '', 200
            
            action = request.args.get('action', '')
            remote_base = 'https://live.hzjt.com/api/upload_voice.php'
            
            try:
                import requests as req
                
                if action == 'get':
                    resp = req.get(f'{remote_base}?action=get&room={request.args.get("room", "")}&license_id={request.args.get("license_id", self.license_id or 0)}')
                    return jsonify(resp.json())
                
                elif action == 'upload':
                    room = request.form.get('room', '')
                    if not room:
                        return jsonify({'code': 400, 'msg': '房间参数错误'}), 400
                    
                    if 'file' not in request.files:
                        return jsonify({'code': 400, 'msg': '文件上传失败'}), 400
                    
                    file = request.files['file']
                    if file.filename == '':
                        return jsonify({'code': 400, 'msg': '文件上传失败'}), 400
                    
                    files = {'file': (file.filename, file.stream, file.content_type)}
                    data = {
                        'room': room,
                        'license_id': request.form.get('license_id', self.license_id or 0),
                        'voice_text': request.form.get('voice_text', ''),
                        'voice_prompt': request.form.get('voice_prompt', ''),
                        'ai_prompt': request.form.get('ai_prompt', '')
                    }
                    
                    resp = req.post(f'{remote_base}?action=upload', files=files, data=data)
                    return jsonify(resp.json())
                
                elif action == 'update_ai_prompt':
                    data = request.get_json() or {}
                    data['license_id'] = data.get('license_id', self.license_id or 0)
                    resp = req.post(f'{remote_base}?action=update_ai_prompt', json=data)
                    return jsonify(resp.json())
                
                elif action == 'update_ai_thank':
                    data = request.get_json() or {}
                    data['license_id'] = data.get('license_id', self.license_id or 0)
                    resp = req.post(f'{remote_base}?action=update_ai_thank', json=data)
                    return jsonify(resp.json())
                
                elif action == 'update_voice_id':
                    data = request.get_json() or {}
                    data['license_id'] = data.get('license_id', self.license_id or 0)
                    resp = req.post(f'{remote_base}?action=update_voice_id', json=data)
                    return jsonify(resp.json())
                
                return jsonify({'code': 404, 'msg': '接口不存在'}), 404
            except Exception as e:
                self.logger.error(f"API代理错误: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                return jsonify({'code': 500, 'msg': str(e)}), 500

        @self.app.route('/sound/<path:filename>')
        def serve_sound_file(filename):
            """提供sound目录下的文件访问"""
            from flask import send_from_directory
            import sys
            
            if getattr(sys, 'frozen', False):
                # 打包后的exe模式
                sound_dir = os.path.join(os.path.dirname(sys.executable), 'sound')
            else:
                # 开发模式
                sound_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'sound')
            
            return send_from_directory(sound_dir, filename)

        @self.app.route('/api/rooms/<int:room_id>/all_devices')
        def get_room_all_devices(room_id):
            room = self.device_manager.get_room_with_all_devices(room_id)
            if room:
                return jsonify(room)
            return jsonify({'error': 'Room not found'}), 404

        @self.app.route('/api/control/<int:room_id>/<device_name>/<action>', methods=['POST'])
        def control_device(room_id, device_name, action):
            success = self.device_manager.control_device(room_id, device_name, action)
            if success:
                return jsonify({'success': True})
            return jsonify({'success': False, 'error': 'Control failed'}), 500

        @self.app.route('/api/rooms/<int:room_id>/prog_devices', methods=['POST'])
        def save_prog_devices(room_id):
            data = request.get_json()
            
            try:
                room = self.device_manager.get_room_with_all_devices(room_id)
                if not room:
                    return jsonify({'success': False, 'error': 'Room not found'}), 404
                
                room_db_path = self.config.get_room_db_path(room_id)
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # 更新设备配置 - 直接操作数据库，避免多次reload
                for device in room.get('devices', []):
                    device_name = device.get('name', '')
                    if device_name.startswith('prog') and device_name in data:
                        device_config = data[device_name]
                        device_id = device.get('id')
                        is_enabled = device_config.get('enabled', device.get('enabled', False))
                        
                        # 直接更新数据库中的设备配置
                        # 【关键修复】如果设备未启用，清空gift_event字段
                        gift_event_value = device_config.get('gift_event', device.get('gift_event', '')) if is_enabled else ''
                        trigger_sound_value = device_config.get('trigger_sound', device.get('trigger_sound', False))
                        
                        cursor.execute(
                            """UPDATE devices 
                               SET label = ?, enabled = ?, trigger_on_duration = ?, 
                                   trigger_off_duration = ?, gift_event = ?, trigger_sound = ?, updated_at = CURRENT_TIMESTAMP
                               WHERE id = ?""",
                            (
                                device_config.get('label', device.get('label', '')),
                                1 if is_enabled else 0,
                                device_config.get('trigger_on_duration', device.get('trigger_on_duration', 3)),
                                device_config.get('trigger_off_duration', device.get('trigger_off_duration', 0)),
                                gift_event_value,
                                1 if trigger_sound_value else 0,
                                device_id
                            )
                        )
                        
                        # 【关键修复】如果设备未启用，删除该设备的所有礼物触发配置
                        if not is_enabled:
                            cursor.execute(
                                "SELECT id, device_config FROM gift_triggers WHERE room_id = ? AND device_type = 'programmable'",
                                (room_id,)
                            )
                            for row in cursor.fetchall():
                                stored_gift_id = row[0]
                                stored_config_str = row[1]
                                if stored_config_str:
                                    try:
                                        stored_config = json.loads(stored_config_str)
                                        if stored_config.get('device_name') == device_name:
                                            # 删除该设备的礼物配置
                                            cursor.execute(
                                                "DELETE FROM gift_triggers WHERE id = ?",
                                                (stored_gift_id,)
                                            )
                                    except:
                                        pass
                            # 跳过礼物配置的保存
                            continue
                        
                        # 处理礼物触发配置（只有启用的设备才处理）
                        gift_event = device_config.get('gift_event', '')
                        if gift_event:
                            # 构建设备配置 JSON
                            device_config_json = {
                                'device_name': device_name,
                                'trigger_on_duration': device_config.get('trigger_on_duration', 3),
                                'trigger_off_duration': device_config.get('trigger_off_duration', 0)
                            }
                            import json
                            device_config_str = json.dumps(device_config_json)
                            
                            # 【关键修复】先删除该设备的所有旧配置，确保一个设备只有一个礼物配置
                            cursor.execute(
                                "SELECT id, device_config FROM gift_triggers WHERE room_id = ? AND device_type = 'programmable'",
                                (room_id,)
                            )
                            for row in cursor.fetchall():
                                stored_gift_id = row[0]
                                stored_config_str = row[1]
                                if stored_config_str:
                                    try:
                                        stored_config = json.loads(stored_config_str)
                                        if stored_config.get('device_name') == device_name:
                                            # 删除该设备的所有旧配置
                                            cursor.execute(
                                                "DELETE FROM gift_triggers WHERE id = ?",
                                                (stored_gift_id,)
                                            )
                                    except:
                                        pass
                            
                            # 检查礼物是否已被其他设备使用
                            cursor.execute(
                                "SELECT id, device_config FROM gift_triggers WHERE room_id = ? AND gift_name = ?",
                                (room_id, gift_event)
                            )
                            existing = cursor.fetchone()
                            
                            if existing:
                                # 如果礼物已被其他设备使用，先删除旧配置
                                cursor.execute(
                                    "DELETE FROM gift_triggers WHERE id = ?",
                                    (existing[0],)
                                )
                            
                            # 插入新配置
                            cursor.execute(
                                "INSERT INTO gift_triggers (room_id, gift_name, trigger_count, device_type, device_config) VALUES (?, ?, 1, ?, ?)",
                                (room_id, gift_event, 'programmable', device_config_str)
                            )
                        else:
                            # 如果没有选择礼物事件，删除该设备相关的礼物配置
                            cursor.execute(
                                "SELECT id, device_config FROM gift_triggers WHERE room_id = ? AND device_type = 'programmable'",
                                (room_id,)
                            )
                            for row in cursor.fetchall():
                                stored_gift_id = row[0]
                                stored_config_str = row[1]
                                if stored_config_str:
                                    try:
                                        stored_config = json.loads(stored_config_str)
                                        if stored_config.get('device_name') == device_name:
                                            # 删除该礼物配置
                                            cursor.execute(
                                                "DELETE FROM gift_triggers WHERE id = ?",
                                                (stored_gift_id,)
                                            )
                                    except:
                                        pass
                
                conn.commit()
                conn.close()
                
                # 只重新加载一次配置
                self.device_manager.reload_rooms()
                
                return jsonify({'success': True})
            except Exception as e:
                import traceback
                self.logger.error(f"保存可编程设备配置失败: {e}\n{traceback.format_exc()}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/trigger/<int:device_id>/add', methods=['POST'])
        def add_trigger(device_id):
            """添加触发任务"""
            if not self.room_worker_manager:
                return jsonify({'success': False, 'error': 'RoomWorkerManager not available'}), 500
            
            data = request.get_json()
            count = data.get('count', 1)
            
            try:
                room_id = self.config.get_room_id_by_device_id(device_id)
                if room_id is None:
                    return jsonify({'success': False, 'error': 'Device not found'}), 404
                self.room_worker_manager.add_trigger(room_id, device_id, count)
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"添加触发任务失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/trigger/<int:device_id>/clear', methods=['POST'])
        def clear_trigger(device_id):
            """清空触发任务"""
            if not self.room_worker_manager:
                return jsonify({'success': False, 'error': 'RoomWorkerManager not available'}), 500
            
            try:
                room_id = self.config.get_room_id_by_device_id(device_id)
                if room_id is None:
                    return jsonify({'success': False, 'error': 'Device not found'}), 404
                self.room_worker_manager.clear_trigger(room_id, device_id)
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"清空触发任务失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/trigger/<int:device_id>/status')
        def get_trigger_status(device_id):
            """获取获取触发状态"""
            if not self.room_worker_manager:
                return jsonify({'success': False, 'error': 'RoomWorkerManager not available'}), 500
            
            try:
                room_id = self.config.get_room_id_by_device_id(device_id)
                if room_id is None:
                    return jsonify({'success': False, 'error': 'Device not found'}), 404
                status = self.room_worker_manager.get_device_status(room_id, device_id)
                if status:
                    return jsonify({'success': True, 'status': status})
                return jsonify({'success': False, 'error': 'Device not found'}), 404
            except Exception as e:
                self.logger.error(f"获取触发状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/trigger_status')
        def get_room_trigger_status(room_id):
            """获取房间所有触发装置的状态"""
            if not self.room_worker_manager:
                return jsonify({'success': False, 'error': 'RoomWorkerManager not available'}), 500
            
            try:
                room = self.device_manager.get_room_with_all_devices(room_id)
                if not room:
                    return jsonify({'success': False, 'error': 'Room not found'}), 404
                
                trigger_devices = []
                for device in room.get('devices', []):
                    device_name = device.get('name', '')
                    if device_name == 'trigger' or (device_name.startswith('prog') and device.get('trigger_off_duration', 0) > 0):
                        status = self.room_worker_manager.get_device_status(room_id, device.get('id'))
                        if status:
                            trigger_state = status.get('trigger_state', False)
                            remaining_count = status.get('trigger_remaining_count', 0)
                            
                            display_remaining_count = remaining_count + 1 if trigger_state else remaining_count
                            
                            trigger_devices.append({
                                'id': device.get('id'),
                                'name': device_name,
                                'label': device.get('label', ''),
                                'pin': device.get('pin'),
                                'trigger_on_duration': device.get('trigger_on_duration',3),
                                'trigger_off_duration': device.get('trigger_off_duration', 0),
                                'remaining_count': display_remaining_count,
                                'state': trigger_state,
                                'last_trigger_time': status.get('last_trigger_time'),
                                'next_trigger_time': status.get('next_trigger_time')
                            })
                
                return jsonify({'success': True, 'devices': trigger_devices})
            except Exception as e:
                self.logger.error(f"获取房间触发状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<int:room_id>/trigger_logs')
        def get_room_trigger_logs(room_id):
            """获取房间礼物触发日志"""
            try:
                room_db_path = self.config.get_room_db_path(room_id)
                if room_db_path and os.path.exists(room_db_path):
                    import sqlite3
                    conn = sqlite3.connect(room_db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, device_name, gift_name, gift_count, trigger_count, 
                               original_count, remaining_count, created_at
                        FROM gift_trigger_logs
                        WHERE room_id = ?
                        ORDER BY id DESC
                        LIMIT 500
                    """, (room_id,))
                    rows = cursor.fetchall()
                    conn.close()
                else:
                    db_path = self._get_db_path()
                    import sqlite3
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, device_name, gift_name, gift_count, trigger_count, 
                               original_count, remaining_count, created_at
                        FROM gift_trigger_logs
                        WHERE room_id = ?
                        ORDER BY id DESC
                        LIMIT 500
                    """, (room_id,))
                    rows = cursor.fetchall()
                    conn.close()
                
                logs = []
                for row in rows:
                    logs.append({
                        'id': row['id'],
                        'device_name': row['device_name'],
                        'gift_name': row['gift_name'],
                        'gift_count': row['gift_count'],
                        'trigger_count': row['trigger_count'],
                        'original_count': row['original_count'],
                        'remaining_count': row['remaining_count'],
                        'created_at': row['created_at']
                    })
                
                return jsonify({'success': True, 'logs': logs})
            except Exception as e:
                self.logger.error(f"获取房间触发日志失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/audio/switch/<int:room_id>', methods=['POST'])
        def switch_audio(room_id):
            success = self.audio_router.switch_to_room(room_id)
            if success:
                self.device_manager.set_audio_active(room_id, True)
                return jsonify({'success': True, 'room_id': room_id})
            return jsonify({'success': False, 'error': 'Switch failed'}), 500

        @self.app.route('/api/audio/broadcast', methods=['POST'])
        def toggle_broadcast():
            data = request.get_json()
            enable = data.get('enable', False)
            
            if enable:
                self.audio_router.enable_broadcast()
            else:
                self.audio_router.disable_broadcast()
                
            return jsonify({'success': True, 'broadcast': enable})

        @self.app.route('/api/launch_barrage', methods=['POST'])
        def launch_barrage():
            try:
                exe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'popup', 'AiobsBarrageIdea.exe')
                if not os.path.exists(exe_path):
                    self.logger.error(f"弹幕程序不存在: {exe_path}")
                    return jsonify({'success': False, 'error': f'弹幕程序不存在: {exe_path}'}), 404
                os.startfile(exe_path)
                self.logger.info(f"弹幕程序已启动: {exe_path}")
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"启动弹幕程序失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/audio/status')
        def get_audio_status():
            return jsonify({
                'active_room': self.audio_router.get_active_room(),
                'broadcast': self.audio_router.is_broadcasting()
            })
        
        @self.app.route('/api/rooms/<int:room_id>/devices/sound_status')
        def get_room_sound_status(room_id):
            """获取房间所有设备的音效状态"""
            try:
                room = self.device_manager.get_room_with_all_devices(room_id)
                if not room:
                    return jsonify({'success': False, 'error': 'Room not found'}), 404
                
                room_obj = self.device_manager.rooms.get(room_id)
                room_online = room_obj.online if room_obj else False

                devices_sound_status = []
                for device in room.get('devices', []):
                    device_name = device.get('name', '')
                    if device_name == 'trigger' or device_name == 'always' or device_name.startswith('prog'):
                        has_sound_file = self.trigger_sound_player.sound_file_exists(room_id, device_name)
                        sound_enabled = device.get('trigger_sound', False)
                        sound_delay = device.get('trigger_sound_delay', 0)
                        
                        devices_sound_status.append({
                            'id': device.get('id'),
                            'name': device_name,
                            'label': device.get('label', ''),
                            'has_sound_file': has_sound_file,
                            'trigger_sound': sound_enabled,
                            'trigger_sound_delay': sound_delay
                        })
                
                return jsonify({'success': True, 'devices': devices_sound_status, 'room_online': room_online})
            except Exception as e:
                self.logger.error(f"获取房间音效状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/rooms/<int:room_id>/devices/<int:device_id>/sound_config', methods=['PUT'])
        def update_device_sound_config(room_id, device_id):
            try:
                data = request.get_json()
                trigger_sound = data.get('trigger_sound', None)
                trigger_sound_delay = data.get('trigger_sound_delay', None)
                
                room = self.device_manager.get_room_with_all_devices(room_id)
                device_name = None
                current_trigger_sound = False
                current_trigger_sound_delay = 0
                if room:
                    for device in room.get('devices', []):
                        if device.get('id') == device_id:
                            device_name = device.get('name')
                            current_trigger_sound = device.get('trigger_sound', False)
                            current_trigger_sound_delay = device.get('trigger_sound_delay', 0)
                            break
                
                if trigger_sound is None:
                    trigger_sound = current_trigger_sound
                if trigger_sound_delay is None:
                    trigger_sound_delay = current_trigger_sound_delay
                
                room_db_path = self.config.get_room_db_path(room_id)
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    "UPDATE devices SET trigger_sound = ?, trigger_sound_delay = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND room_id = ?",
                    (1 if trigger_sound else 0, trigger_sound_delay, device_id, room_id)
                )
                
                conn.commit()
                conn.close()
                
                self.device_manager.reload_rooms()
                
                esp32_sync_result = None
                if device_name and self.trigger_sound_player and trigger_sound != current_trigger_sound:
                    room_obj = self.device_manager.rooms.get(room_id)
                    if room_obj and room_obj.online:
                        if trigger_sound:
                            esp32_sync_result = self.trigger_sound_player.upload_sound_to_esp32(room_id, device_name)
                        else:
                            esp32_sync_result = self.trigger_sound_player.delete_sound_from_esp32(room_id, device_name)
                    elif trigger_sound:
                        import sqlite3
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE devices SET trigger_sound = 0, trigger_sound_delay = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND room_id = ?",
                            (device_id, room_id)
                        )
                        conn.commit()
                        conn.close()
                        self.device_manager.reload_rooms()
                        return jsonify({
                            'success': False,
                            'error': '设备离线，无法开启音效'
                        })
                
                return jsonify({
                    'success': True,
                    'esp32_sync': esp32_sync_result
                })
            except Exception as e:
                self.logger.error(f"更新设备音效配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/rooms/<int:room_id>/always/loop_status')
        def get_always_loop_status(room_id):
            """获取主常动装置的循环触发状态"""
            try:
                room = self.device_manager.get_room_with_all_devices(room_id)
                if not room:
                    return jsonify({'success': False, 'error': 'Room not found'}), 404
                
                always_device = None
                for device in room.get('devices', []):
                    if device.get('name') == 'always':
                        always_device = device
                        break
                
                if not always_device:
                    return jsonify({'success': False, 'error': 'Always device not found'}), 404
                
                is_running = False
                if self.room_worker_manager:
                    is_running = self.room_worker_manager.is_loop_active(room_id, 'always')
                
                return jsonify({
                    'success': True,
                    'device': {
                        'id': always_device.get('id'),
                        'name': always_device.get('name'),
                        'label': always_device.get('label', ''),
                        'loop_action': always_device.get('loop_action', 'manual'),
                        'loop_minute': always_device.get('loop_minute', ''),
                        'loop_duration': always_device.get('loop_duration', 0.0),
                        'is_running': is_running
                    }
                })
            except Exception as e:
                self.logger.error(f"获取主常动循环状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/rooms/<int:room_id>/always/loop_config', methods=['PUT'])
        def update_always_loop_config(room_id):
            """更新主常动装置的循环配置"""
            try:
                data = request.get_json()
                loop_action = data.get('loop_action', 'manual')
                loop_minute = data.get('loop_minute', '')
                if not isinstance(loop_minute, str):
                    loop_minute = str(loop_minute)
                
                if loop_minute.strip():
                    parts = [p.strip() for p in loop_minute.split('|') if p.strip()]
                    for part in parts:
                        try:
                            num = int(part)
                        except ValueError:
                            return jsonify({'success': False, 'error': f'无效的分钟值: {part}'}), 400
                        if num < 0 or num > 59:
                            return jsonify({'success': False, 'error': f'分钟值必须在0-59之间: {part}'}), 400
                
                loop_duration = data.get('loop_duration', 0.0)
                
                room = self.device_manager.get_room_with_all_devices(room_id)
                if not room:
                    return jsonify({'success': False, 'error': 'Room not found'}), 404
                
                always_device = None
                for device in room.get('devices', []):
                    if device.get('name') == 'always':
                        always_device = device
                        break
                
                if not always_device:
                    return jsonify({'success': False, 'error': 'Always device not found'}), 404
                
                room_db_path = self.config.get_room_db_path(room_id)
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    "UPDATE devices SET loop_action = ?, loop_minute = ?, loop_duration = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND room_id = ?",
                    (loop_action, loop_minute, loop_duration, always_device.get('id'), room_id)
                )
                
                conn.commit()
                conn.close()
                
                self.device_manager.reload_rooms()
                
                if self.room_worker_manager:
                    self.room_worker_manager.update_loop_device_config(room_id, 'always')
                
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"更新主常动循环配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/system/status')
        def get_system_status():
            status = self.device_manager.get_system_status()
            status['license_id'] = self.license_id
            return jsonify(status)

        @self.app.route('/api/system/patrol_dialog', methods=['POST'])
        def update_patrol_dialog():
            data = request.get_json()
            enabled = data.get('enabled', False)
            
            try:
                self.config.set_system_db_config('patrol_dialog_enabled', enabled)
                self.logger.info(f"巡检对讲状态已保存: {enabled}")
                return jsonify({'success': True, 'enabled': enabled})
            except Exception as e:
                self.logger.error(f"更新巡检对讲配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/system/db_config', methods=['GET', 'POST'])
        def system_db_config():
            """获取或设置system数据库配置"""
            if request.method == 'GET':
                try:
                    configs = self.config.get_all_system_db_configs()
                    return jsonify({'success': True, 'configs': configs})
                except Exception as e:
                    self.logger.error(f"获取system配置失败: {e}")
                    return jsonify({'success': False, 'error': str(e)}), 500
            else:
                try:
                    data = request.get_json()
                    for key, value in data.items():
                        self.config.set_system_db_config(key, value)
                    self.logger.info(f"更新system配置成功: {data}")
                    return jsonify({'success': True})
                except Exception as e:
                    self.logger.error(f"更新system配置失败: {e}")
                    return jsonify({'success': False, 'error': str(e)}), 500


        @self.app.route('/api/system/config/zip', methods=['GET'])
        def download_config_zip():
            project_dir = os.path.dirname(os.path.dirname(__file__))
            config_ini_path = os.path.join(project_dir, 'config.ini')
            config_db_path = os.path.join(project_dir, 'config.db')
            
            files_to_zip = []
            
            if os.path.exists(config_ini_path):
                files_to_zip.append(('config.ini', config_ini_path))
            else:
                self.logger.warning(f"config.ini文件不存在: {config_ini_path}")
            
            if os.path.exists(config_db_path):
                files_to_zip.append(('config.db', config_db_path))
            else:
                self.logger.warning(f"config.db文件不存在: {config_db_path}")
            
            if not files_to_zip:
                return jsonify({'success': False, 'error': '配置文件不存在'}), 404
            
            memory_file = io.BytesIO()
            try:
                with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for filename, filepath in files_to_zip:
                        zf.write(filepath, filename)
                
                memory_file.seek(0)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                return send_file(
                    memory_file,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=f'config_{timestamp}.zip'
                )
            except Exception as e:
                self.logger.error(f"打包配置文件失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/audio/upload', methods=['POST'])
        def upload_audio():
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': '没有文件'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': '未选择文件'}), 400
            
            if not self._allowed_file(file.filename):
                return jsonify({'success': False, 'error': '只支持WAV格式'}), 400
            
            original_filename = file.filename
            music_name = request.form.get('music_name', original_filename)
            secure_name = self._generate_secure_filename(original_filename)
            filepath = os.path.join(self.audio_upload_dir, secure_name)
            
            try:
                file.save(filepath)
                
                if not self._validate_wav_file(filepath):
                    os.remove(filepath)
                    return jsonify({'success': False, 'error': '无效的WAV文件'}), 400
                
                file_size = os.path.getsize(filepath)
                file_url = f"/static/audio/{secure_name}"
                
                self.audio_metadata[secure_name] = {
                    'music_name': music_name,
                    'original_name': original_filename,
                    'upload_time': int(time.time())
                }
                self._save_audio_metadata()
                
                self.logger.info(f"音频文件上传成功: {original_filename} -> {secure_name} ({file_size} bytes), 音乐名称: {music_name}")
                
                return jsonify({
                    'success': True,
                    'filename': secure_name,
                    'original_name': original_filename,
                    'music_name': music_name,
                    'size': file_size,
                    'url': file_url
                })
            except Exception as e:
                self.logger.error(f"音频文件上传失败: {e}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/audio/files')
        def list_audio_files():
            try:
                files = []
                for filename in os.listdir(self.audio_upload_dir):
                    if filename.endswith('.wav'):
                        filepath = os.path.join(self.audio_upload_dir, filename)
                        file_size = os.path.getsize(filepath)
                        file_url = f"/static/audio/{filename}"
                        
                        metadata = self.audio_metadata.get(filename, {})
                        music_name = metadata.get('music_name', filename)
                        
                        files.append({
                            'filename': filename,
                            'music_name': music_name,
                            'size': file_size,
                            'url': file_url
                        })
                
                files.sort(key=lambda x: os.path.getmtime(os.path.join(self.audio_upload_dir, x['filename'])), reverse=True)
                
                return jsonify({'success': True, 'files': files})
            except Exception as e:
                self.logger.error(f"获取音频文件列表失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/audio/delete/<filename>', methods=['DELETE'])
        def delete_audio_file(filename):
            try:
                filepath = os.path.join(self.audio_upload_dir, filename)
                if not os.path.exists(filepath):
                    return jsonify({'success': False, 'error': '文件不存在'}), 404
                
                os.remove(filepath)
                
                if filename in self.audio_metadata:
                    del self.audio_metadata[filename]
                    self._save_audio_metadata()
                
                self.logger.info(f"音频文件删除成功: {filename}")
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"音频文件删除失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/system/shutdown', methods=['POST'])
        def shutdown_system():
            try:
                self.logger.info("收到关机请求")
                
                import subprocess
                import time
                import threading
                
                # 立即返回响应，不等待关机准备完成
                response = jsonify({
                    'success': True,
                    'message': '系统正在关机...'
                })
                
                # 在后台线程中执行关机准备
                def shutdown_preparation():
                    try:
                        self.logger.info("正在准备关机...")
                        
                        # 发送进度更新
                        self.socketio.emit('shutdown_progress', {'step': 'preparing', 'message': '正在准备关机...'})
                        
                        # 先停止所有服务
                        self.logger.info("停止音频路由器...")
                        self.socketio.emit('shutdown_progress', {'step': 'stopping_audio', 'message': '停止音频路由器...'})
                        self.audio_router.stop()
                        
                        self.logger.info("停止设备管理器...")
                        self.socketio.emit('shutdown_progress', {'step': 'stopping_device', 'message': '停止设备管理器...'})
                        self.device_manager.stop()
                        
                        self.logger.info("停止网络服务器...")
                        self.socketio.emit('shutdown_progress', {'step': 'stopping_network', 'message': '停止网络服务器...'})
                        self.network_server.stop()
                        
                        # 等待资源清理完成
                        self.logger.info("等待资源清理完成...")
                        self.socketio.emit('shutdown_progress', {'step': 'waiting_cleanup', 'message': '等待资源清理完成...'})
                        time.sleep(2)
                        
                        # 同步文件系统
                        self.logger.info("同步文件系统...")
                        self.socketio.emit('shutdown_progress', {'step': 'syncing', 'message': '同步文件系统...'})
                        subprocess.call(['sync'])
                        
                        self.logger.info("执行关机命令: sudo shutdown -h now")
                        self.socketio.emit('shutdown_progress', {'step': 'executing_shutdown', 'message': '执行关机命令...'})
                        
                        # 执行关机
                        subprocess.call(['sudo', 'shutdown', '-h', 'now'])
                        
                    except Exception as e:
                        self.logger.error(f"关机准备失败: {e}")
                        self.socketio.emit('shutdown_progress', {'step': 'error', 'message': f'关机准备失败: {e}'})
                
                # 启动后台线程执行关机准备
                shutdown_thread = threading.Thread(target=shutdown_preparation)
                shutdown_thread.daemon = True
                shutdown_thread.start()
                
                return response
                
            except Exception as e:
                self.logger.error(f"关机失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/gifts', methods=['GET'])
        def get_gifts():
            try:
                gifts = self.gift_config_manager.get_all_gifts()
                return jsonify({'success': True, 'gifts': gifts})
            except Exception as e:
                self.logger.error(f"获取礼物配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/gifts/<int:gift_id>', methods=['GET'])
        def get_gift_by_id(gift_id):
            try:
                gift = self.gift_config_manager.get_gift_by_id(gift_id)
                if gift:
                    return jsonify({'success': True, 'gift': gift})
                return jsonify({'success': False, 'error': '礼物不存在'}), 404
            except Exception as e:
                self.logger.error(f"获取礼物配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/gifts', methods=['POST'])
        def add_gift():
            try:
                data = request.get_json()
                name = data.get('name')
                value = data.get('value')
                level = data.get('level')
                
                if not name or value is None or level is None:
                    return jsonify({'success': False, 'error': '缺少必要参数'}), 400
                
                success = self.gift_config_manager.add_gift(name, value, level)
                if success:
                    self.gift_config_manager.save()
                    return jsonify({'success': True, 'gift': self.gift_config_manager.get_gift_by_name(name)})
                return jsonify({'success': False, 'error': '添加礼物失败'}), 500
            except Exception as e:
                self.logger.error(f"添加礼物失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/gifts/<int:gift_id>', methods=['PUT'])
        def update_gift(gift_id):
            try:
                data = request.get_json()
                new_name = data.get('name')
                value = data.get('value')
                level = data.get('level')
                
                success = self.gift_config_manager.update_gift_by_id(gift_id, new_name=new_name, value=value, level=level)
                
                if success:
                    self.gift_config_manager.save()
                    return jsonify({'success': True, 'gifts': self.gift_config_manager.get_all_gifts()})
                
                return jsonify({'success': False, 'error': '更新礼物失败'}), 500
            except Exception as e:
                self.logger.error(f"更新礼物失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/gifts/<int:gift_id>', methods=['DELETE'])
        def delete_gift(gift_id):
            try:
                self.logger.info(f"[DEBUG] delete_gift 接收到 gift_id: {gift_id}, 类型: {type(gift_id)}")
                
                success = self.gift_config_manager.delete_gift_by_id(gift_id)
                if success:
                    self.gift_config_manager.save()
                    return jsonify({'success': True})
                return jsonify({'success': False, 'error': '删除礼物失败'}), 500
            except Exception as e:
                self.logger.error(f"删除礼物失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/gifts/sync', methods=['POST'])
        def sync_gifts_from_local():
            """从本地SQLite同步礼物数据到礼物配置"""
            try:
                gift_values = {
                    'huge_min': 1000,
                    'big_min': 500,
                    'medium_min': 100,
                    'small_min': 10,
                    'tiny_min': 1,
                    'none_max': 0
                }

                gift_stats = {}
                rooms = self.config.get_all_rooms() if hasattr(self.config, 'get_all_rooms') else []

                for room in rooms:
                    room_id = room['id']
                    db_path = self.config.get_room_db_path(room_id)
                    if not db_path or not os.path.exists(db_path):
                        continue
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT gift_name, gift_price
                            FROM gifts
                            WHERE gift_count > 0
                            ORDER BY created_at DESC
                            LIMIT 1000
                        """)
                        rows = cursor.fetchall()
                        conn.close()

                        for row in rows:
                            name = row['gift_name']
                            diamond = row['gift_price'] or 0
                            if not name:
                                continue
                            if name not in gift_stats:
                                gift_stats[name] = {'total': 0, 'count': 0}
                            gift_stats[name]['total'] += diamond
                            gift_stats[name]['count'] += 1
                    except Exception as e:
                        self.logger.error(f"同步礼物-读取房间{room_id}失败: {e}")

                synced_count = 0
                updated_count = 0

                for name, stats in gift_stats.items():
                    avg_value = stats['total'] // stats['count'] if stats['count'] > 0 else 0

                    if avg_value >= gift_values['huge_min']:
                        level = '巨'
                    elif avg_value >= gift_values['big_min']:
                        level = '大'
                    elif avg_value >= gift_values['medium_min']:
                        level = '中'
                    elif avg_value >= gift_values['small_min']:
                        level = '小'
                    elif avg_value >= gift_values['tiny_min']:
                        level = '微'
                    else:
                        level = '无'

                    existing = self.gift_config_manager.get_gift_by_name(name)
                    if existing:
                        self.gift_config_manager.update_gift(
                            str(existing['id']),
                            value=avg_value,
                            level=level
                        )
                        updated_count += 1
                    else:
                        self.gift_config_manager.add_gift(name, avg_value, level)
                        synced_count += 1

                self.gift_config_manager.save()

                return jsonify({
                    'success': True,
                    'synced': synced_count,
                    'updated': updated_count,
                    'total': len(gift_stats)
                })

            except Exception as e:
                import traceback
                self.logger.error(f"同步礼物失败: {e}\n{traceback.format_exc()}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<room_id>/gift_triggers', methods=['GET'])
        def get_room_gift_triggers(room_id):
            try:
                device_type = request.args.get('device_type')
                room_db_path = self.config.get_room_db_path(int(room_id))
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if device_type:
                    cursor.execute(
                        "SELECT id, room_id, gift_name, trigger_count, device_type, device_config, created_at FROM gift_triggers WHERE room_id = ? AND device_type = ? ORDER BY created_at DESC",
                        (room_id, device_type)
                    )
                else:
                    cursor.execute(
                        "SELECT id, room_id, gift_name, trigger_count, device_type, device_config, created_at FROM gift_triggers WHERE room_id = ? ORDER BY created_at DESC",
                        (room_id,)
                    )
                rows = cursor.fetchall()
                conn.close()
                
                configs = []
                for row in rows:
                    configs.append({
                        'id': row['id'],
                        'room_id': row['room_id'],
                        'gift_name': row['gift_name'],
                        'trigger_count': row['trigger_count'],
                        'device_type': row['device_type'] if row['device_type'] else 'main',
                        'device_config': row['device_config'],
                        'created_at': row['created_at']
                    })
                
                return jsonify({'success': True, 'configs': configs})
            except Exception as e:
                self.logger.error(f"获取礼物触发配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<room_id>/gift_triggers', methods=['POST'])
        def add_room_gift_trigger(room_id):
            try:
                data = request.get_json()
                gift_name = data.get('gift_name')
                trigger_count = data.get('trigger_count', 1)
                device_type = data.get('device_type', 'main')
                device_config = data.get('device_config')
                
                if not gift_name:
                    return jsonify({'success': False, 'error': '礼物名称不能为空'}), 400
                
                room_db_path = self.config.get_room_db_path(int(room_id))
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # 检查是否已存在（同一房间同一礼物只能有一条记录）
                cursor.execute(
                    "SELECT id FROM gift_triggers WHERE room_id = ? AND gift_name = ?",
                    (room_id, gift_name)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # 更新现有配置
                    cursor.execute(
                        "UPDATE gift_triggers SET trigger_count = ?, device_type = ?, device_config = ?, updated_at = CURRENT_TIMESTAMP WHERE room_id = ? AND gift_name = ?",
                        (trigger_count, device_type, device_config, room_id, gift_name)
                    )
                    config_id = existing[0]
                else:
                    # 插入新配置
                    cursor.execute(
                        "INSERT INTO gift_triggers (room_id, gift_name, trigger_count, device_type, device_config) VALUES (?, ?, ?, ?, ?)",
                        (room_id, gift_name, trigger_count, device_type, device_config)
                    )
                    config_id = cursor.lastrowid
                
                conn.commit()
                conn.close()
                
                return jsonify({'success': True, 'config_id': config_id})
            except Exception as e:
                self.logger.error(f"添加礼物触发配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<room_id>/unknown_gift_config', methods=['GET'])
        def get_unknown_gift_config(room_id):
            try:
                room_db_path = self.config.get_room_db_path(int(room_id))
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                import json
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT device_config FROM gift_triggers WHERE room_id = ? AND gift_name = '未知礼物'",
                    (room_id,)
                )
                row = cursor.fetchone()
                conn.close()
                
                if row and row[0]:
                    try:
                        config = json.loads(row[0])
                        return jsonify({
                            'success': True,
                            'enabled': True,
                            'threshold': config.get('threshold', 10)
                        })
                    except json.JSONDecodeError:
                        pass
                
                return jsonify({
                    'success': True,
                    'enabled': False,
                    'threshold': 10
                })
            except Exception as e:
                self.logger.error(f"获取未知礼物配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<room_id>/unknown_gift_config', methods=['POST'])
        def update_unknown_gift_config(room_id):
            try:
                data = request.get_json()
                enabled = data.get('enabled', False)
                threshold = data.get('threshold', 10)
                
                room_db_path = self.config.get_room_db_path(int(room_id))
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                import json
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                if enabled:
                    # 启用未知礼物触发，添加或更新配置
                    config_json = json.dumps({'threshold': threshold})
                    
                    cursor.execute(
                        "SELECT id FROM gift_triggers WHERE room_id = ? AND gift_name = '未知礼物'",
                        (room_id,)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        cursor.execute(
                            "UPDATE gift_triggers SET device_config = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (config_json, existing[0])
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO gift_triggers (room_id, gift_name, trigger_count, device_type, device_config) VALUES (?, '未知礼物', 1, 'main', ?)",
                            (room_id, config_json)
                        )
                else:
                    # 禁用未知礼物触发，删除配置
                    cursor.execute(
                        "DELETE FROM gift_triggers WHERE room_id = ? AND gift_name = '未知礼物'",
                        (room_id,)
                    )
                
                conn.commit()
                conn.close()
                
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"更新未知礼物配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/gift_triggers/<int:config_id>', methods=['DELETE'])
        def delete_gift_trigger(config_id):
            try:
                import sqlite3
                deleted = False
                
                # 首先检查是否有 room_id 参数
                room_id_param = request.args.get('room_id')
                
                if room_id_param:
                    # 优先使用传入的 room_id
                    try:
                        room_id = int(room_id_param)
                        room_db_path = self.config.get_room_db_path(room_id)
                        if room_db_path and os.path.exists(room_db_path):
                            conn = sqlite3.connect(room_db_path)
                            cursor = conn.cursor()
                            # 检查并删除
                            cursor.execute("DELETE FROM gift_triggers WHERE id = ?", (config_id,))
                            if cursor.rowcount > 0:
                                deleted = True
                                self.logger.info(f"从房间 {room_id} 数据库中删除礼物触发配置 {config_id}")
                            conn.commit()
                            conn.close()
                    except Exception as e:
                        self.logger.warning(f"尝试从指定房间 {room_id_param} 数据库删除失败: {e}")
                
                # 如果通过 room_id 没删除成功，遍历所有房间数据库
                if not deleted:
                    all_rooms = self.config.get_all_rooms()
                    for room in all_rooms:
                        room_id = room.get('id')
                        room_db_path = self.config.get_room_db_path(room_id)
                        if room_db_path and os.path.exists(room_db_path):
                            try:
                                conn = sqlite3.connect(room_db_path)
                                cursor = conn.cursor()
                                # 先检查是否存在
                                cursor.execute("SELECT id FROM gift_triggers WHERE id = ?", (config_id,))
                                if cursor.fetchone():
                                    # 存在，删除它
                                    cursor.execute("DELETE FROM gift_triggers WHERE id = ?", (config_id,))
                                    conn.commit()
                                    conn.close()
                                    deleted = True
                                    self.logger.info(f"从房间 {room_id} 数据库中删除礼物触发配置 {config_id}")
                                    break
                                conn.close()
                            except Exception as e:
                                self.logger.warning(f"尝试从房间 {room_id} 数据库删除失败: {e}")
                
                # 如果房间数据库中没有找到，尝试在主数据库中删除
                if not deleted:
                    db_path = self._get_db_path()
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM gift_triggers WHERE id = ?", (config_id,))
                    if cursor.rowcount > 0:
                        deleted = True
                        self.logger.info(f"从主数据库中删除礼物触发配置 {config_id}")
                    conn.commit()
                    conn.close()
                
                if deleted:
                    return jsonify({'success': True})
                else:
                    self.logger.warning(f"未找到要删除的礼物触发配置 {config_id}")
                    return jsonify({'success': False, 'error': '配置不存在'}), 404
            except Exception as e:
                self.logger.error(f"删除礼物触发配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<room_id>/idle_timeout_config', methods=['GET'])
        def get_idle_timeout_config(room_id):
            try:
                room_db_path = self.config.get_room_db_path(int(room_id))
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                import json
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT trigger_count, device_config FROM gift_triggers WHERE room_id = ? AND gift_name = '闲置触发'",
                    (room_id,)
                )
                row = cursor.fetchone()
                conn.close()
                
                if row and row[0]:
                    try:
                        config = json.loads(row[1]) if row[1] else {}
                        return jsonify({
                            'success': True,
                            'enabled': True,
                            'timeout_seconds': config.get('timeout_seconds', 60),
                            'trigger_count': row[0]
                        })
                    except json.JSONDecodeError:
                        pass
                
                return jsonify({
                    'success': True,
                    'enabled': False,
                    'timeout_seconds': 60,
                    'trigger_count': 1
                })
            except Exception as e:
                self.logger.error(f"获取空闲超时配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/rooms/<room_id>/idle_timeout_config', methods=['POST'])
        def update_idle_timeout_config(room_id):
            try:
                data = request.get_json()
                enabled = data.get('enabled', False)
                timeout_seconds = data.get('timeout_seconds', 60)
                trigger_count = data.get('trigger_count', 1)
                
                room_db_path = self.config.get_room_db_path(int(room_id))
                if room_db_path and os.path.exists(room_db_path):
                    db_path = room_db_path
                else:
                    db_path = self._get_db_path()
                import sqlite3
                import json
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                if enabled:
                    config_json = json.dumps({'timeout_seconds': timeout_seconds})
                    
                    cursor.execute(
                        "SELECT id FROM gift_triggers WHERE room_id = ? AND gift_name = '闲置触发'",
                        (room_id,)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        cursor.execute(
                            "UPDATE gift_triggers SET trigger_count = ?, device_config = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (trigger_count, config_json, existing[0])
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO gift_triggers (room_id, gift_name, trigger_count, device_type, device_config) VALUES (?, '闲置触发', ?, 'main', ?)",
                            (room_id, trigger_count, config_json)
                        )
                else:
                    cursor.execute(
                        "DELETE FROM gift_triggers WHERE room_id = ? AND gift_name = '闲置触发'",
                        (room_id,)
                    )
                
                conn.commit()
                conn.close()
                
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"更新空闲超时配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/messages/<int:room_id>')
        def get_messages(room_id):
            try:
                limit = request.args.get('limit', 20, type=int)
                self.logger.info(f"[API] get_messages called: room_id={room_id}, limit={limit}")

                db_path = self.config.get_room_db_path(room_id)
                if not db_path:
                    return jsonify({'success': False, 'error': f'房间{room_id}数据库不存在'}), 404

                room = self.config.get_room(room_id)
                room_ip = room.get('ip', '') if room else ''

                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")

                try:
                    messages = []

                    msg_rows = conn.execute("""
                        SELECT id, type, nickname as name, content, status, created_at
                        FROM messages
                        ORDER BY id DESC LIMIT ?
                    """, (limit,)).fetchall()

                    for row in msg_rows:
                        msg = dict(row)
                        msg['room'] = room_ip
                        msg['room_id'] = room_id
                        msg['giftname'] = ''
                        msg['giftcount'] = 0
                        msg['giftdiamond'] = 0
                        if msg.get('created_at'):
                            try:
                                dt = datetime.strptime(msg['created_at'], '%Y-%m-%d %H:%M:%S')
                                msg['timestamp'] = dt.timestamp()
                                msg['created_at'] = dt.strftime('%H:%M:%S')
                            except ValueError:
                                pass
                        messages.append(msg)

                    gift_rows = conn.execute("""
                        SELECT id, nickname as name, gift_name as giftname,
                               gift_count as giftcount, gift_price as giftdiamond,
                               content, status, created_at
                        FROM gifts
                        ORDER BY id DESC LIMIT ?
                    """, (limit,)).fetchall()

                    for row in gift_rows:
                        msg = dict(row)
                        msg['room'] = room_ip
                        msg['room_id'] = room_id
                        msg['type'] = 'gif'
                        if msg.get('created_at'):
                            try:
                                dt = datetime.strptime(msg['created_at'], '%Y-%m-%d %H:%M:%S')
                                msg['timestamp'] = dt.timestamp()
                                msg['created_at'] = dt.strftime('%H:%M:%S')
                            except ValueError:
                                pass
                        messages.append(msg)

                    viewer_count = None
                    try:
                        stats_row = conn.execute("""
                            SELECT online_count, created_at FROM room_stats
                            ORDER BY created_at DESC LIMIT 1
                        """).fetchone()
                        if stats_row and stats_row['online_count'] and stats_row['created_at']:
                            stats_time = datetime.strptime(stats_row['created_at'], '%Y-%m-%d %H:%M:%S')
                            if (datetime.now() - stats_time).total_seconds() <= 60:
                                parsed = self._parse_viewer_count(str(stats_row['online_count']))
                                if parsed is not None:
                                    viewer_count = parsed
                    except Exception:
                        pass

                    return jsonify({'success': True, 'messages': messages, 'viewer_count': viewer_count})

                finally:
                    conn.close()

            except Exception as e:
                self.logger.error(f"获取消息失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/messages/all')
        def get_all_messages():
            try:
                from datetime import timedelta
                limit = request.args.get('limit', 100, type=int)

                all_messages = []
                rooms = self.config.get_all_rooms()

                for room in rooms:
                    room_id = room['id']
                    room_ip = room.get('ip', '')
                    db_path = self.config.get_room_db_path(room_id)
                    if not db_path:
                        continue

                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        conn.execute("PRAGMA journal_mode=WAL")

                        msg_rows = conn.execute("""
                            SELECT id, type, nickname as name, content, status, created_at
                            FROM messages
                            ORDER BY id DESC LIMIT ?
                        """, (limit,)).fetchall()

                        for row in msg_rows:
                            msg = dict(row)
                            msg['room'] = room_ip
                            msg['room_id'] = room_id
                            msg['giftname'] = ''
                            msg['giftcount'] = 0
                            msg['giftdiamond'] = 0
                            if msg.get('created_at'):
                                try:
                                    dt = datetime.strptime(msg['created_at'], '%Y-%m-%d %H:%M:%S')
                                    msg['timestamp'] = dt.timestamp()
                                    msg['created_at'] = dt.strftime('%H:%M:%S')
                                except ValueError:
                                    pass
                            all_messages.append(msg)

                        gift_rows = conn.execute("""
                            SELECT id, nickname as name, gift_name as giftname,
                                   gift_count as giftcount, gift_price as giftdiamond,
                                   content, status, created_at
                            FROM gifts
                            ORDER BY id DESC LIMIT ?
                        """, (limit,)).fetchall()

                        for row in gift_rows:
                            msg = dict(row)
                            msg['room'] = room_ip
                            msg['room_id'] = room_id
                            msg['type'] = 'gif'
                            if msg.get('created_at'):
                                try:
                                    dt = datetime.strptime(msg['created_at'], '%Y-%m-%d %H:%M:%S')
                                    msg['timestamp'] = dt.timestamp()
                                    msg['created_at'] = dt.strftime('%H:%M:%S')
                                except ValueError:
                                    pass
                            all_messages.append(msg)

                        conn.close()
                    except Exception as e:
                        self.logger.error(f"获取房间{room_id}消息失败: {e}")

                all_messages.sort(key=lambda x: x.get('timestamp', 0) if x.get('timestamp') else 0, reverse=True)
                all_messages = all_messages[:limit]

                viewer_counts = {}
                for room in rooms:
                    rid = room['id']
                    rip = room.get('ip', '')
                    db_path = self.config.get_room_db_path(rid)
                    if db_path and os.path.exists(db_path):
                        try:
                            c = sqlite3.connect(db_path)
                            c.row_factory = sqlite3.Row
                            sr = c.execute("SELECT online_count, created_at FROM room_stats ORDER BY created_at DESC LIMIT 1").fetchone()
                            c.close()
                            if sr and sr['online_count'] and sr['created_at']:
                                stats_time = datetime.strptime(sr['created_at'], '%Y-%m-%d %H:%M:%S')
                                if (datetime.now() - stats_time).total_seconds() <= 60:
                                    parsed = self._parse_viewer_count(str(sr['online_count']))
                                    if parsed is not None:
                                        viewer_counts[rip] = parsed
                        except Exception:
                            pass

                return jsonify({'success': True, 'messages': all_messages, 'viewer_counts': viewer_counts})

            except Exception as e:
                self.logger.error(f"获取所有消息失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/ota/versions', methods=['GET'])
        def get_ota_versions():
            """获取固件版本列表"""
            try:
                if not self.ota_manager:
                    return jsonify({'success': False, 'error': 'OTA管理器未初始化'}), 500
                versions = self.ota_manager.load_versions()
                return jsonify({'success': True, 'versions': versions})
            except Exception as e:
                self.logger.error(f"获取固件版本失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/ota/devices/check', methods=['POST'])
        def check_devices_update():
            """检查设备是否需要更新"""
            try:
                if not self.ota_manager:
                    return jsonify({'success': False, 'error': 'OTA管理器未初始化'}), 500
                
                data = request.get_json()
                device_ips = data.get('devices', [])
                
                if not device_ips:
                    return jsonify({'success': False, 'error': '设备列表不能为空'}), 400
                
                versions = self.ota_manager.load_versions()
                latest_version = versions.get('latest', '0.0.0')
                
                results = []
                for ip in device_ips:
                    device_info = self.ota_manager.get_device_info(ip)
                    if device_info:
                        device_version = device_info.get('version', '0.0.0')
                        needs_update = self.ota_manager.needs_update(device_version, latest_version)
                        results.append({
                            'ip': ip,
                            'info': device_info,
                            'current_version': device_version,
                            'latest_version': latest_version,
                            'needs_update': needs_update
                        })
                    else:
                        results.append({
                            'ip': ip,
                            'error': '无法获取设备信息',
                            'needs_update': False
                        })
                
                return jsonify({'success': True, 'results': results})
            except Exception as e:
                self.logger.error(f"检查设备更新失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/ota/devices/update', methods=['POST'])
        def update_devices():
            """批量更新设备固件"""
            try:
                if not self.ota_manager:
                    return jsonify({'success': False, 'error': 'OTA管理器未初始化'}), 500
                
                data = request.get_json()
                device_ips = data.get('devices', [])
                version = data.get('version', 'latest')
                max_workers = data.get('max_workers', 3)
                
                if not device_ips:
                    return jsonify({'success': False, 'error': '设备列表不能为空'}), 400
                
                versions = self.ota_manager.load_versions()
                
                if version == 'latest':
                    target_version = versions.get('latest', '0.0.0')
                else:
                    target_version = version
                
                version_info = next((v for v in versions.get('versions', []) if v['version'] == target_version), None)
                if not version_info:
                    return jsonify({'success': False, 'error': f'未找到版本 {target_version}'}), 404
                
                firmware_path = os.path.join(self.ota_manager.firmware_dir, version_info['file'])
                if not os.path.exists(firmware_path):
                    return jsonify({'success': False, 'error': '固件文件不存在'}), 404
                
                results = self.ota_manager.batch_update(device_ips, firmware_path, max_workers)
                
                return jsonify({'success': True, 'results': results})
            except Exception as e:
                self.logger.error(f"批量更新设备失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/log/')
        def log_index():
            return render_template('log_index.html')

        @self.app.route('/log/<int:room_id>')
        def log_room(room_id):
            return render_template('log_room.html', room_id=room_id)

        @self.app.route('/api/log/types')
        def get_log_types():
            log_types = {
                'esp32': 'ESP32设备日志',
                'heartbeat_detail': '心跳详细日志',
                'heartbeat_recv': '心跳接收日志',
                'heartbeat_stats': '心跳统计日志',
                'network_error': '网络异常日志',
                'room_state_change': '房间状态变更日志',
                'esp32_logs_recv': 'ESP32日志接收日志',
                'offline': '离线事件日志',
                'batch_offline': '批量离线日志',
                'server_resource': '服务器资源日志'
            }
            return jsonify({'success': True, 'log_types': log_types})

        @self.app.route('/api/log/list')
        def get_log_list():
            try:
                log_dir = self._get_log_dir()
                if not os.path.exists(log_dir):
                    return jsonify({'success': True, 'logs': []})
                
                log_files = []
                for filename in os.listdir(log_dir):
                    if filename.endswith('.log'):
                        filepath = os.path.join(log_dir, filename)
                        file_size = os.path.getsize(filepath)
                        file_mtime = os.path.getmtime(filepath)
                        log_files.append({
                            'filename': filename,
                            'size': file_size,
                            'mtime': file_mtime,
                            'mtime_str': datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
                
                esp32_dir = os.path.join(log_dir, 'esp32')
                if os.path.exists(esp32_dir):
                    for filename in os.listdir(esp32_dir):
                        if filename.endswith('.json'):
                            filepath = os.path.join(esp32_dir, filename)
                            file_size = os.path.getsize(filepath)
                            file_mtime = os.path.getmtime(filepath)
                            log_files.append({
                                'filename': f'esp32/{filename}',
                                'size': file_size,
                                'mtime': file_mtime,
                                'mtime_str': datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                            })
                
                log_files.sort(key=lambda x: x['mtime'], reverse=True)
                return jsonify({'success': True, 'logs': log_files})
            except Exception as e:
                self.logger.error(f"获取日志列表失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/log/content/<path:log_filename>')
        def get_log_content(log_filename):
            try:
                log_dir = self._get_log_dir()
                if log_filename.startswith('esp32/'):
                    filepath = os.path.join(log_dir, log_filename)
                else:
                    filepath = os.path.join(log_dir, log_filename)
                
                if not os.path.exists(filepath):
                    return jsonify({'success': False, 'error': 'Log file not found'}), 404
                
                if log_filename.endswith('.json'):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                    return jsonify({'success': True, 'content': content, 'is_json': True})
                else:
                    lines_limit = request.args.get('lines', 500, type=int)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    content = lines[-lines_limit:] if len(lines) > lines_limit else lines
                    return jsonify({'success': True, 'content': content, 'is_json': False, 'total_lines': len(lines)})
            except Exception as e:
                self.logger.error(f"获取日志内容失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/log/room/<int:room_id>')
        def get_room_logs(room_id):
            try:
                log_dir = self._get_log_dir()
                esp32_dir = os.path.join(log_dir, 'esp32')
                
                room_logs = []
                if os.path.exists(esp32_dir):
                    for filename in os.listdir(esp32_dir):
                        if filename.startswith(f'room_{room_id}_') and filename.endswith('.json'):
                            filepath = os.path.join(esp32_dir, filename)
                            file_size = os.path.getsize(filepath)
                            file_mtime = os.path.getmtime(filepath)
                            with open(filepath, 'r', encoding='utf-8') as f:
                                log_data = json.load(f)
                            room_logs.append({
                                'filename': filename,
                                'size': file_size,
                                'mtime': file_mtime,
                                'mtime_str': datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                'logs_count': log_data.get('logs_count', 0),
                                'recv_time_str': log_data.get('recv_time_str', '')
                            })
                
                room_logs.sort(key=lambda x: x['mtime'], reverse=True)
                return jsonify({'success': True, 'room_logs': room_logs, 'room_id': room_id})
            except Exception as e:
                self.logger.error(f"获取房间{room_id}日志失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/log/diagnosis/<int:room_id>')
        def get_room_diagnosis(room_id):
            try:
                offline_log_path = os.path.join(self._get_log_dir(), 'offline.log')
                if not os.path.exists(offline_log_path):
                    return jsonify({'success': True, 'diagnosis': []})
                
                diagnosis_results = []
                with open(offline_log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines:
                        if f'房间ID={room_id}' in line:
                            diagnosis_results.append(line.strip())
                
                return jsonify({'success': True, 'diagnosis': diagnosis_results[-20:]})
            except Exception as e:
                self.logger.error(f"获取房间{room_id}诊断结果失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/log/diagnose/<int:room_id>/<float:offline_time>')
        def diagnose_room_offline(room_id, offline_time):
            try:
                diagnosis_type, diagnosis_desc, diagnosis_logs = self.device_manager._diagnose_offline_reason(room_id, offline_time)
                return jsonify({
                    'success': True,
                    'diagnosis_type': diagnosis_type,
                    'diagnosis_desc': diagnosis_desc,
                    'diagnosis_logs': diagnosis_logs[-10:]
                })
            except Exception as e:
                self.logger.error(f"诊断房间{room_id}离线原因失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

    def _get_log_dir(self):
        try:
            if HAS_PATH_HELPER:
                return PathHelper.get_warn_log_dir()
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                return os.path.join(base_dir, 'log')
        except Exception as e:
            self.logger.error(f"获取日志目录失败: {e}")
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(base_dir, 'log')

    def _setup_socketio(self):
        @self.socketio.on('connect')
        def handle_connect():
            self.logger.info(f"客户端连接: {request.sid}")
            emit('connected', {'message': 'Connected to IoT Voice Control System'})
            
            # 发送所有房间的对讲状态
            intercom_status = self.audio_router.get_all_intercom_status()
            emit('all_intercom_status', {'intercom_status': intercom_status})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            self.logger.info(f"客户端断开: {request.sid}")

        @self.socketio.on('get_rooms')
        def handle_get_rooms():
            rooms = self.device_manager.get_all_rooms()
            for room in rooms:
                room_id = room['id']
                db_path = self.config.get_room_db_path(room_id)
                if db_path and os.path.exists(db_path):
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT online_count, created_at FROM room_stats
                            ORDER BY created_at DESC LIMIT 1
                        """)
                        row = cursor.fetchone()
                        conn.close()
                        if row and row['online_count'] and row['created_at']:
                            try:
                                stats_time = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S')
                                if (datetime.now() - stats_time).total_seconds() <= 60:
                                    parsed = self._parse_viewer_count(str(row['online_count']))
                                    if parsed is not None:
                                        room['viewer_count'] = parsed
                            except (ValueError, TypeError):
                                pass
                    except Exception:
                        pass
            emit('rooms_update', {'rooms': rooms})

        @self.socketio.on('control_device')
        def handle_control_device(data):
            room_id = data.get('room_id')
            device_name = data.get('device')
            action = data.get('action')
            
            play_sound = False
            sound_delay = 0
            room = self.device_manager.rooms.get(room_id)
            if room and device_name in room.devices:
                device = room.devices[device_name]
                play_sound = device.trigger_sound
                sound_delay = device.trigger_sound_delay
            
            success = self.device_manager.control_device(room_id, device_name, action, play_sound=play_sound, sound_delay=sound_delay)
            emit('device_control_result', {
                'success': success,
                'room_id': room_id,
                'device': device_name,
                'action': action
            })

        @self.socketio.on('switch_audio')
        def handle_switch_audio(data):
            room_id = data.get('room_id')
            success = self.audio_router.switch_to_room(room_id)
            
            if success:
                self.device_manager.set_audio_active(room_id, True)
                emit('audio_switched', {'room_id': room_id, 'active': True})
            else:
                emit('error', {'message': 'Failed to switch audio'})

        @self.socketio.on('toggle_broadcast')
        def handle_toggle_broadcast(data):
            enable = data.get('enable', False)
            
            if enable:
                self.audio_router.enable_broadcast()
            else:
                self.audio_router.disable_broadcast()
                
            emit('broadcast_toggled', {'enabled': enable})

        @self.socketio.on('update_room_name')
        def handle_update_room_name(data):
            room_id = data.get('room_id')
            new_name = data.get('name')
            
            success = self.device_manager.update_room_name(room_id, new_name)
            if success:
                emit('room_name_updated', {'room_id': room_id, 'name': new_name}, broadcast=True)
            else:
                emit('error', {'message': 'Failed to update room name'})

        @self.socketio.on('update_room_sort')
        def handle_update_room_sort(data):
            room_id = data.get('room_id')
            sort_order = data.get('sort_order')
            
            success = self.device_manager.update_room_sort(room_id, sort_order)
            if success:
                emit('room_sort_updated', {'room_id': room_id, 'sort_order': sort_order}, broadcast=True)
            else:
                emit('error', {'message': 'Failed to update room sort'})

        @self.socketio.on('update_room_live_url')
        def handle_update_room_live_url(data):
            room_id = data.get('room_id')
            live_url = data.get('live_url')
            
            success = self.device_manager.update_room_live_url(room_id, live_url)
            if success:
                # 刷新ws_message_receiver的房间映射
                if self.ws_message_receiver:
                    self.ws_message_receiver._refresh_room_mapping()
                emit('room_live_url_updated', {'room_id': room_id, 'live_url': live_url}, broadcast=True)
            else:
                emit('error', {'message': 'Failed to update room live URL'})

        @self.socketio.on('update_room_intercom_volume')
        def handle_update_room_intercom_volume(data):
            room_id = data.get('room_id')
            volume = data.get('volume')
            
            success = self.device_manager.update_room_intercom_volume(room_id, volume)
            if success:
                emit('room_intercom_volume_updated', {'room_id': room_id, 'volume': volume})
            else:
                emit('error', {'message': 'Failed to update room intercom volume'})

        @self.socketio.on('update_room_background_music_url')
        def handle_update_room_background_music_url(data):
            room_id = data.get('room_id')
            url = data.get('url')
            music_name = data.get('music_name', '')
            size = data.get('size', 0)
            
            success = self.device_manager.update_room_background_music_url(room_id, url, music_name, size)
            if success:
                emit('room_background_music_url_updated', {'room_id': room_id, 'url': url, 'music_name': music_name, 'size': size})
            else:
                emit('error', {'message': 'Failed to update room background music URL'})

        @self.socketio.on('update_trigger_device_config')
        def handle_update_trigger_device_config(data):
            self.logger.info(f"收到update_trigger_device_config事件: {data}")
            room_id = data.get('room_id')
            trigger_on_duration = data.get('trigger_on_duration')
            trigger_off_duration = data.get('trigger_off_duration')
            
            self.logger.info(f"准备保存房间{room_id}的trigger设备配置: on_duration={trigger_on_duration}, off_duration={trigger_off_duration}")
            
            # 添加详细的参数验证调试信息
            self.logger.debug(f"参数验证 - room_id: {room_id}, type: {type(room_id)}")
            self.logger.debug(f"参数验证 - trigger_on_duration: {trigger_on_duration}, type: {type(trigger_on_duration)}")
            self.logger.debug(f"参数验证 - trigger_off_duration: {trigger_off_duration}, type: {type(trigger_off_duration)}")
            
            # 检查room_id是否为有效值
            if not room_id or not isinstance(room_id, int):
                self.logger.error(f"无效的room_id: {room_id}")
                emit('error', {'message': 'Failed to update trigger device config - invalid room_id'})
                return
                
            # 检查时间参数是否为有效值
            if not isinstance(trigger_on_duration, (int, float)) or trigger_on_duration < 0:
                self.logger.error(f"无效的trigger_on_duration: {trigger_on_duration}")
                emit('error', {'message': 'Failed to update trigger device config - invalid on_duration'})
                return
                
            if not isinstance(trigger_off_duration, (int, float)) or trigger_off_duration < 0:
                self.logger.error(f"无效的trigger_off_duration: {trigger_off_duration}")
                emit('error', {'message': 'Failed to update trigger device config - invalid off_duration'})
                return
            
            success = self.device_manager.save_trigger_device_config(room_id, trigger_on_duration, trigger_off_duration)
            if success:
                emit('trigger_device_config_updated', {'room_id': room_id, 'trigger_on_duration': trigger_on_duration, 'trigger_off_duration': trigger_off_duration})
                self.logger.info(f"房间{room_id}的trigger设备配置已保存并广播")
            else:
                self.logger.error(f"房间{room_id}的trigger设备配置保存失败 - device_manager返回False")
                emit('error', {'message': 'Failed to update trigger device config'})

        @self.socketio.on('toggle_microphone')
        def handle_toggle_microphone(data):
            print(f"【后端事件】收到 toggle_microphone 事件: {data}")
            room_id = data.get('room_id')
            enabled = data.get('enabled', False)
            
            success = self.audio_router.toggle_room_intercom(room_id, enabled)
            if success:
                emit('microphone_toggled', {'room_id': room_id, 'enabled': enabled})
                self.logger.info(f"房间{room_id}对话状态已切换: {enabled}")
                print(f"【后端事件】房间{room_id}对话状态已切换: {enabled}")
            else:
                emit('error', {'message': 'Failed to toggle microphone'})
                print(f"【后端事件】切换房间对讲失败")

        @self.socketio.on('detect_room')
        def handle_detect_room(data):
            room_id = data.get('room_id')
            
            room = self.device_manager.get_room(room_id)
            if not room:
                emit('detect_result', {
                    'room_id': room_id,
                    'error': 'Room not found',
                    'connection_success': False,
                    'suggestion': '房间不存在，请检查房间ID'
                })
                return
            
            config_ip = room.get('ip')
            config_port = room.get('port', 8080)
            room_name = room.get('name', f'Room {room_id}')
            
            result = {
                'room_id': room_id,
                'room_name': room_name,
                'config_ip': config_ip,
                'config_port': config_port,
                'connection_success': False,
                'response_time': 0,
                'device_status': None,
                'backend_online': room.get('online', False),
                'last_seen': room.get('last_seen', 0),
                'heartbeat_interval': self.device_manager.heartbeat_interval,
                'error': None,
                'suggestion': ''
            }
            
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                
                self.logger.info(f"检测房间{room_id}连接: {config_ip}:{config_port}")
                
                sock.connect((config_ip, config_port))
                result['response_time'] = int((time.time() - start_time) * 1000)
                result['connection_success'] = True
                
                command = {
                    'type': 'status',
                    'timestamp': time.time()
                }
                
                sock.sendall((json.dumps(command) + '\n').encode())
                response = sock.recv(4096).decode()
                sock.close()
                
                device_status = json.loads(response)
                result['device_status'] = device_status
                
                if device_status.get('status') == 'success':
                    result['suggestion'] = '连接成功！设备响应正常。如果后端仍显示离线，请检查后端心跳检测配置或重启后端服务。'
                else:
                    result['suggestion'] = f'设备响应异常: {device_status.get("message", "未知错误")}'
                    
            except socket.timeout:
                result['error'] = '连接超时'
                result['suggestion'] = '连接超时。请检查：1) ESP32设备是否在线 2) IP地址是否正确 3) 网络连接是否正常 4) 防火墙是否阻止了连接'
                self.logger.warning(f"房间{room_id}连接超时: {config_ip}:{config_port}")
                
            except ConnectionRefusedError:
                result['error'] = '连接被拒绝'
                result['suggestion'] = '连接被拒绝。请检查：1) ESP32设备是否运行 2) 端口是否正确 3) 设备是否被其他程序占用'
                self.logger.warning(f"房间{room_id}连接被拒绝: {config_ip}:{config_port}")
                
            except Exception as e:
                result['error'] = str(e)
                result['suggestion'] = f'连接失败: {str(e)}。请检查网络连接和设备状态。'
                self.logger.error(f"房间{room_id}连接失败: {e}")
            
            emit('detect_result', result)

        @self.socketio.on('play_speaker_beep')
        def handle_play_speaker_beep(data):
            room_id = data.get('room_id')
            volume = data.get('volume', 0.5)
            frequency = data.get('frequency', 1000)
            duration = data.get('duration', 200)
            
            room = self.device_manager.get_room(room_id)
            if not room:
                emit('error', {'message': f'房间{room_id}不存在'})
                return
            
            config_ip = room.get('ip')
            config_port = room.get('port', 8080)
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                
                self.logger.info(f"播放喇叭: 房间{room_id}, {config_ip}:{config_port}, 频率={frequency}Hz, 时长={duration}ms, 音量={volume}")
                
                sock.connect((config_ip, config_port))
                
                command = {
                    'type': 'beep',
                    'duration': duration,
                    'frequency': frequency,
                    'volume': volume
                }
                
                sock.sendall((json.dumps(command) + '\n').encode())
                response = sock.recv(1024).decode()
                sock.close()
                
                response_data = json.loads(response)
                if response_data.get('status') == 'success':
                    self.logger.info(f"喇叭播放成功: 房间{room_id}")
                    emit('speaker_beep_result', {
                        'success': True,
                        'room_id': room_id,
                        'frequency': frequency,
                        'duration': duration,
                        'volume': volume
                    })
                else:
                    emit('error', {'message': f'喇叭播放失败: {response_data.get("message", "未知错误")}'})
                    
            except socket.timeout:
                emit('error', {'message': f'房间{room_id}连接超时'})
                self.logger.warning(f"房间{room_id}喇叭播放超时: {config_ip}:{config_port}")
                
            except ConnectionRefusedError:
                emit('error', {'message': f'房间{room_id}连接被拒绝'})
                self.logger.warning(f"房间{room_id}喇叭播放连接被拒绝: {config_ip}:{config_port}")
                
            except Exception as e:
                emit('error', {'message': f'喇叭播放失败: {str(e)}'})
                self.logger.error(f"房间{room_id}喇叭播放失败: {e}")

        @self.socketio.on('play_audio_file')
        def handle_play_audio_file(data):
            self.logger.info(f"[DEBUG] 收到 play_audio_file 事件")
            self.logger.info(f"[DEBUG] 接收到的数据: {data}")
            
            room_id = data.get('room_id')
            audio_url = data.get('audio_url')
            filename = data.get('filename')
            
            self.logger.info(f"[DEBUG] 解析参数 - room_id: {room_id}, audio_url: {audio_url}, filename: {filename}")
            
            room = self.device_manager.get_room(room_id)
            if not room:
                self.logger.error(f"[DEBUG] 房间{room_id}不存在")
                emit('error', {'message': f'房间{room_id}不存在'})
                return
            
            config_ip = room.get('ip')
            config_port = room.get('port', 8080)
            
            self.logger.info(f"[DEBUG] 房间信息 - IP: {config_ip}, Port: {config_port}")
            
            try:
                self.logger.info(f"[DEBUG] 开始创建socket连接")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                
                self.logger.info(f"[DEBUG] 尝试连接到 {config_ip}:{config_port}")
                sock.connect((config_ip, config_port))
                self.logger.info(f"[DEBUG] 连接成功")
                
                full_audio_url = self._get_full_url(audio_url)
                self.logger.info(f"[DEBUG] 完整音频URL: {full_audio_url}")
                
                command = {
                    'type': 'play_audio',
                    'url': full_audio_url,
                    'filename': filename
                }
                
                command_str = json.dumps(command) + '\n'
                self.logger.info(f"[DEBUG] 发送命令: {command_str}")
                sock.sendall(command_str.encode())
                self.logger.info(f"[DEBUG] 命令已发送，等待响应")
                
                response = sock.recv(1024).decode()
                self.logger.info(f"[DEBUG] 收到响应: {response}")
                sock.close()
                
                response_data = json.loads(response)
                self.logger.info(f"[DEBUG] 解析后的响应数据: {response_data}")
                
                if response_data.get('status') == 'success':
                    self.logger.info(f"音频文件播放成功: 房间{room_id}, 文件={filename}")
                    emit('audio_file_played', {
                        'success': True,
                        'room_id': room_id,
                        'filename': filename,
                        'audio_url': audio_url
                    })
                else:
                    error_msg = response_data.get("message", "未知错误")
                    self.logger.error(f"[DEBUG] ESP32返回错误: {error_msg}")
                    emit('error', {'message': f'音频文件播放失败: {error_msg}'})
                    
            except socket.timeout:
                self.logger.error(f"[DEBUG] 连接超时: {config_ip}:{config_port}")
                emit('error', {'message': f'房间{room_id}连接超时'})
                self.logger.warning(f"房间{room_id}音频文件播放超时: {config_ip}:{config_port}")
                
            except ConnectionRefusedError:
                self.logger.error(f"[DEBUG] 连接被拒绝: {config_ip}:{config_port}")
                emit('error', {'message': f'房间{room_id}连接被拒绝'})
                self.logger.warning(f"房间{room_id}音频文件播放连接被拒绝: {config_ip}:{config_port}")
                
            except Exception as e:
                self.logger.error(f"[DEBUG] 发生异常: {str(e)}")
                emit('error', {'message': f'音频文件播放失败: {str(e)}'})
                self.logger.error(f"房间{room_id}音频文件播放失败: {e}")

        @self.socketio.on('play_background_music')
        def handle_play_background_music(data):
            self.logger.info(f"[DEBUG] 收到 play_background_music 事件: {data}")
            
            room_id = data.get('room_id')
            url = data.get('url')
            loop = data.get('loop', False)
            volume = data.get('volume', 0.5)
            
            self.logger.info(f"[DEBUG] 解析参数 - room_id: {room_id}, url: {url}, loop: {loop}, volume: {volume}")
            
            room = self.device_manager.get_room(room_id)
            if not room:
                self.logger.error(f"[DEBUG] 房间{room_id}不存在")
                emit('error', {'message': f'房间{room_id}不存在'})
                return
            
            config_ip = room.get('ip')
            config_port = room.get('port', 8080)
            
            self.logger.info(f"[DEBUG] 房间信息 - IP: {config_ip}, Port: {config_port}")
            
            try:
                self.logger.info(f"[DEBUG] 开始创建socket连接")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                
                self.logger.info(f"[DEBUG] 尝试连接到 {config_ip}:{config_port}")
                sock.connect((config_ip, config_port))
                self.logger.info(f"[DEBUG] 连接成功")
                
                full_url = self._get_full_url(url)
                self.logger.info(f"[DEBUG] 完整音频URL: {full_url}")
                
                filename = url.split('/')[-1]
                self.logger.info(f"[DEBUG] 文件名: {filename}")
                
                command = {
                    'type': 'play_audio',
                    'url': full_url,
                    'filename': filename,
                    'loop': loop,
                    'volume': volume
                }
                
                command_str = json.dumps(command) + '\n'
                self.logger.info(f"[DEBUG] 发送命令: {command_str}")
                sock.sendall(command_str.encode())
                self.logger.info(f"[DEBUG] 命令已发送，等待响应")
                
                response = sock.recv(1024).decode()
                self.logger.info(f"[DEBUG] 收到响应: {response}")
                sock.close()
                
                response_data = json.loads(response)
                self.logger.info(f"[DEBUG] 解析后的响应数据: {response_data}")
                
                if response_data.get('status') == 'success':
                    self.logger.info(f"背景音乐播放成功: 房间{room_id}")
                    emit('background_music_played', {
                        'success': True,
                        'room_id': room_id,
                        'url': url
                    })
                else:
                    error_msg = response_data.get("message", "未知错误")
                    self.logger.error(f"[DEBUG] ESP32返回错误: {error_msg}")
                    emit('error', {'message': f'背景音乐播放失败: {error_msg}'})
                    
            except socket.timeout:
                self.logger.error(f"[DEBUG] 连接超时: {config_ip}:{config_port}")
                emit('error', {'message': f'房间{room_id}连接超时'})
                self.logger.warning(f"房间{room_id}背景音乐播放超时: {config_ip}:{config_port}")
                
            except ConnectionRefusedError:
                self.logger.error(f"[DEBUG] 连接被拒绝: {config_ip}:{config_port}")
                emit('error', {'message': f'房间{room_id}连接被拒绝'})
                self.logger.warning(f"房间{room_id}背景音乐播放连接被拒绝: {config_ip}:{config_port}")
                
            except Exception as e:
                self.logger.error(f"[DEBUG] 发生异常: {str(e)}")
                emit('error', {'message': f'背景音乐播放失败: {str(e)}'})
                self.logger.error(f"房间{room_id}背景音乐播放失败: {e}")

        @self.socketio.on('stop_background_music')
        def handle_stop_background_music(data):
            room_id = data.get('room_id')
            
            room = self.device_manager.get_room(room_id)
            if not room:
                emit('error', {'message': f'房间{room_id}不存在'})
                return
            
            config_ip = room.get('ip')
            config_port = room.get('port', 8080)
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                
                self.logger.info(f"停止背景音乐: 房间{room_id}")
                
                sock.connect((config_ip, config_port))
                
                command = {
                    'type': 'stop_audio'
                }
                
                sock.sendall((json.dumps(command) + '\n').encode())
                response = sock.recv(1024).decode()
                sock.close()
                
                response_data = json.loads(response)
                if response_data.get('status') == 'success':
                    self.logger.info(f"背景音乐停止成功: 房间{room_id}")
                    emit('background_music_stopped', {
                        'success': True,
                        'room_id': room_id
                    })
                else:
                    emit('error', {'message': f'背景音乐停止失败: {response_data.get("message", "未知错误")}'})
                    
            except socket.timeout:
                emit('error', {'message': f'房间{room_id}连接超时'})
                self.logger.warning(f"房间{room_id}背景音乐停止超时: {config_ip}:{config_port}")
                
            except ConnectionRefusedError:
                emit('error', {'message': f'房间{room_id}连接被拒绝'})
                self.logger.warning(f"房间{room_id}背景音乐停止连接被拒绝: {config_ip}:{config_port}")
                
            except Exception as e:
                emit('error', {'message': f'背景音乐停止失败: {str(e)}'})
                self.logger.error(f"房间{room_id}背景音乐停止失败: {e}")

    def _setup_network_handlers(self):
        def device_callback(event_type, data):
            if event_type == 'device_control':
                self.socketio.emit('device_status_update', data)
            elif event_type == 'room_status':
                self.socketio.emit('room_status_update', data)
            elif event_type == 'audio_status':
                self.socketio.emit('audio_status_update', data)
            elif event_type == 'intercom_status':
                self.socketio.emit('intercom_status_update', data)

        self.device_manager.register_callback(device_callback)

    def initialize(self):
        self.logger.info("初始化Web应用...")
        
        # 重新加载配置以确保获取最新设置
        self.config.reload()
        
        if not self.audio_router.initialize():
            self.logger.error("音频路由引擎初始化失败")
            return False
            
        self.device_manager.start()
        self.audio_router.start()
        self.ai_voice_player.start()
        
        if self.room_worker_manager:
            self.room_worker_manager.start_all_rooms()
            self.logger.info("RoomWorkerManager已启动所有房间Worker")

        if self.ws_message_receiver:
            self.ws_message_receiver.start()
            self.logger.info("WSMessageReceiver已启动")
        
        if not self.network_server.start():
            self.logger.error("网络服务器启动失败")
            return False
            
        self.logger.info("Web应用初始化完成")
        return True

    def run(self, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=False):
        self.logger.info(f"启动Web服务器: {host}:{port}")
        
        self.socketio.run(self.app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=allow_unsafe_werkzeug)

    def shutdown(self):
        self.logger.info("关闭Web应用...")
        self.ai_voice_player.stop()
        self.audio_router.stop()
        self.device_manager.stop()
        self.network_server.stop()
        
        if self.ws_message_receiver:
            self.ws_message_receiver.stop()

        if self.room_worker_manager:
            self.room_worker_manager.stop_all_rooms()