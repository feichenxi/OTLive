import queue
import threading
import time
import configparser
import logging
import os
import sqlite3
from typing import Dict, Optional, List
from datetime import datetime
from collections import defaultdict
import sys
from queue import Queue

logger = logging.getLogger('AIManager')

SCAN_INTERVAL = 1.0
BIG_GIFT_THRESHOLD = 100
MAX_SMALL_GIFTS_PER_ROOM = 5
MERGE_WINDOW = 30
EXPIRE_THRESHOLD = 30
GENERATOR_POOL_SIZE = 3
ROOM_THANK_INTERVAL = 8
ROOM_CONFIG_CACHE_TTL = 30

STATUS_DISABLED = -5
STATUS_SKIPPED_DIAMOND = -1
STATUS_SKIPPED_OVERLIMIT = -2
STATUS_MERGED = -3
STATUS_COOLDOWN = -4
STATUS_PENDING = 0
STATUS_CLAIMED = 1
STATUS_TEXT_GENERATED = 2
STATUS_VOICE_GENERATED = 3
STATUS_PLAYING = 4
STATUS_COMPLETED = 9


class AIManager:

    def __init__(self, license_id: int = None, config_path: str = None, database_manager=None):
        self.logger = logger
        self.license_id = license_id
        self.database_manager = database_manager

        self.config = self._load_config(config_path)

        self.scan_interval = self.config.getfloat('ai', 'scan_interval', fallback=SCAN_INTERVAL)
        self.big_gift_threshold = self.config.getint('ai', 'big_gift_threshold', fallback=BIG_GIFT_THRESHOLD)
        self.max_small_gifts_per_room = self.config.getint('ai', 'max_small_gifts_per_room', fallback=MAX_SMALL_GIFTS_PER_ROOM)
        self.merge_window = self.config.getint('ai', 'merge_window', fallback=MERGE_WINDOW)
        self.expire_threshold = self.config.getint('ai', 'expire_threshold', fallback=EXPIRE_THRESHOLD)
        self.generator_pool_size = self.config.getint('ai', 'generator_pool_size', fallback=GENERATOR_POOL_SIZE)
        self.room_thank_interval = self.config.getint('ai', 'room_thank_interval', fallback=ROOM_THANK_INTERVAL)
        self.room_config_cache_ttl = self.config.getint('ai', 'room_config_cache_ttl', fallback=ROOM_CONFIG_CACHE_TTL)
        self.user_thank_cooldown = self.config.getint('ai', 'user_thank_cooldown', fallback=15)

        self.running = False
        self._scan_event = threading.Event()

        self.text_generator = None
        self.voice_generator = None
        self.ai_voice_player = None

        self._room_config_cache: Dict[str, dict] = {}
        self._room_last_play_time: Dict[str, float] = {}
        self._user_last_thank: Dict[tuple, float] = {}

        self._merge_queue = Queue()
        self._generation_queue = Queue()
        self._playback_queues: Dict[str, Queue] = {}
        self._playback_threads: Dict[str, threading.Thread] = {}
        self._playback_lock = threading.Lock()

        self._init_generators()

    def _load_config(self, config_path: str = None) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        if config_path is None:
            possible_paths = [
                'config.ini',
                '../config.ini',
                '../../config.ini',
                os.path.join(os.path.dirname(__file__), '..', 'config.ini')
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
        if config_path and os.path.exists(config_path):
            config.read(config_path, encoding='utf-8')
        return config

    def _get_all_room_db_paths(self) -> list:
        if not self.database_manager:
            return []
        rooms = self.database_manager.get_all_rooms()
        result = []
        for room in rooms:
            room_id = room['id']
            room_ip = room.get('ip', '')
            db_path = self.database_manager.get_room_db_path(room_id)
            if db_path and os.path.exists(db_path):
                result.append({'room_id': room_id, 'room_ip': room_ip, 'db_path': db_path})
        return result

    def _init_generators(self):
        try:
            aitxt_config = {
                'enabled': True,
                'api_key': self.config.get('aitxt', 'api_key', fallback=''),
                'model': self.config.get('aitxt', 'model', fallback=''),
                'endpoint': self.config.get('aitxt', 'endpoint', fallback=''),
                'timeout': self.config.getint('aitxt', 'timeout', fallback=30)
            }
            try:
                from ai.aitxt import GiftTextGenerator
                self.text_generator = GiftTextGenerator(aitxt_config)
            except ImportError:
                try:
                    from aitxt import GiftTextGenerator
                    self.text_generator = GiftTextGenerator(aitxt_config)
                except ImportError:
                    self.logger.warning("文本生成器模块未找到")
                    self.text_generator = None
        except Exception as e:
            self.logger.error(f"文本生成器初始化失败: {e}")
            self.text_generator = None

        try:
            if getattr(sys, 'frozen', False):
                self.base_dir = os.path.dirname(sys.executable)
            else:
                ai_dir = os.path.dirname(__file__)
                self.base_dir = os.path.dirname(ai_dir)

            aiwav_config = {
                'enabled': True,
                'provider': self.config.get('aiwav', 'provider', fallback='cosyvoice'),
                'api_key': self.config.get('aiwav', 'api_key', fallback=''),
                'model': self.config.get('aiwav', 'model', fallback=''),
                'endpoint': self.config.get('aiwav', 'endpoint', fallback='http://localhost:50000'),
                'output_dir': self.config.get('aiwav', 'output_dir', fallback='./aiwav/output'),
                'output_format': self.config.get('aiwav', 'output_format', fallback='wav'),
                'sample_rate': self.config.getint('audio', 'sample_rate', fallback=48000),
                'timeout': self.config.getint('aiwav', 'timeout', fallback=60),
                'base_dir': self.base_dir
            }
            aiwav_config['output_dir'] = os.path.join(self.base_dir, 'wav')

            try:
                from ai.aiwav import GiftVoiceGenerator
                self.voice_generator = GiftVoiceGenerator(aiwav_config)
            except ImportError:
                try:
                    from aiwav import GiftVoiceGenerator
                    self.voice_generator = GiftVoiceGenerator(aiwav_config)
                except ImportError:
                    self.logger.warning("语音生成器模块未找到")
                    self.voice_generator = None
        except Exception as e:
            self.logger.error(f"语音生成器初始化失败: {e}")
            self.voice_generator = None

    def _get_room_config_cached(self, room_ip: str) -> dict:
        now = time.time()
        cached = self._room_config_cache.get(room_ip)
        if cached and (now - cached.get('_cached_at', 0)) < self.room_config_cache_ttl:
            return cached

        config = self._fetch_room_config(room_ip)
        config['_cached_at'] = now
        self._room_config_cache[room_ip] = config
        return config

    def _fetch_room_config(self, room_ip: str) -> dict:
        try:
            import requests
            response = requests.get(
                f'https://live.hzjt.com/api/upload_voice.php?action=get&room={room_ip}&license_id={self.license_id or 0}',
                timeout=5
            )
            result = response.json()

            if result.get('code') == 0 and result.get('data'):
                voice_data = result['data']
                voice_id = None
                ai_thank_enabled = bool(int(voice_data.get('ai_thank_enabled', 0)))
                thank_value = float(voice_data.get('thank_value', 0) or 0)
                ai_prompt = voice_data.get('ai_prompt', '')

                if voice_data.get('voice_id') and int(voice_data.get('voice_status', 0)) == 2:
                    voice_id = voice_data['voice_id']

                return {
                    'voice_id': voice_id,
                    'ai_thank_enabled': ai_thank_enabled,
                    'thank_value': thank_value,
                    'ai_prompt': ai_prompt if ai_prompt and len(ai_prompt.strip()) > 1 else None
                }
            else:
                return {'voice_id': None, 'ai_thank_enabled': False, 'thank_value': 0, 'ai_prompt': None}
        except Exception as e:
            self.logger.error(f"获取房间voice配置失败: {e}")
            return {'voice_id': None, 'ai_thank_enabled': False, 'thank_value': 0, 'ai_prompt': None}

    def _is_expired(self, created_at) -> bool:
        if not created_at:
            return True
        try:
            if isinstance(created_at, str):
                msg_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            else:
                msg_time = created_at
            elapsed = (datetime.now() - msg_time).total_seconds()
            return elapsed > self.expire_threshold
        except Exception:
            return True

    def _update_gift_status(self, msg_id: int, status: int, txt: str = None, db_path: str = None):
        try:
            if not db_path:
                db_path = self._find_db_path_for_msg(msg_id)
            if not db_path or not os.path.exists(db_path):
                return False
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            if txt:
                cursor.execute("UPDATE gifts SET status = ?, txt = ? WHERE id = ?", (status, txt, msg_id))
            else:
                cursor.execute("UPDATE gifts SET status = ? WHERE id = ?", (status, msg_id))
            conn.commit()
            conn.close()

            if status in (STATUS_DISABLED, STATUS_SKIPPED_DIAMOND, STATUS_SKIPPED_OVERLIMIT, STATUS_MERGED, STATUS_COOLDOWN, STATUS_COMPLETED):
                room_id = self._get_room_id_from_db_path(db_path)
                if room_id is not None:
                    self._emit_gift_status(room_id, msg_id, status)

            return True
        except Exception as e:
            self.logger.error(f"更新礼物状态失败: {e}")
            return False

    def _get_room_id_from_db_path(self, db_path: str) -> Optional[int]:
        try:
            for room_info in self._get_all_room_db_paths():
                if room_info['db_path'] == db_path:
                    return room_info['room_id']
        except Exception:
            pass
        return None

    def _emit_gift_status(self, room_id: int, gift_id: int, status: int):
        try:
            if self.ai_voice_player and hasattr(self.ai_voice_player, 'socketio') and self.ai_voice_player.socketio:
                self.ai_voice_player.socketio.emit('gift_status_update', {
                    'room_id': room_id,
                    'gift_id': gift_id,
                    'status': status
                })
        except Exception as e:
            self.logger.error(f"推送礼物状态失败: {e}")

    def _find_db_path_for_msg(self, msg_id: int) -> Optional[str]:
        room_dbs = self._get_all_room_db_paths()
        for room_info in room_dbs:
            try:
                conn = sqlite3.connect(room_info['db_path'])
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM gifts WHERE id = ?", (msg_id,))
                if cursor.fetchone():
                    conn.close()
                    return room_info['db_path']
                conn.close()
            except Exception:
                pass
        return None

    def _batch_update_status(self, msg_ids: List[int], status: int, db_path: str = None):
        if not msg_ids:
            return
        if db_path and os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                placeholders = ','.join(['?'] * len(msg_ids))
                cursor.execute(f"UPDATE gifts SET status = ? WHERE id IN ({placeholders})", [status] + msg_ids)
                conn.commit()
                conn.close()

                if status in (STATUS_DISABLED, STATUS_SKIPPED_DIAMOND, STATUS_SKIPPED_OVERLIMIT, STATUS_MERGED, STATUS_COOLDOWN, STATUS_COMPLETED):
                    room_id = self._get_room_id_from_db_path(db_path)
                    if room_id is not None:
                        for msg_id in msg_ids:
                            self._emit_gift_status(room_id, msg_id, status)
            except Exception as e:
                self.logger.error(f"批量更新状态失败: {e}")
        else:
            for msg_id in msg_ids:
                self._update_gift_status(msg_id, status)

    def _get_gift_value_level(self, gift_name: str, diamond_count: int) -> str:
        if diamond_count >= 1000:
            return '巨'
        elif diamond_count >= 100:
            return '大'
        elif diamond_count >= 10:
            return '中'
        elif diamond_count >= 1:
            return '小'
        else:
            return '无'

    def _generate_filename(self, room_id: int = None, msg_id: int = None) -> str:
        ext = 'wav'
        if room_id and msg_id:
            return f'{room_id}_gift_{msg_id}.{ext}'
        elif msg_id:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return f'gift_{msg_id}_{timestamp}.{ext}'
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            return f'gift_{timestamp}.{ext}'

    def _get_relative_path(self, absolute_path: str) -> str:
        if not self.base_dir:
            return absolute_path
        try:
            rel_path = os.path.relpath(absolute_path, self.base_dir)
            rel_path = rel_path.replace('\\', '/')
            return rel_path
        except ValueError:
            return absolute_path

    def _get_absolute_wav_path(self, wav_path: str) -> str:
        if not wav_path:
            return wav_path
        if os.path.isabs(wav_path):
            return wav_path
        wav_path = wav_path.replace('/', os.sep)
        return os.path.join(self.base_dir, wav_path)

    # ==================== Scanner Thread ====================

    def _scanner_loop(self):
        self.logger.info("Scanner线程启动")
        while self.running:
            try:
                self._scan_and_push()
            except Exception as e:
                self.logger.error(f"Scanner异常: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            self._scan_event.wait(timeout=self.scan_interval)
            self._scan_event.clear()
        self.logger.info("Scanner线程停止")

    def _scan_and_push(self):
        room_dbs = self._get_all_room_db_paths()
        if not room_dbs:
            return

        for room_info in room_dbs:
            room_ip = room_info['room_ip']
            db_path = room_info['db_path']
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, nickname as name, content, gift_name as giftname,
                           gift_count as giftcount, gift_price as giftdiamond,
                           status, txt, created_at
                    FROM gifts
                    WHERE status = 0 AND gift_count > 0
                    ORDER BY created_at ASC LIMIT 100
                """)
                rows = cursor.fetchall()
                if rows:
                    msg_ids = [row['id'] for row in rows]
                    placeholders = ','.join(['?'] * len(msg_ids))
                    cursor.execute(f"UPDATE gifts SET status = ? WHERE id IN ({placeholders})", [STATUS_CLAIMED] + msg_ids)
                    conn.commit()
                for row in rows:
                    msg = dict(row)
                    msg['room'] = room_ip
                    msg['room_id'] = room_info['room_id']
                    msg['_db_path'] = db_path
                    self._merge_queue.put(msg)
                conn.close()
            except Exception as e:
                self.logger.error(f"扫描房间{room_info['room_id']}失败: {e}")

    # ==================== Merge/Filter Thread ====================

    def _merge_loop(self):
        self.logger.info("Merge线程启动")
        while self.running:
            try:
                batch = []
                try:
                    item = self._merge_queue.get(timeout=1.0)
                    batch.append(item)
                    while not self._merge_queue.empty() and len(batch) < 200:
                        batch.append(self._merge_queue.get_nowait())
                except queue.Empty:
                    continue

                if batch:
                    self._merge_and_filter(batch)
            except Exception as e:
                self.logger.error(f"Merge异常: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
        self.logger.info("Merge线程停止")

    def _merge_and_filter(self, messages: List[Dict]):
        expired_by_db = {}
        valid_messages = []

        for msg in messages:
            if self._is_expired(msg.get('created_at')):
                db_path = msg.get('_db_path')
                if db_path not in expired_by_db:
                    expired_by_db[db_path] = []
                expired_by_db[db_path].append(msg['id'])
            else:
                valid_messages.append(msg)

        for db_path, ids in expired_by_db.items():
            self._batch_update_status(ids, STATUS_SKIPPED_OVERLIMIT, db_path=db_path)

        if not valid_messages:
            return

        room_messages = defaultdict(list)
        for msg in valid_messages:
            room_messages[msg.get('room', 'unknown')].append(msg)

        for room_ip, room_msgs in room_messages.items():
            to_process = self._merge_room_messages(room_ip, room_msgs)
            for item in to_process:
                self._generation_queue.put(item)

    def _merge_room_messages(self, room_ip: str, messages: List[Dict]) -> List[Dict]:
        big_gifts = []
        small_gifts = []

        for msg in messages:
            diamond_per = int(msg.get('giftdiamond', 0))
            count = int(msg.get('giftcount', 1))
            total = diamond_per * count
            msg['_total_diamond'] = total
            if total >= self.big_gift_threshold:
                big_gifts.append(msg)
            else:
                small_gifts.append(msg)

        merged_small = self._apply_merge_rules(small_gifts)

        result = list(big_gifts)
        skipped_by_db = defaultdict(list)

        for i, msg in enumerate(merged_small):
            if i < self.max_small_gifts_per_room:
                result.append(msg)
            else:
                db_path = msg.get('_db_path')
                if msg.get('is_merged'):
                    skipped_by_db[db_path].extend(msg.get('merged_ids', [msg['id']]))
                else:
                    skipped_by_db[db_path].append(msg['id'])

        for db_path, ids in skipped_by_db.items():
            self._batch_update_status(ids, STATUS_SKIPPED_OVERLIMIT, db_path=db_path)

        return result

    def _apply_merge_rules(self, messages: List[Dict]) -> List[Dict]:
        if not messages:
            return []

        messages.sort(key=lambda x: x.get('created_at', ''))

        user_groups = defaultdict(list)
        for msg in messages:
            user = msg.get('name', 'unknown')
            user_groups[user].append(msg)

        result = []

        for user, user_msgs in user_groups.items():
            same_gift_groups = defaultdict(list)
            for msg in user_msgs:
                gift_name = msg.get('giftname', '')
                same_gift_groups[gift_name].append(msg)

            merged_same_gift = []
            for gift_name, gift_msgs in same_gift_groups.items():
                time_windows = []
                for msg in gift_msgs:
                    placed = False
                    for window in time_windows:
                        last_msg = window[-1]
                        try:
                            last_time = datetime.strptime(last_msg['created_at'], '%Y-%m-%d %H:%M:%S') if isinstance(last_msg.get('created_at'), str) else last_msg.get('created_at')
                            cur_time = datetime.strptime(msg['created_at'], '%Y-%m-%d %H:%M:%S') if isinstance(msg.get('created_at'), str) else msg.get('created_at')
                            if (cur_time - last_time).total_seconds() <= self.merge_window:
                                window.append(msg)
                                placed = True
                                break
                        except Exception:
                            pass
                    if not placed:
                        time_windows.append([msg])

                for window in time_windows:
                    if len(window) == 1:
                        merged_same_gift.append(window[0])
                    else:
                        merged_same_gift.append(self._create_merged_message(window))

            merged_same_gift.sort(key=lambda x: x.get('created_at', ''))

            time_windows = []
            for msg in merged_same_gift:
                placed = False
                for window in time_windows:
                    last_msg = window[-1]
                    try:
                        last_time = datetime.strptime(last_msg['created_at'], '%Y-%m-%d %H:%M:%S') if isinstance(last_msg.get('created_at'), str) else last_msg.get('created_at')
                        cur_time = datetime.strptime(msg['created_at'], '%Y-%m-%d %H:%M:%S') if isinstance(msg.get('created_at'), str) else msg.get('created_at')
                        if (cur_time - last_time).total_seconds() <= self.merge_window:
                            window.append(msg)
                            placed = True
                            break
                    except Exception:
                        pass
                if not placed:
                    time_windows.append([msg])

            for window in time_windows:
                if len(window) == 1:
                    result.append(window[0])
                else:
                    best = max(window, key=lambda m: m.get('_total_diamond', 0))
                    for msg in window:
                        if msg is best:
                            continue
                        db_path = msg.get('_db_path')
                        if msg.get('is_merged'):
                            self._batch_update_status(msg.get('merged_ids', [msg['id']]), STATUS_MERGED, db_path=db_path)
                        else:
                            self._update_gift_status(msg['id'], STATUS_MERGED, db_path=db_path)
                    result.append(best)

        result.sort(key=lambda x: x.get('_total_diamond', 0), reverse=True)
        return result

    def _create_merged_message(self, messages: List[Dict]) -> Dict:
        first_msg = messages[0]
        gift_list = []
        total_diamond = 0

        for msg in messages:
            gift_name = msg.get('giftname', '')
            gift_count = int(msg.get('giftcount', 1))
            diamond = int(msg.get('giftdiamond', 0))
            gift_list.append(f"{gift_name}x{gift_count}")
            total_diamond += diamond * gift_count

        merged_msg = {
            'id': first_msg['id'],
            'room': first_msg.get('room', ''),
            'name': first_msg.get('name', 'unknown'),
            'giftname': '、'.join(gift_list),
            'giftcount': 1,
            'giftdiamond': total_diamond,
            'created_at': first_msg.get('created_at'),
            'merged_ids': [m['id'] for m in messages],
            'is_merged': True,
            '_db_path': first_msg.get('_db_path'),
            '_total_diamond': total_diamond
        }
        return merged_msg

    # ==================== Generation Thread Pool ====================

    def _generation_worker(self, worker_id: int):
        self.logger.info(f"Generation Worker-{worker_id} 启动")
        while self.running:
            try:
                msg_data = self._generation_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._generate_for_message(msg_data)
            except Exception as e:
                self.logger.error(f"Generation Worker-{worker_id} 异常: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
        self.logger.info(f"Generation Worker-{worker_id} 停止")

    def _generate_for_message(self, msg_data: Dict):
        msg_id = msg_data['id']
        user = msg_data.get('name', 'unknown')
        gift_name = msg_data.get('giftname', '')
        gift_count = int(msg_data.get('giftcount', 1))
        diamond_per_gift = int(msg_data.get('giftdiamond', 0))
        total_diamond = diamond_per_gift * gift_count
        room_ip = msg_data.get('room', '')
        room_id = msg_data.get('room_id')
        merged_ids = msg_data.get('merged_ids', [])
        db_path = msg_data.get('_db_path')

        self.logger.info(f"[Gen] 开始处理消息: id={msg_id}, user={user}, gift={gift_name}, diamond={total_diamond}")

        room_config = self._get_room_config_cached(room_ip) if room_ip else {'voice_id': None, 'ai_thank_enabled': False, 'thank_value': 0, 'ai_prompt': None}
        room_thank_value = room_config.get('thank_value', 0)

        if total_diamond < room_thank_value:
            self.logger.info(f"[Gen] 消息 {msg_id} 钻石数{total_diamond}低于答谢价值{room_thank_value}，跳过")
            self._update_gift_status(msg_id, STATUS_SKIPPED_DIAMOND, db_path=db_path)
            if merged_ids:
                self._batch_update_status(merged_ids, STATUS_MERGED, db_path=db_path)
            return

        if self.user_thank_cooldown > 0 and room_ip and user and gift_name:
            cooldown_key = (room_ip, user, gift_name)
            last_thank_time = self._user_last_thank.get(cooldown_key, 0)
            now = time.time()
            if now - last_thank_time < self.user_thank_cooldown:
                self.logger.info(f"[Gen] 消息 {msg_id} 用户 {user} 在房间 {room_ip} 送 {gift_name} 冷却中，跳过")
                self._update_gift_status(msg_id, STATUS_COOLDOWN, db_path=db_path)
                if merged_ids:
                    self._batch_update_status(merged_ids, STATUS_COOLDOWN, db_path=db_path)
                return

        if not room_config.get('ai_thank_enabled'):
            self.logger.info(f"[Gen] 消息 {msg_id} 房间 {room_ip} AI答谢未启用，跳过")
            self._update_gift_status(msg_id, STATUS_DISABLED, db_path=db_path)
            if merged_ids:
                self._batch_update_status(merged_ids, STATUS_DISABLED, db_path=db_path)
            return

        thank_text = None
        if self.text_generator:
            try:
                value_level = self._get_gift_value_level(gift_name, total_diamond)
                room_prompt = room_config.get('ai_prompt')

                thank_text = self.text_generator.generate_text(
                    user=user,
                    gift_name=gift_name,
                    count=gift_count,
                    diamond_count=total_diamond,
                    value_level=value_level,
                    custom_prompt=room_prompt,
                    msg_id=msg_id
                )
            except Exception as e:
                self.logger.error(f"[Gen] 消息 {msg_id} 文字生成异常: {e}")

        if not thank_text:
            self.logger.warning(f"[Gen] 消息 {msg_id} 文字生成失败，跳过")
            self._update_gift_status(msg_id, STATUS_COMPLETED, db_path=db_path)
            if merged_ids:
                self._batch_update_status(merged_ids, STATUS_MERGED, db_path=db_path)
            return

        if merged_ids:
            self._batch_update_status(merged_ids, STATUS_MERGED, db_path=db_path)

        if self.user_thank_cooldown > 0 and room_ip and user and gift_name:
            self._user_last_thank[(room_ip, user, gift_name)] = time.time()

        self._update_gift_status(msg_id, STATUS_TEXT_GENERATED, txt=thank_text, db_path=db_path)

        if not self.voice_generator or not self.voice_generator.is_enabled():
            self.logger.info(f"[Gen] 消息 {msg_id} 语音生成器不可用，仅保存文字")
            self._update_gift_status(msg_id, STATUS_COMPLETED, txt=thank_text, db_path=db_path)
            return

        room_voice_id = room_config.get('voice_id')
        if not room_voice_id:
            self.logger.warning(f"[Gen] 消息 {msg_id} 房间 {room_ip} 未完成音频复刻，仅保存文字")
            self._update_gift_status(msg_id, STATUS_COMPLETED, txt=thank_text, db_path=db_path)
            return

        output_filename = self._generate_filename(room_id, msg_id)
        output_path = os.path.join(self.base_dir, 'wav', output_filename)
        relative_path = self._get_relative_path(output_path)

        wav_success = False
        try:
            wav_success = self.voice_generator.generate_voice_file(thank_text, output_path, room_voice_id)
        except Exception as e:
            self.logger.error(f"[Gen] 消息 {msg_id} 语音文件生成异常: {e}")

        if not wav_success:
            self.logger.warning(f"[Gen] 消息 {msg_id} 语音文件生成失败，仅保存文字")
            self._update_gift_status(msg_id, STATUS_COMPLETED, txt=thank_text, db_path=db_path)
            return

        self._update_gift_status(msg_id, STATUS_VOICE_GENERATED, txt=thank_text, db_path=db_path)

        playback_item = {
            'msg_id': msg_id,
            'room_ip': room_ip,
            'wav_path': relative_path,
            'txt': thank_text,
            'db_path': db_path
        }
        self._enqueue_playback(room_ip, playback_item)
        self.logger.info(f"[Gen] 消息 {msg_id} 生成完成，已推入播放队列")

    # ==================== Playback Scheduler ====================

    def _enqueue_playback(self, room_ip: str, item: dict):
        with self._playback_lock:
            if room_ip not in self._playback_queues:
                self._playback_queues[room_ip] = Queue()
            self._playback_queues[room_ip].put(item)

            if room_ip not in self._playback_threads or not self._playback_threads[room_ip].is_alive():
                t = threading.Thread(target=self._playback_worker, args=(room_ip,), daemon=True, name=f"Playback-{room_ip}")
                t.start()
                self._playback_threads[room_ip] = t

    def _playback_worker(self, room_ip: str):
        self.logger.info(f"[Playback] 房间 {room_ip} 播放线程启动")
        q = self._playback_queues.get(room_ip)
        if not q:
            return

        while self.running:
            try:
                item = q.get(timeout=60)
            except queue.Empty:
                break

            try:
                self._play_one_item(room_ip, item)
            except Exception as e:
                self.logger.error(f"[Playback] 房间 {room_ip} 播放异常: {e}")
                import traceback
                self.logger.error(traceback.format_exc())

        with self._playback_lock:
            if room_ip in self._playback_threads and self._playback_threads[room_ip] is threading.current_thread():
                del self._playback_threads[room_ip]
        self.logger.info(f"[Playback] 房间 {room_ip} 播放线程停止")

    def _play_one_item(self, room_ip: str, item: dict):
        msg_id = item['msg_id']
        wav_path = item['wav_path']
        txt = item['txt']
        db_path = item['db_path']

        room_config = self._get_room_config_cached(room_ip) if room_ip else {}
        if not room_config.get('ai_thank_enabled'):
            self.logger.info(f"[Playback] 房间 {room_ip} AI答谢已关闭，跳过播放 msg_id={msg_id}")
            self._update_gift_status(msg_id, STATUS_DISABLED, txt=txt, db_path=db_path)
            return

        # 检查播放间隔 - 非阻塞方式
        now = time.time()
        last_play = self._room_last_play_time.get(room_ip, 0)
        wait = self.room_thank_interval - (now - last_play)
        if wait > 0:
            self.logger.info(f"[Playback] 房间 {room_ip} 等待答谢间隔 {wait:.1f}s，将任务重新入队")
            # 将任务重新放入队列尾部，让其他房间的任务有机会执行
            with self._playback_lock:
                if room_ip in self._playback_queues:
                    self._playback_queues[room_ip].put(item)
            # 短暂休眠，避免 CPU 占用过高
            time.sleep(0.1)
            return

        self._update_gift_status(msg_id, STATUS_PLAYING, txt=txt, db_path=db_path)

        if not self.ai_voice_player:
            self.logger.warning(f"[Playback] ai_voice_player 不可用，跳过播放")
            self._update_gift_status(msg_id, STATUS_COMPLETED, txt=txt, db_path=db_path)
            return

        room = None
        for r in self.ai_voice_player.device_manager.rooms.values():
            if r.ip == room_ip:
                room = r
                break

        if not room:
            self.logger.error(f"[Playback] 找不到房间 {room_ip}")
            self._update_gift_status(msg_id, STATUS_COMPLETED, txt=txt, db_path=db_path)
            return

        absolute_wav = self._get_absolute_wav_path(wav_path)
        if not os.path.exists(absolute_wav):
            self.logger.error(f"[Playback] wav文件不存在: {absolute_wav}")
            self._update_gift_status(msg_id, STATUS_COMPLETED, txt=txt, db_path=db_path)
            return

        play_success = False
        try:
            play_success = self.ai_voice_player.play_wav_file(room.id, absolute_wav)
        except Exception as e:
            self.logger.error(f"[Playback] 播放异常: {e}")

        self._room_last_play_time[room_ip] = time.time()
        self._update_gift_status(msg_id, STATUS_COMPLETED, txt=txt, db_path=db_path)
        self.logger.info(f"[Playback] 消息 {msg_id} 播放完成, success={play_success}")

    # ==================== Start / Stop ====================

    def start(self):
        if self.running:
            self.logger.warning("AI管理器已经在运行中")
            return

        if not self.license_id:
            self.logger.warning("license_id 未设置，AI管理器不会处理消息")

        self.running = True

        self._scanner_thread = threading.Thread(target=self._scanner_loop, daemon=True, name="AIScanner")
        self._scanner_thread.start()

        self._merge_thread = threading.Thread(target=self._merge_loop, daemon=True, name="AIMerge")
        self._merge_thread.start()

        self._gen_threads = []
        for i in range(self.generator_pool_size):
            t = threading.Thread(target=self._generation_worker, args=(i,), daemon=True, name=f"AIGen-{i}")
            t.start()
            self._gen_threads.append(t)

        self.logger.info(f"AI管理器已启动 (pool={self.generator_pool_size}, merge_window={self.merge_window}s, cache_ttl={self.room_config_cache_ttl}s)")

    def notify_new_gifts(self):
        self._scan_event.set()

    def cancel_room_tasks(self, room_ip: str):
        """关闭AI答谢时，清空该房间所有待处理任务"""
        self.logger.info(f"[Cancel] 开始清空房间 {room_ip} 的待处理任务")

        with self._playback_lock:
            q = self._playback_queues.get(room_ip)
            if q:
                disabled_ids = []
                while not q.empty():
                    try:
                        item = q.get_nowait()
                        disabled_ids.append(item['msg_id'])
                    except queue.Empty:
                        break
                for msg_id in disabled_ids:
                    self._update_gift_status(msg_id, STATUS_DISABLED, db_path=None)
                self.logger.info(f"[Cancel] 清空房间 {room_ip} 播放队列，共 {len(disabled_ids)} 条")

        remaining = []
        while not self._generation_queue.empty():
            try:
                item = self._generation_queue.get_nowait()
                if item.get('room') == room_ip:
                    self._update_gift_status(item['id'], STATUS_DISABLED, db_path=item.get('_db_path'))
                else:
                    remaining.append(item)
            except queue.Empty:
                break
        for item in remaining:
            self._generation_queue.put(item)

        self._room_config_cache.pop(room_ip, None)
        self.logger.info(f"[Cancel] 房间 {room_ip} 任务清空完成")

    def refresh_room_config(self, room_ip: str):
        """强制刷新房间配置缓存"""
        self._room_config_cache.pop(room_ip, None)
        self.logger.info(f"[Refresh] 已刷新房间 {room_ip} 的配置缓存")

    def stop(self):
        if not self.running:
            return
        self.running = False
        self._scan_event.set()
        self.logger.info("AI管理器已停止")

    def set_license_id(self, license_id: int):
        self.license_id = license_id
        self.logger.info(f"AI管理器 license_id 已设置: {license_id}")

    def set_ai_voice_player(self, ai_voice_player):
        self.ai_voice_player = ai_voice_player
