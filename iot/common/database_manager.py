import sqlite3
import os
import sys
import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import json
from datetime import datetime
import configparser


def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DatabaseManager:
    _instance = None
    _db_path = None
    _config_cache = {}
    _ini_config = None
    _room_db_paths = {}
    _device_room_map = {}

    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path=None):
        if self._db_path is None:
            self._db_path = self._find_global_db_path()

        if not self._config_cache:
            self._init_db()
            self._discover_room_dbs()
            self._build_device_room_map()
            self._load_configs_to_cache()

    def _find_global_db_path(self):
        base_dir = _get_base_dir()
        db_dir = os.path.join(base_dir, 'iot', 'database')
        if os.path.exists(os.path.join(db_dir, 'config.db')):
            return os.path.join(db_dir, 'config.db')

        db_dir = os.path.join(base_dir, 'database')
        if os.path.exists(os.path.join(db_dir, 'config.db')):
            return os.path.join(db_dir, 'config.db')

        try:
            from utils.path_helper import PathHelper
            path = PathHelper.get_config_db_path()
            if os.path.exists(path):
                return path
        except ImportError:
            pass

        possible_paths = [
            'config.db',
            '../config.db'
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return 'config.db'

    def _find_ini_path(self):
        try:
            from utils.path_helper import PathHelper
            return PathHelper.get_config_ini_path()
        except ImportError:
            pass

        possible_paths = [
            'config.ini',
            '../config.ini',
            '../../config.ini'
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return 'config.ini'

    def _discover_room_dbs(self):
        base_dir = _get_base_dir()
        search_dirs = [
            os.path.join(base_dir, 'iot', 'database'),
            os.path.join(base_dir, 'database'),
        ]
        for db_dir in search_dirs:
            if not os.path.exists(db_dir):
                continue
            for f in os.listdir(db_dir):
                if not f.endswith('.db'):
                    continue
                match = re.match(r'room_(\d+)\.db$', f)
                if match:
                    room_id = int(match.group(1))
                    db_path = os.path.join(db_dir, f)
                    self._room_db_paths[room_id] = db_path
                    self._migrate_room_db(db_path)
            if self._room_db_paths:
                break

    def _build_device_room_map(self):
        self._device_room_map = {}
        for room_id, db_path in self._room_db_paths.items():
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
                if cursor.fetchone():
                    cursor.execute("SELECT id FROM devices")
                    for row in cursor.fetchall():
                        self._device_room_map[row[0]] = room_id
                conn.close()
            except Exception:
                pass

    def get_room_db_path(self, room_id: int) -> Optional[str]:
        if room_id in self._room_db_paths:
            return self._room_db_paths[room_id]

        base_dir = _get_base_dir()
        search_dirs = [
            os.path.join(base_dir, 'iot', 'database'),
            os.path.join(base_dir, 'database'),
        ]
        for db_dir in search_dirs:
            db_path = os.path.join(db_dir, f'room_{room_id}.db')
            if os.path.exists(db_path):
                self._room_db_paths[room_id] = db_path
                return db_path
        return None

    def ensure_room_db(self, room_id: int) -> str:
        db_path = self.get_room_db_path(room_id)
        if db_path and os.path.exists(db_path):
            self._migrate_room_db(db_path)
            return db_path

        base_dir = _get_base_dir()
        db_dir = os.path.join(base_dir, 'database')
        if not os.path.exists(db_dir):
            db_dir = os.path.join(base_dir, 'iot', 'database')
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, f'room_{room_id}.db')
        self._init_room_db(db_path)
        self._room_db_paths[room_id] = db_path
        return db_path

    def _migrate_room_db(self, db_path: str):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {r[0] for r in cursor.fetchall()}
            conn.close()

            required_tables = {'devices', 'gift_triggers', 'gift_trigger_logs', 'messages', 'gifts', 'room_stats'}
            missing_tables = required_tables - existing_tables
            if missing_tables:
                self._init_room_db(db_path)
        except Exception as e:
            print(f"迁移房间数据库失败: {e}")

    def _init_room_db(self, db_path: str):
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                label TEXT NOT NULL,
                pin INTEGER NOT NULL,
                trigger_on_duration INTEGER DEFAULT 3,
                trigger_off_duration INTEGER DEFAULT 1,
                enabled BOOLEAN DEFAULT 0,
                gift_event TEXT,
                trigger_remaining_count INTEGER DEFAULT 0,
                trigger_state INTEGER DEFAULT 0,
                last_trigger_time TEXT,
                next_trigger_time TEXT,
                trigger_sound BOOLEAN DEFAULT 0,
                trigger_sound_delay REAL DEFAULT 0,
                loop_action TEXT DEFAULT 'manual',
                loop_minute TEXT DEFAULT '',
                loop_duration REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS gift_triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                gift_name TEXT NOT NULL,
                trigger_count INTEGER DEFAULT 1,
                device_type TEXT DEFAULT 'main',
                device_config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS gift_trigger_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                device_name TEXT NOT NULL,
                gift_name TEXT NOT NULL,
                gift_count INTEGER NOT NULL DEFAULT 0,
                trigger_count INTEGER NOT NULL DEFAULT 0,
                original_count INTEGER NOT NULL DEFAULT 0,
                remaining_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL DEFAULT 'msg',
                platform TEXT DEFAULT '',
                user_id TEXT DEFAULT '',
                nickname TEXT DEFAULT '',
                content TEXT DEFAULT '',
                room_id TEXT DEFAULT '',
                web_room_id TEXT DEFAULT '',
                triggered INTEGER DEFAULT 0,
                status INTEGER DEFAULT 0,
                txt TEXT DEFAULT '',
                raw_data TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                time_span INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS gifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL DEFAULT 'gif',
                platform TEXT DEFAULT '',
                user_id TEXT DEFAULT '',
                nickname TEXT DEFAULT '',
                content TEXT DEFAULT '',
                gift_id TEXT DEFAULT '',
                gift_name TEXT DEFAULT '',
                gift_count INTEGER DEFAULT 0,
                gift_price INTEGER DEFAULT 0,
                gift_image TEXT DEFAULT '',
                combo INTEGER DEFAULT 0,
                combo_count INTEGER DEFAULT 0,
                room_id TEXT DEFAULT '',
                web_room_id TEXT DEFAULT '',
                triggered INTEGER DEFAULT 0,
                status INTEGER DEFAULT 0,
                txt TEXT DEFAULT '',
                raw_data TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                time_span INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS room_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                online_count TEXT DEFAULT '',
                popularity_count TEXT DEFAULT '',
                room_id TEXT DEFAULT '',
                web_room_id TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                time_span INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_devices_room_id ON devices(room_id);
            CREATE INDEX IF NOT EXISTS idx_gift_trigger_logs_created_at ON gift_trigger_logs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_triggered ON messages(triggered);
            CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
            CREATE INDEX IF NOT EXISTS idx_gifts_created_at ON gifts(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_gifts_triggered ON gifts(triggered);
            CREATE INDEX IF NOT EXISTS idx_gifts_name ON gifts(gift_name);
            CREATE INDEX IF NOT EXISTS idx_room_stats_created_at ON room_stats(created_at DESC);
        """)
        conn.commit()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -2000")
        conn.execute("PRAGMA wal_autocheckpoint = 1000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def get_room_connection(self, room_id: int):
        db_path = self.get_room_db_path(room_id)
        if not db_path:
            raise ValueError(f"房间{room_id}的数据库不存在")
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -2000")
        conn.execute("PRAGMA wal_autocheckpoint = 1000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_room_id_by_device_id(self, device_id: int) -> Optional[int]:
        return self._device_room_map.get(device_id)

    def refresh_device_room_map(self, room_id: int):
        db_path = self.get_room_db_path(room_id)
        if not db_path:
            return
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM devices")
            for row in cursor.fetchall():
                self._device_room_map[row[0]] = room_id
            conn.close()
        except Exception:
            pass

    def _init_db(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = f.read()
            with self._get_connection() as conn:
                conn.executescript(schema)
        else:
            self._create_default_schema()
        self._migrate_db()

    def _create_default_schema(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    port INTEGER NOT NULL DEFAULT 8080,
                    online BOOLEAN DEFAULT 0,
                    rssi INTEGER DEFAULT -100,
                    sort_order INTEGER NOT NULL,
                    intercom_volume INTEGER DEFAULT 50,
                    last_seen REAL,
                    prompt TEXT DEFAULT '',
                    live_url TEXT DEFAULT '',
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    label TEXT NOT NULL,
                    pin INTEGER NOT NULL,
                    trigger_on_duration INTEGER DEFAULT 3,
                    trigger_off_duration INTEGER DEFAULT 1,
                    enabled BOOLEAN DEFAULT 0,
                    gift_event TEXT,
                    trigger_remaining_count INTEGER DEFAULT 0,
                    trigger_state INTEGER DEFAULT 0,
                    last_trigger_time TEXT,
                    next_trigger_time TEXT,
                    trigger_sound BOOLEAN DEFAULT 0,
                    trigger_sound_delay REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS gifts (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    value INTEGER NOT NULL,
                    level TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_devices_room_id ON devices(room_id);
                CREATE INDEX IF NOT EXISTS idx_rooms_sort_order ON rooms(sort_order);
                CREATE INDEX IF NOT EXISTS idx_rooms_online ON rooms(online);

                CREATE TABLE IF NOT EXISTS gift_trigger_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    device_name TEXT NOT NULL,
                    gift_name TEXT NOT NULL,
                    gift_count INTEGER NOT NULL DEFAULT 0,
                    trigger_count INTEGER NOT NULL DEFAULT 0,
                    original_count INTEGER NOT NULL DEFAULT 0,
                    remaining_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_gift_trigger_logs_room_id ON gift_trigger_logs(room_id);
                CREATE INDEX IF NOT EXISTS idx_gift_trigger_logs_created_at ON gift_trigger_logs(created_at DESC);

                CREATE TABLE IF NOT EXISTS system (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL UNIQUE,
                    config_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def _migrate_db(self):
        with self._get_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(rooms)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'live_url' not in columns:
                conn.execute("ALTER TABLE rooms ADD COLUMN live_url TEXT DEFAULT ''")
                print("数据库迁移: 已添加 live_url 字段到 rooms 表")

            if 'voice_status' not in columns:
                conn.execute("ALTER TABLE rooms ADD COLUMN voice_status BOOLEAN DEFAULT 0")
                print("数据库迁移: 已添加 voice_status 字段到 rooms 表")

            if 'enabled' not in columns:
                conn.execute("ALTER TABLE rooms ADD COLUMN enabled BOOLEAN DEFAULT 1")
                print("数据库迁移: 已添加 enabled 字段到 rooms 表")

            cursor = conn.execute("PRAGMA table_info(devices)")
            device_columns = [row[1] for row in cursor.fetchall()]

            if 'trigger_sound' not in device_columns:
                conn.execute("ALTER TABLE devices ADD COLUMN trigger_sound BOOLEAN DEFAULT 0")
                print("数据库迁移: 已添加 trigger_sound 字段到 devices 表")

            if 'loop_action' not in device_columns:
                conn.execute("ALTER TABLE devices ADD COLUMN loop_action TEXT DEFAULT 'manual'")
                print("数据库迁移: 已添加 loop_action 字段到 devices 表")

            if 'loop_minute' not in device_columns:
                conn.execute("ALTER TABLE devices ADD COLUMN loop_minute TEXT DEFAULT ''")
                print("数据库迁移: 已添加 loop_minute 字段到 devices 表")
            else:
                cursor = conn.execute("PRAGMA table_info(devices)")
                for col in cursor.fetchall():
                    if col[1] == 'loop_minute' and col[2].upper() == 'INTEGER':
                        conn.execute("CREATE TABLE IF NOT EXISTS devices_backup AS SELECT * FROM devices")
                        conn.execute("DROP TABLE devices")
                        conn.execute("""
                            CREATE TABLE devices (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                room_id INTEGER NOT NULL,
                                name TEXT NOT NULL,
                                label TEXT NOT NULL,
                                pin INTEGER NOT NULL,
                                trigger_on_duration INTEGER DEFAULT 3,
                                trigger_off_duration INTEGER DEFAULT 1,
                                enabled BOOLEAN DEFAULT 0,
                                gift_event TEXT,
                                trigger_remaining_count INTEGER DEFAULT 0,
                                trigger_state INTEGER DEFAULT 0,
                                last_trigger_time TEXT,
                                next_trigger_time TEXT,
                                trigger_sound BOOLEAN DEFAULT 0,
                                trigger_sound_delay REAL DEFAULT 0,
                                loop_action TEXT DEFAULT 'manual',
                                loop_minute TEXT DEFAULT '',
                                loop_duration REAL DEFAULT 0.0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (room_id) REFERENCES rooms (id)
                            )
                        """)
                        conn.execute("""
                            INSERT INTO devices (id, room_id, name, label, pin, trigger_on_duration, trigger_off_duration,
                                enabled, gift_event, trigger_remaining_count, trigger_state, last_trigger_time,
                                next_trigger_time, trigger_sound, loop_action, loop_minute, loop_duration,
                                created_at, updated_at)
                            SELECT id, room_id, name, label, pin, trigger_on_duration, trigger_off_duration,
                                enabled, gift_event, trigger_remaining_count, trigger_state, last_trigger_time,
                                next_trigger_time, trigger_sound, loop_action, CAST(loop_minute AS TEXT), loop_duration,
                                created_at, updated_at
                            FROM devices_backup
                        """)
                        conn.execute("DROP TABLE devices_backup")
                        print("数据库迁移: loop_minute 字段已从 INTEGER 转换为 TEXT")
                        break

            if 'loop_duration' not in device_columns:
                conn.execute("ALTER TABLE devices ADD COLUMN loop_duration REAL DEFAULT 0.0")
                print("数据库迁移: 已添加 loop_duration 字段到 devices 表")

            if 'trigger_sound_delay' not in device_columns:
                conn.execute("ALTER TABLE devices ADD COLUMN trigger_sound_delay REAL DEFAULT 0")
                print("数据库迁移: 已添加 trigger_sound_delay 字段到 devices 表")

        for room_id, db_path in self._room_db_paths.items():
            try:
                room_conn = sqlite3.connect(db_path)
                room_cursor = room_conn.execute("PRAGMA table_info(devices)")
                room_device_columns = [row[1] for row in room_cursor.fetchall()]
                if 'trigger_sound_delay' not in room_device_columns:
                    room_conn.execute("ALTER TABLE devices ADD COLUMN trigger_sound_delay REAL DEFAULT 0")
                    room_conn.commit()
                    print(f"数据库迁移: 已添加 trigger_sound_delay 字段到房间{room_id}的 devices 表")

                room_cursor = room_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = [row[0] for row in room_cursor.fetchall()]

                if 'messages' not in existing_tables:
                    room_conn.executescript("""
                        CREATE TABLE IF NOT EXISTS messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            type TEXT NOT NULL DEFAULT 'msg',
                            platform TEXT DEFAULT '',
                            user_id TEXT DEFAULT '',
                            nickname TEXT DEFAULT '',
                            content TEXT DEFAULT '',
                            room_id TEXT DEFAULT '',
                            web_room_id TEXT DEFAULT '',
                            triggered INTEGER DEFAULT 0,
                            status INTEGER DEFAULT 0,
                            txt TEXT DEFAULT '',
                            raw_data TEXT DEFAULT '',
                            created_at TEXT DEFAULT '',
                            time_span INTEGER DEFAULT 0
                        );
                        CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);
                        CREATE INDEX IF NOT EXISTS idx_messages_triggered ON messages(triggered);
                        CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
                    """)
                    room_conn.commit()
                    print(f"数据库迁移: 已添加 messages 表到房间{room_id}")

                if 'gifts' not in existing_tables:
                    room_conn.executescript("""
                        CREATE TABLE IF NOT EXISTS gifts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            type TEXT NOT NULL DEFAULT 'gif',
                            platform TEXT DEFAULT '',
                            user_id TEXT DEFAULT '',
                            nickname TEXT DEFAULT '',
                            content TEXT DEFAULT '',
                            gift_id TEXT DEFAULT '',
                            gift_name TEXT DEFAULT '',
                            gift_count INTEGER DEFAULT 0,
                            gift_price INTEGER DEFAULT 0,
                            gift_image TEXT DEFAULT '',
                            combo INTEGER DEFAULT 0,
                            combo_count INTEGER DEFAULT 0,
                            room_id TEXT DEFAULT '',
                            web_room_id TEXT DEFAULT '',
                            triggered INTEGER DEFAULT 0,
                            status INTEGER DEFAULT 0,
                            txt TEXT DEFAULT '',
                            raw_data TEXT DEFAULT '',
                            created_at TEXT DEFAULT '',
                            time_span INTEGER DEFAULT 0
                        );
                        CREATE INDEX IF NOT EXISTS idx_gifts_created_at ON gifts(created_at DESC);
                        CREATE INDEX IF NOT EXISTS idx_gifts_triggered ON gifts(triggered);
                        CREATE INDEX IF NOT EXISTS idx_gifts_name ON gifts(gift_name);
                    """)
                    room_conn.commit()
                    print(f"数据库迁移: 已添加 gifts 表到房间{room_id}")

                if 'room_stats' not in existing_tables:
                    room_conn.executescript("""
                        CREATE TABLE IF NOT EXISTS room_stats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            online_count TEXT DEFAULT '',
                            popularity_count TEXT DEFAULT '',
                            room_id TEXT DEFAULT '',
                            web_room_id TEXT DEFAULT '',
                            created_at TEXT DEFAULT '',
                            time_span INTEGER DEFAULT 0
                        );
                        CREATE INDEX IF NOT EXISTS idx_room_stats_created_at ON room_stats(created_at DESC);
                    """)
                    room_conn.commit()
                    print(f"数据库迁移: 已添加 room_stats 表到房间{room_id}")

                room_conn.execute("PRAGMA journal_mode=WAL")
                room_conn.commit()
                room_conn.close()
            except Exception as e:
                print(f"数据库迁移: 房间{room_id}迁移失败: {e}")

    def _load_configs_to_cache(self):
        self._config_cache = {}
        self._load_ini_config()
        self._load_system_config_to_cache()
        rooms = self.get_all_rooms()
        self._config_cache['rooms'] = {'rooms': rooms}

    def _load_system_config_to_cache(self):
        if 'system_db' not in self._config_cache:
            self._config_cache['system_db'] = {}
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT config_key, config_value FROM system")
            rows = cursor.fetchall()
            for row in rows:
                self._config_cache['system_db'][row['config_key']] = row['config_value']

    def _load_ini_config(self):
        ini_path = self._find_ini_path()
        if self._ini_config is None:
            self._ini_config = configparser.ConfigParser(interpolation=None)
            self._ini_config.read(ini_path, encoding='utf-8')
        for section in self._ini_config.sections():
            if section not in self._config_cache:
                self._config_cache[section] = {}
            for key, value in self._ini_config.items(section):
                value = value.split('#')[0].strip()
                self._config_cache[section][key] = self._convert_ini_value(value)

    def _convert_ini_value(self, value: str) -> Any:
        value = value.strip()
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def get_room(self, room_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
            if row:
                room = dict(row)
                room['online'] = bool(room['online'])
                room['enabled'] = bool(room.get('enabled', 1))
                room['devices'] = self.get_room_devices(room_id)
                return room
        return None

    def get_all_rooms(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM rooms ORDER BY sort_order").fetchall()
            rooms = []
            for row in rows:
                room = dict(row)
                room['online'] = bool(room['online'])
                room['enabled'] = bool(room.get('enabled', 1))
                room['devices'] = self.get_room_devices(room['id'])
                rooms.append(room)
            return rooms

    def get_room_devices(self, room_id: int) -> List[Dict[str, Any]]:
        room_db_path = self.get_room_db_path(room_id)
        if room_db_path and os.path.exists(room_db_path):
            try:
                conn = sqlite3.connect(room_db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM devices WHERE room_id = ? ORDER BY id", (room_id,))
                rows = cursor.fetchall()
                conn.close()
                devices = []
                for row in rows:
                    device = dict(row)
                    device['enabled'] = bool(device['enabled'])
                    if 'trigger_sound' in device:
                        device['trigger_sound'] = bool(device['trigger_sound'])
                    devices.append(device)
                return devices
            except sqlite3.OperationalError:
                self._migrate_room_db(room_db_path)
                try:
                    conn = sqlite3.connect(room_db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM devices WHERE room_id = ? ORDER BY id", (room_id,))
                    rows = cursor.fetchall()
                    conn.close()
                    devices = []
                    for row in rows:
                        device = dict(row)
                        device['enabled'] = bool(device['enabled'])
                        if 'trigger_sound' in device:
                            device['trigger_sound'] = bool(device['trigger_sound'])
                        devices.append(device)
                    return devices
                except Exception:
                    return []

        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM devices WHERE room_id = ? ORDER BY id",
                (room_id,)
            ).fetchall()
            devices = []
            for row in rows:
                device = dict(row)
                device['enabled'] = bool(device['enabled'])
                if 'trigger_sound' in device:
                    device['trigger_sound'] = bool(device['trigger_sound'])
                devices.append(device)
            return devices

    def update_room(self, room_id: int, **kwargs):
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [room_id]
        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE rooms SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
        self._load_configs_to_cache()

    def update_device(self, device_id: int, room_id: int = None, **kwargs):
        if room_id is None:
            room_id = self._device_room_map.get(device_id)

        if room_id:
            room_db_path = self.get_room_db_path(room_id)
            if room_db_path and os.path.exists(room_db_path):
                return self._update_device_in_room_db(room_db_path, device_id, **kwargs)

        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [device_id]
        try:
            with self._get_connection() as conn:
                if 'enabled' in kwargs and kwargs['enabled'] == False:
                    result = conn.execute(
                        f"UPDATE devices SET {set_clause}, trigger_remaining_count = 0, trigger_state = 0, next_trigger_time = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        values
                    )
                elif 'trigger_off_duration' in kwargs and kwargs['trigger_off_duration'] == 0:
                    result = conn.execute(
                        f"UPDATE devices SET {set_clause}, trigger_remaining_count = 0, trigger_state = 0, next_trigger_time = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        values
                    )
                else:
                    result = conn.execute(
                        f"UPDATE devices SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        values
                    )
                if result.rowcount == 0:
                    return False
            self._load_configs_to_cache()
            return True
        except Exception as e:
            print(f"更新设备失败: {e}")
            return False

    def _update_device_in_room_db(self, db_path: str, device_id: int, **kwargs):
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [device_id]
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            if 'enabled' in kwargs and kwargs['enabled'] == False:
                cursor.execute(
                    f"UPDATE devices SET {set_clause}, trigger_remaining_count = 0, trigger_state = 0, next_trigger_time = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    values
                )
            elif 'trigger_off_duration' in kwargs and kwargs['trigger_off_duration'] == 0:
                cursor.execute(
                    f"UPDATE devices SET {set_clause}, trigger_remaining_count = 0, trigger_state = 0, next_trigger_time = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    values
                )
            else:
                cursor.execute(
                    f"UPDATE devices SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    values
                )
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            if affected == 0:
                return False
            self._load_configs_to_cache()
            return True
        except Exception as e:
            print(f"更新房间设备失败: {e}")
            return False

    def get_all_gifts(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM gifts ORDER BY id").fetchall()
            return [dict(row) for row in rows]

    def get_gift(self, gift_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM gifts WHERE id = ?", (gift_id,)).fetchone()
            return dict(row) if row else None

    def get(self, key: str, default=None) -> Any:
        keys = key.split('.')
        if len(keys) == 2:
            section, config_key = keys
            if section in self._config_cache and config_key in self._config_cache[section]:
                return self._config_cache[section][config_key]
        return default

    def get_system_config(self) -> Dict[str, Any]:
        return self._config_cache.get('system', {})

    def get_server_config(self) -> Dict[str, Any]:
        return self._config_cache.get('server', {})

    def get_audio_config(self) -> Dict[str, Any]:
        return self._config_cache.get('audio', {})

    def get_network_config_section(self) -> Dict[str, Any]:
        return self._config_cache.get('network', {})

    def get_rooms_config(self) -> List[Dict[str, Any]]:
        rooms_config = self._config_cache.get('rooms', {})
        if isinstance(rooms_config, dict) and 'rooms' in rooms_config:
            return rooms_config['rooms']
        return []

    def get_logging_config(self) -> Dict[str, Any]:
        return self._config_cache.get('logging', {})

    def get_performance_config(self) -> Dict[str, Any]:
        return self._config_cache.get('performance', {})

    def get_patrol_dialog_enabled(self) -> bool:
        value = self.get_system_db_config('patrol_dialog_enabled', 'true')
        return value.lower() == 'true' if isinstance(value, str) else bool(value)

    def get_current_intercom_room_id(self) -> int:
        value = self.get_system_db_config('current_intercom_room_id', '0')
        return int(value) if value else 0

    def set_system_config(self, key: str, value: Any) -> bool:
        ini_path = self._find_ini_path()
        try:
            config_ini = configparser.ConfigParser()
            config_ini.read(ini_path, encoding='utf-8')
            if not config_ini.has_section('system'):
                config_ini.add_section('system')
            if isinstance(value, bool):
                value_str = str(value).lower()
            else:
                value_str = str(value)
            config_ini.set('system', key, value_str)
            with open(ini_path, 'w', encoding='utf-8') as f:
                config_ini.write(f)
            self._load_configs_to_cache()
            return True
        except Exception as e:
            print(f"设置系统配置失败: {e}")
            return False

    def debug_print(self):
        print(f"=== 数据库配置调试信息 ===")
        print(f"配置键: {list(self._config_cache.keys())}")
        if 'system' in self._config_cache:
            print(f"system配置: {self._config_cache['system']}")
        print(f"===================")

    def get_system_db_config(self, key: str, default: Any = None) -> Any:
        return self._config_cache.get('system_db', {}).get(key, default)

    def get_all_system_db_configs(self) -> Dict[str, Any]:
        return self._config_cache.get('system_db', {}).copy()

    def set_system_db_config(self, key: str, value: Any) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO system (config_key, config_value, updated_at) 
                       VALUES (?, ?, CURRENT_TIMESTAMP)""",
                    (key, str(value))
                )
            if 'system_db' not in self._config_cache:
                self._config_cache['system_db'] = {}
            self._config_cache['system_db'][key] = str(value)
            return True
        except Exception as e:
            print(f"设置system配置失败: {e}")
            return False

    def reload(self):
        self._config_cache = {}
        self._ini_config = None
        self._discover_room_dbs()
        self._build_device_room_map()
        self._load_configs_to_cache()


def get_database_manager(db_path=None):
    return DatabaseManager(db_path)
