import threading
import time
import sqlite3
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional, List

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger('IoT_Voice_Control')


class WSMessageReceiver:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WSMessageReceiver, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self.db_manager = None
        self.ws_url = "ws://localhost:8888"
        self.running = False
        self.thread = None
        self.message_count = 0
        self._room_live_url_map = {}
        self._room_map_lock = threading.Lock()
        self._write_buffer: List[Dict] = []
        self._buffer_lock = threading.Lock()
        self._flush_interval = 0.2
        self._last_flush_time = 0
        self._cleanup_interval = 600
        self._last_cleanup_time = 0
        self._reconnect_interval = 3.0
        self._max_messages_count = 300
        self._max_gifts_count = 300
        self._on_data_flushed_callback = None

    def configure(self, db_manager=None, ws_url: str = None, on_data_flushed=None, config=None):
        if db_manager:
            self.db_manager = db_manager
        if ws_url:
            self.ws_url = ws_url
        if on_data_flushed:
            self._on_data_flushed_callback = on_data_flushed
        if config:
            try:
                self._max_messages_count = config.getint('database', 'max_messages_count', fallback=300)
                self._max_gifts_count = config.getint('database', 'max_gifts_count', fallback=300)
            except Exception:
                pass
        self._refresh_room_mapping()

    def _refresh_room_mapping(self):
        if not self.db_manager:
            return
        try:
            rooms = self.db_manager.get_all_rooms()
            new_map = {}
            for room in rooms:
                room_id = room['id']
                live_url = room.get('live_url', '')
                if live_url:
                    new_map[live_url] = room_id
            with self._room_map_lock:
                self._room_live_url_map = new_map
            logger.info(f"WSMessageReceiver: 已刷新房间映射, {len(new_map)}个房间有直播地址")
        except Exception as e:
            logger.error(f"WSMessageReceiver: 刷新房间映射失败: {e}")

    def _match_room(self, message: Dict) -> Optional[int]:
        data = message.get('Data', {})
        room_id_val = data.get('RoomId') or data.get('roomId')
        web_room_id_val = data.get('WebRoomId') or data.get('webRoomId')

        logger.info(f"WSMessageReceiver: 开始匹配房间, RoomId={room_id_val}, WebRoomId={web_room_id_val}")
        
        if room_id_val or web_room_id_val:
            with self._room_map_lock:
                logger.info(f"WSMessageReceiver: 当前房间映射表: {self._room_live_url_map}")
                for live_url, room_id in self._room_live_url_map.items():
                    if room_id_val and str(room_id_val) in str(live_url):
                        logger.info(f"WSMessageReceiver: 匹配成功 (RoomId), room_id={room_id}, live_url={live_url}")
                        return room_id
                    if web_room_id_val and str(web_room_id_val) in str(live_url):
                        logger.info(f"WSMessageReceiver: 匹配成功 (WebRoomId), room_id={room_id}, live_url={live_url}")
                        return room_id

        logger.info(f"WSMessageReceiver: 未匹配到房间")
        return None

    def start(self):
        if self.running:
            return
        if not WEBSOCKETS_AVAILABLE:
            logger.error("WSMessageReceiver: websockets库不可用，无法启动")
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="WSMessageReceiver")
        self.thread.start()
        logger.info(f"WSMessageReceiver: 已启动, ws_url={self.ws_url}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        self._flush_buffer()
        logger.info("WSMessageReceiver: 已停止")

    def _run_loop(self):
        while self.running:
            try:
                asyncio.run(self._ws_connect())
            except Exception as e:
                logger.error(f"WSMessageReceiver: 连接异常: {e}")
            if self.running:
                time.sleep(self._reconnect_interval)

    async def _ws_connect(self):
        try:
            async with websockets.connect(self.ws_url) as ws:
                logger.info(f"WSMessageReceiver: 已连接到 {self.ws_url}")
                while self.running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        message = json.loads(raw)
                        self._on_message(message)
                    except asyncio.TimeoutError:
                        self._try_flush()
                        self._try_cleanup()
                        continue
                    except json.JSONDecodeError as e:
                        logger.warning(f"WSMessageReceiver: JSON解析失败: {e}")
        except Exception as e:
            logger.warning(f"WSMessageReceiver: WebSocket连接失败: {e}")

    def _on_message(self, message: Dict):
        self.message_count += 1
        room_id = self._match_room(message)
        
        if room_id is None:
            logger.debug(f"WSMessageReceiver: 未匹配到房间，跳过消息")
            return
        
        # 检查房间是否已关闭
        if self.db_manager:
            try:
                with self.db_manager._get_connection() as conn:
                    enabled_row = conn.execute("SELECT enabled FROM rooms WHERE id = ?", (room_id,)).fetchone()
                    if enabled_row and not bool(enabled_row[0]):
                        return
            except Exception:
                pass
            
        msg_type = message.get('Type') or message.get('type', 0)
        data = message.get('Data', {})
        platform = message.get('Platform', '')

        try:
            if msg_type == 3:
                self._buffer_chat_message(room_id, platform, data, message)
            elif msg_type == 4:
                self._buffer_like_message(room_id, platform, data, message)
            elif msg_type == 6:
                self._buffer_gift_message(room_id, platform, data, message)
            elif msg_type == 12:
                self._buffer_room_stats(room_id, data, message)
            else:
                self._buffer_other_message(room_id, platform, msg_type, data, message)
        except Exception as e:
            logger.error(f"WSMessageReceiver: 处理消息失败: {e}")

        now = time.time()
        if now - self._last_flush_time >= self._flush_interval:
            self._flush_buffer()

    def _buffer_chat_message(self, room_id: int, platform: str, data: Dict, raw: Dict):
        user = data.get('User', {})
        self._write_buffer.append({
            'table': 'messages',
            'room_id': room_id,
            'data': {
                'type': 'msg',
                'platform': platform,
                'user_id': str(user.get('Id', '')),
                'nickname': user.get('NickName', ''),
                'content': data.get('Content', ''),
                'room_id_ws': str(data.get('RoomId', '') or ''),
                'web_room_id': str(data.get('WebRoomId', '') or ''),
                'triggered': 0,
                'status': 0,
                'txt': '',
                'raw_data': json.dumps(raw, ensure_ascii=False),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'time_span': data.get('TimeSpan', 0)
            }
        })

    def _buffer_like_message(self, room_id: int, platform: str, data: Dict, raw: Dict):
        user = data.get('User', {})
        gift_count = data.get('LikeCount', 1)
        content = f"点了{gift_count}个赞"
        
        self._write_buffer.append({
            'table': 'gifts',
            'room_id': room_id,
            'data': {
                'type': 'gif',
                'platform': platform,
                'user_id': str(user.get('Id', '')),
                'nickname': user.get('NickName', ''),
                'content': content,
                'gift_id': '0',
                'gift_name': '点赞',
                'gift_count': gift_count,
                'gift_price': 0,
                'gift_image': '',
                'combo': 0,
                'combo_count': 0,
                'room_id_ws': str(data.get('RoomId', '') or ''),
                'web_room_id': str(data.get('WebRoomId', '') or ''),
                'triggered': 0,
                'status': 0,
                'txt': '',
                'raw_data': json.dumps(raw, ensure_ascii=False),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'time_span': data.get('TimeSpan', 0)
            }
        })

    def _buffer_gift_message(self, room_id: int, platform: str, data: Dict, raw: Dict):
        user = data.get('User', {})
        gift = data.get('Gift') or {}
        gift_name = data.get('GiftName', '') or gift.get('Name', '')
        gift_count = data.get('GiftCount', 1)
        gift_price = data.get('GiftPrice', 0) or gift.get('Price', 0)
        content = f"送了{gift_count}个{gift_name}" if gift_name and gift_count else ""

        self._write_buffer.append({
            'table': 'gifts',
            'room_id': room_id,
            'data': {
                'type': 'gif',
                'platform': platform,
                'user_id': str(user.get('Id', '')),
                'nickname': user.get('NickName', ''),
                'content': content,
                'gift_id': str(data.get('GiftId', '') or gift.get('Id', '')),
                'gift_name': gift_name,
                'gift_count': gift_count,
                'gift_price': gift_price,
                'gift_image': data.get('GiftImage', '') or gift.get('Image', ''),
                'combo': 1 if data.get('Combo', False) else 0,
                'combo_count': data.get('ComboCount', 0),
                'room_id_ws': str(data.get('RoomId', '') or ''),
                'web_room_id': str(data.get('WebRoomId', '') or ''),
                'triggered': 0,
                'status': 0,
                'txt': '',
                'raw_data': json.dumps(raw, ensure_ascii=False),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'time_span': data.get('TimeSpan', 0)
            }
        })

    def _buffer_room_stats(self, room_id: int, data: Dict, raw: Dict):
        self._write_buffer.append({
            'table': 'room_stats',
            'room_id': room_id,
            'data': {
                'online_count': str(data.get('CurrentlyOnlineCount', '')),
                'popularity_count': str(data.get('TotalPopularityCount', '')),
                'room_id_ws': str(data.get('RoomId', '') or ''),
                'web_room_id': str(data.get('WebRoomId', '') or ''),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'time_span': data.get('TimeSpan', 0)
            }
        })

    def _buffer_other_message(self, room_id: int, platform: str, msg_type: int, data: Dict, raw: Dict):
        user = data.get('User', {})
        self._write_buffer.append({
            'table': 'messages',
            'room_id': room_id,
            'data': {
                'type': f'type_{msg_type}',
                'platform': platform,
                'user_id': str(user.get('Id', '')),
                'nickname': user.get('NickName', ''),
                'content': data.get('Content', ''),
                'room_id_ws': str(data.get('RoomId', '') or ''),
                'web_room_id': str(data.get('WebRoomId', '') or ''),
                'triggered': 0,
                'status': 0,
                'txt': '',
                'raw_data': json.dumps(raw, ensure_ascii=False),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'time_span': data.get('TimeSpan', 0)
            }
        })

    def _try_flush(self):
        now = time.time()
        if now - self._last_flush_time >= self._flush_interval:
            self._flush_buffer()

    def _flush_buffer(self):
        with self._buffer_lock:
            if not self._write_buffer:
                return
            buffer = self._write_buffer[:]
            self._write_buffer.clear()

        self._last_flush_time = time.time()

        room_groups: Dict[int, List[Dict]] = {}
        for item in buffer:
            rid = item['room_id']
            if rid not in room_groups:
                room_groups[rid] = []
            room_groups[rid].append(item)

        flushed_data = {}
        for room_id, items in room_groups.items():
            try:
                self._write_to_room_db(room_id, items)
                gifts = [item for item in items if item['table'] == 'gifts']
                messages = [item for item in items if item['table'] == 'messages']
                stats = [item for item in items if item['table'] == 'room_stats']
                if gifts or messages or stats:
                    flushed_data[room_id] = {
                        'gifts': gifts,
                        'messages': messages,
                        'stats': stats
                    }
            except Exception as e:
                logger.error(f"WSMessageReceiver: 写入房间{room_id}数据库失败: {e}")

        if flushed_data and self._on_data_flushed_callback:
            try:
                self._on_data_flushed_callback(flushed_data)
            except Exception as e:
                logger.error(f"WSMessageReceiver: 数据刷新回调失败: {e}")

    def _write_to_room_db(self, room_id: int, items: List[Dict]):
        if not self.db_manager:
            return
        db_path = self.db_manager.ensure_room_db(room_id)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            for item in items:
                table = item['table']
                data = item['data']
                if table == 'messages':
                    cursor = conn.execute("""
                        INSERT INTO messages (type, platform, user_id, nickname, content,
                            room_id, web_room_id, triggered, status, txt, raw_data, created_at, time_span)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data['type'], data['platform'], data['user_id'], data['nickname'],
                        data['content'], data['room_id_ws'], data['web_room_id'],
                        data['triggered'], data['status'], data['txt'],
                        data['raw_data'], data['created_at'], data['time_span']
                    ))
                    data['db_id'] = cursor.lastrowid
                elif table == 'gifts':
                    cursor = conn.execute("""
                        INSERT INTO gifts (type, platform, user_id, nickname, content,
                            gift_id, gift_name, gift_count, gift_price, gift_image,
                            combo, combo_count, room_id, web_room_id,
                            triggered, status, txt, raw_data, created_at, time_span)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data['type'], data['platform'], data['user_id'], data['nickname'],
                        data['content'], data['gift_id'], data['gift_name'],
                        data['gift_count'], data['gift_price'], data['gift_image'],
                        data['combo'], data['combo_count'],
                        data['room_id_ws'], data['web_room_id'],
                        data['triggered'], data['status'], data['txt'],
                        data['raw_data'], data['created_at'], data['time_span']
                    ))
                    data['db_id'] = cursor.lastrowid
                elif table == 'room_stats':
                    conn.execute("""
                        INSERT INTO room_stats (online_count, popularity_count,
                            room_id, web_room_id, created_at, time_span)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        data['online_count'], data['popularity_count'],
                        data['room_id_ws'], data['web_room_id'],
                        data['created_at'], data['time_span']
                    ))
                    # 只保留最近10条 room_stats 记录
                    conn.execute("""
                        DELETE FROM room_stats 
                        WHERE id NOT IN (
                            SELECT id FROM room_stats 
                            ORDER BY created_at DESC 
                            LIMIT 10
                        )
                    """)
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"WSMessageReceiver: 写入房间{room_id}失败: {e}")
            raise
        finally:
            conn.close()

    def _try_cleanup(self):
        now = time.time()
        if now - self._last_cleanup_time < self._cleanup_interval:
            return
        self._last_cleanup_time = now
        self._cleanup_old_data()

    def _cleanup_old_data(self):
        if not self.db_manager:
            return
        try:
            rooms = self.db_manager.get_all_rooms()
            for room in rooms:
                room_id = room['id']
                db_path = self.db_manager.get_room_db_path(room_id)
                if not db_path:
                    continue
                try:
                    conn = sqlite3.connect(db_path)
                    conn.execute("PRAGMA journal_mode=WAL")
                    cursor = conn.cursor()

                    cursor.execute(
                        "DELETE FROM messages WHERE id NOT IN (SELECT id FROM messages ORDER BY id DESC LIMIT ?)",
                        (self._max_messages_count,)
                    )
                    cursor.execute(
                        "DELETE FROM gifts WHERE id NOT IN (SELECT id FROM gifts ORDER BY id DESC LIMIT ?)",
                        (self._max_gifts_count,)
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.error(f"WSMessageReceiver: 清理房间{room_id}数据失败: {e}")
            logger.info("WSMessageReceiver: 数据翻转清理完成")
        except Exception as e:
            logger.error(f"WSMessageReceiver: 数据清理失败: {e}")

    def get_stats(self) -> Dict:
        return {
            'running': self.running,
            'ws_url': self.ws_url,
            'message_count': self.message_count,
            'buffer_size': len(self._write_buffer),
            'room_mapping': dict(self._room_live_url_map)
        }

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            if cls._instance:
                cls._instance.stop()
            cls._instance = None
