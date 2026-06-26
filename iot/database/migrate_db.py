import sqlite3
import os
import sys
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.path_helper import PathHelper


def get_room_db_schema():
    return """
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

    CREATE INDEX IF NOT EXISTS idx_devices_room_id ON devices(room_id);
    CREATE INDEX IF NOT EXISTS idx_gift_trigger_logs_created_at ON gift_trigger_logs(created_at DESC);
    """


def migrate():
    old_db_path = PathHelper.get_config_db_path()
    if not os.path.exists(old_db_path):
        print(f"[ERROR] 原始config.db不存在: {old_db_path}")
        return False

    db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database')
    os.makedirs(db_dir, exist_ok=True)

    new_config_db_path = os.path.join(db_dir, 'config.db')

    if os.path.exists(new_config_db_path):
        print(f"[INFO] database/config.db已存在，跳过迁移")
        return True

    backup_path = old_db_path + f'.bak_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    shutil.copy2(old_db_path, backup_path)
    print(f"[INFO] 已备份原始config.db到: {backup_path}")

    shutil.copy2(old_db_path, new_config_db_path)
    print(f"[INFO] 已复制config.db到: {new_config_db_path}")

    old_conn = sqlite3.connect(old_db_path)
    old_conn.row_factory = sqlite3.Row
    old_cursor = old_conn.cursor()

    old_cursor.execute("SELECT id, name, ip, port, sort_order FROM rooms ORDER BY sort_order")
    rooms = old_cursor.fetchall()

    if not rooms:
        print("[WARNING] 未找到任何房间配置")
        old_conn.close()
        return True

    room_table_migrated = False

    for room in rooms:
        room_id = room['id']
        room_name = room['name']
        room_db_path = os.path.join(db_dir, f'room_{room_id}.db')

        if os.path.exists(room_db_path):
            print(f"[INFO] room_{room_id}.db已存在，跳过: {room_name}")
            continue

        print(f"[INFO] 创建room_{room_id}.db: {room_name}")

        room_conn = sqlite3.connect(room_db_path)
        room_cursor = room_conn.cursor()
        room_cursor.executescript(get_room_db_schema())

        old_cursor.execute("SELECT * FROM devices WHERE room_id = ?", (room_id,))
        devices = old_cursor.fetchall()
        if devices:
            cols = [desc[0] for desc in old_cursor.description]
            placeholders = ', '.join(['?'] * len(cols))
            col_names = ', '.join(cols)
            for dev in devices:
                values = [dev[col] for col in cols]
                room_cursor.execute(f"INSERT INTO devices ({col_names}) VALUES ({placeholders})", values)
            print(f"  - 迁移了 {len(devices)} 个设备")

        try:
            old_cursor.execute("SELECT * FROM gift_triggers WHERE room_id = ?", (room_id,))
            triggers = old_cursor.fetchall()
            if triggers:
                cols = [desc[0] for desc in old_cursor.description]
                placeholders = ', '.join(['?'] * len(cols))
                col_names = ', '.join(cols)
                for trig in triggers:
                    values = [trig[col] for col in cols]
                    room_cursor.execute(f"INSERT INTO gift_triggers ({col_names}) VALUES ({placeholders})", values)
                print(f"  - 迁移了 {len(triggers)} 个礼物触发配置")
        except sqlite3.OperationalError:
            print("  - gift_triggers表不存在，跳过")

        try:
            old_cursor.execute("SELECT * FROM gift_trigger_logs WHERE room_id = ?", (room_id,))
            logs = old_cursor.fetchall()
            if logs:
                cols = [desc[0] for desc in old_cursor.description]
                placeholders = ', '.join(['?'] * len(cols))
                col_names = ', '.join(cols)
                for log in logs:
                    values = [log[col] for col in cols]
                    room_cursor.execute(f"INSERT INTO gift_trigger_logs ({col_names}) VALUES ({placeholders})", values)
                print(f"  - 迁移了 {len(logs)} 条触发日志")
        except sqlite3.OperationalError:
            print("  - gift_trigger_logs表不存在，跳过")

        room_conn.commit()
        room_conn.close()
        room_table_migrated = True

    old_conn.close()

    if room_table_migrated:
        print(f"\n[INFO] 迁移完成！")
        print(f"  - 全局配置: {new_config_db_path}")
        print(f"  - 房间数据库: {db_dir}\\room_N.db")
        print(f"  - 原始备份: {backup_path}")
        print(f"\n[重要] 原始config.db已保留，新代码将使用database/目录下的文件")
    else:
        print("[INFO] 无需迁移数据")

    return True


if __name__ == '__main__':
    migrate()
