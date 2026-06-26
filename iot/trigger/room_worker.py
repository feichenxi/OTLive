import threading
import time
import sqlite3
import logging
import json
import re
import math
from contextlib import contextmanager
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger('IoT_Voice_Control')


@dataclass
class PendingTrigger:
    device_id: int
    room_id: int
    device_name: str
    trigger_on_duration: float
    trigger_off_duration: float
    current_state: int
    remaining_count: int
    next_trigger_time: Optional[str]
    room_ip: str
    room_port: int


class LoopTriggerState:
    def __init__(self):
        self.last_executed_hour = -1
        self.last_executed_minute = -1
        self.is_active = False
        self.action_start_time = 0.0


class RoomWorker:
    def __init__(self, room_id: int, room_ip: str, room_port: int,
                 device_manager, trigger_sound_player, socketio,
                 db_manager, poll_interval: float = 0.5, trigger_timeout: int = 10):
        self.room_id = room_id
        self.room_ip = room_ip
        self.room_port = room_port
        self.device_manager = device_manager
        self.trigger_sound_player = trigger_sound_player
        self.socketio = socketio
        self.db_manager = db_manager
        self.poll_interval = poll_interval
        self.trigger_timeout = trigger_timeout
        self.logger = logger

        self.db_path = db_manager.get_room_db_path(room_id)
        if not self.db_path:
            self.db_path = db_manager.ensure_room_db(room_id)
        self.running = False
        self.threads = []

        self.gift_enabled = True
        self.message_enabled = True
        self.loop_states: Dict[str, LoopTriggerState] = {}
        self.loop_lock = threading.Lock()
        self.service_start_time = datetime.now()
        self._gift_event = threading.Event()
        self._message_event = threading.Event()

    def start(self):
        if self.running:
            return
        self.running = True

        t1 = threading.Thread(target=self._gift_trigger_loop, daemon=True,
                              name=f"GiftTrigger-Room{self.room_id}")
        t1.start()
        self.threads.append(t1)

        t2 = threading.Thread(target=self._message_trigger_loop, daemon=True,
                              name=f"MsgTrigger-Room{self.room_id}")
        t2.start()
        self.threads.append(t2)

        t3 = threading.Thread(target=self._trigger_queue_loop, daemon=True,
                              name=f"TriggerQueue-Room{self.room_id}")
        t3.start()
        self.threads.append(t3)

        t4 = threading.Thread(target=self._loop_trigger_loop, daemon=True,
                              name=f"LoopTrigger-Room{self.room_id}")
        t4.start()
        self.threads.append(t4)

        t5 = threading.Thread(target=self._idle_check_loop, daemon=True,
                              name=f"IdleCheck-Room{self.room_id}")
        t5.start()
        self.threads.append(t5)

        self.logger.info(f"RoomWorker[房间{self.room_id}] 已启动 (5个子线程)")

    def notify_new_gifts(self):
        self._gift_event.set()

    def notify_new_messages(self):
        self._message_event.set()

    def stop(self):
        self.running = False
        self._gift_event.set()
        self._message_event.set()
        for t in self.threads:
            t.join(timeout=3)
        self.threads.clear()
        self.logger.info(f"RoomWorker[房间{self.room_id}] 已停止")

    @contextmanager
    def _get_room_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def add_trigger(self, device_id: int, count: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT trigger_on_duration, trigger_off_duration, trigger_state
                FROM devices WHERE id = ?
            """, (device_id,))
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"设备不存在: {device_id}")

            cursor.execute("""
                UPDATE devices 
                SET trigger_remaining_count = trigger_remaining_count + ?,
                    updated_at = ?
                WHERE id = ?
            """, (count, datetime.now().isoformat(), device_id))

            cursor.execute("""
                SELECT trigger_remaining_count, next_trigger_time
                FROM devices WHERE id = ?
            """, (device_id,))
            remaining_count, next_trigger_time = cursor.fetchone()

            if next_trigger_time is None and remaining_count > 0:
                cursor.execute("""
                    UPDATE devices 
                    SET next_trigger_time = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), datetime.now().isoformat(), device_id))

            conn.commit()
            self.logger.info(f"RoomWorker[房间{self.room_id}] 添加触发: device_id={device_id}, count={count}")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def clear_trigger(self, device_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE devices 
                SET trigger_remaining_count = 0,
                    trigger_state = 0,
                    next_trigger_time = NULL,
                    updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), device_id))
            conn.commit()
            self.logger.info(f"RoomWorker[房间{self.room_id}] 清空触发: device_id={device_id}")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_device_status(self, device_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, name, trigger_remaining_count, trigger_state,
                       last_trigger_time, next_trigger_time
                FROM devices WHERE id = ?
            """, (device_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            conn.close()

    def _gift_trigger_loop(self):
        if not self.gift_enabled:
            return
        while self.running:
            try:
                self._process_gift_messages()
            except Exception as e:
                self.logger.error(f"RoomWorker[房间{self.room_id}] 礼物触发出错: {e}")
            self._gift_event.wait(timeout=self.poll_interval)
            self._gift_event.clear()

    def _message_trigger_loop(self):
        if not self.message_enabled:
            return
        while self.running:
            try:
                self._process_message_messages()
            except Exception as e:
                self.logger.error(f"RoomWorker[房间{self.room_id}] 文字触发出错: {e}")
            self._message_event.wait(timeout=self.poll_interval)
            self._message_event.clear()

    def _trigger_queue_loop(self):
        while self.running:
            try:
                self._process_trigger_queue()
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"RoomWorker[房间{self.room_id}] 触发队列出错: {e}")
                time.sleep(1)

    def _loop_trigger_loop(self):
        while self.running:
            try:
                self._check_and_execute_loop()
                time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"RoomWorker[房间{self.room_id}] 循环触发出错: {e}")
                time.sleep(1)

    def _idle_check_loop(self):
        while self.running:
            try:
                self._check_idle_timeout()
                time.sleep(1.0)
            except Exception as e:
                self.logger.error(f"RoomWorker[房间{self.room_id}] 空闲检测出错: {e}")
                time.sleep(1)

    def _process_gift_messages(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            time_threshold = datetime.now() - timedelta(minutes=self.trigger_timeout)
            time_threshold_str = time_threshold.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                SELECT id, nickname as name, gift_name as giftname,
                       gift_count as giftcount, gift_price as giftdiamond, created_at
                FROM gifts
                WHERE triggered = 0
                  AND created_at >= ?
                  AND gift_count > 0
                ORDER BY created_at DESC
                LIMIT 100
            """, (time_threshold_str,))
            gift_messages = [dict(row) for row in cursor.fetchall()]
            conn.close()

            if not gift_messages:
                return

            for msg in gift_messages:
                self._process_single_gift(msg)

        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 处理礼物消息失败: {e}")

    def _process_single_gift(self, msg: Dict):
        msg_id = msg['id']
        gift_name = msg.get('giftname', '')
        gift_count = msg.get('giftcount', 0)
        gift_diamond = msg.get('giftdiamond', 0)
        created_at = msg['created_at']

        try:
            if self._is_message_expired(created_at):
                self._mark_gift_processed(msg_id, "消息超时")
                return

            gift_trigger = self._find_gift_trigger(gift_name, gift_count)

            if gift_trigger:
                trigger_count = gift_trigger['trigger_count']
                device_type = gift_trigger.get('device_type', 'main')
                device_config = gift_trigger.get('device_config', None)

                if device_type == 'programmable':
                    device_info = self._update_programmable_device(trigger_count, device_config)
                    if device_info:
                        self._log_trigger_event(device_info['name'], gift_name, gift_count,
                                               trigger_count, device_info['original_count'],
                                               device_info['remaining_count'])
                else:
                    device_info = self._update_device_trigger_count(trigger_count)
                    if device_info:
                        self._log_trigger_event(device_info['name'], gift_name, gift_count,
                                               trigger_count, device_info['original_count'],
                                               device_info['remaining_count'])

                self._mark_gift_processed(msg_id, "成功处理")
            else:
                self._handle_unknown_gift(msg_id, gift_count, gift_diamond, gift_name)
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 处理礼物消息失败(ID={msg_id}): {e}")

    def _process_message_messages(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            time_threshold = datetime.now() - timedelta(minutes=self.trigger_timeout)
            time_threshold_str = time_threshold.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                SELECT id, nickname as name, content, created_at
                FROM messages
                WHERE triggered = 0
                  AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT 100
            """, (time_threshold_str,))
            message_messages = [dict(row) for row in cursor.fetchall()]
            conn.close()

            if not message_messages:
                return

            for msg in message_messages:
                self._process_single_message(msg)

        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 处理文字消息失败: {e}")

    def _process_single_message(self, msg: Dict):
        msg_id = msg['id']
        message_content = msg.get('content', '')
        created_at = msg['created_at']

        try:
            if self._is_message_expired(created_at):
                self._mark_message_processed(msg_id, "消息超时")
                return

            triggered_devices = self._find_and_trigger_devices(message_content)

            if triggered_devices:
                self._mark_message_processed(msg_id, f"成功触发{len(triggered_devices)}个设备")
            else:
                self._mark_message_processed(msg_id, "无匹配配置")
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 处理文字消息失败(ID={msg_id}): {e}")

    def _find_and_trigger_devices(self, message_content: str) -> List[Dict]:
        triggered_devices = []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, trigger_remaining_count, gift_event
                FROM devices
                WHERE room_id = ? AND enabled = 1 AND gift_event IS NOT NULL AND gift_event != ''
            """, (self.room_id,))
            devices = cursor.fetchall()
            conn.close()

            for device_row in devices:
                device_id, device_name, original_count, gift_event = device_row[0], device_row[1], device_row[2], device_row[3]
                trigger_text = self._parse_message_trigger(gift_event)
                if not trigger_text:
                    continue
                if trigger_text not in message_content:
                    continue

                device_info = self._update_programmable_device(
                    1, json.dumps({'device_name': device_name}))
                if device_info:
                    triggered_devices.append({
                        'name': device_name,
                        'original_count': original_count,
                        'remaining_count': device_info['remaining_count']
                    })
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 查找触发设备失败: {e}")
        return triggered_devices

    def _parse_message_trigger(self, gift_event: str) -> Optional[str]:
        if not gift_event:
            return None
        try:
            data = json.loads(gift_event)
            if data.get('type') == 'msg':
                return data.get('text', '')
        except Exception:
            pass
        return None

    def _find_gift_trigger(self, gift_name: str, gift_count: int = 1) -> Optional[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT room_id, gift_name, trigger_count, device_type, device_config
                FROM gift_triggers
                WHERE room_id = ?
            """, (self.room_id,))
            all_configs = cursor.fetchall()
            conn.close()

            for row in all_configs:
                config_gift_name = row[1]
                base_trigger_count = row[2]
                if config_gift_name and config_gift_name in gift_name:
                    actual_trigger_count = base_trigger_count * gift_count
                    return {
                        'room_id': row[0],
                        'gift_name': row[1],
                        'trigger_count': actual_trigger_count,
                        'base_count': base_trigger_count,
                        'device_type': row[3],
                        'device_config': row[4]
                    }
            return None
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 查询礼物触发配置失败: {e}")
            return None

    def _update_device_trigger_count(self, trigger_count: int) -> Optional[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, trigger_remaining_count
                FROM devices 
                WHERE room_id = ? AND enabled = 1 AND name = 'trigger'
            """, (self.room_id,))
            before_device = cursor.fetchone()

            if not before_device:
                conn.close()
                return None

            original_count = before_device[2]
            device_name = before_device[1]

            current_time = datetime.now().isoformat()
            cursor.execute("""
                UPDATE devices
                SET trigger_remaining_count = trigger_remaining_count + ?,
                    next_trigger_time = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE room_id = ? AND enabled = 1 AND name = 'trigger'
            """, (trigger_count, current_time, self.room_id))

            cursor.execute("""
                SELECT trigger_remaining_count
                FROM devices 
                WHERE room_id = ? AND enabled = 1 AND name = 'trigger'
            """, (self.room_id,))
            updated_device = cursor.fetchone()

            conn.commit()
            conn.close()

            remaining_count = updated_device[0] if updated_device else original_count + trigger_count
            return {
                'name': device_name,
                'original_count': original_count,
                'remaining_count': remaining_count
            }
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 更新设备触发次数失败: {e}")
            return None

    def _update_programmable_device(self, trigger_count: int, device_config: str) -> Optional[Dict]:
        try:
            config = json.loads(device_config) if device_config else {}
            device_name = config.get('device_name', '')
            if not device_name:
                return None

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, trigger_remaining_count
                FROM devices 
                WHERE room_id = ? AND enabled = 1 AND name = ?
            """, (self.room_id, device_name))
            before_device = cursor.fetchone()

            if not before_device:
                conn.close()
                return None

            original_count = before_device[2]

            cursor.execute("""
                UPDATE devices
                SET trigger_remaining_count = trigger_remaining_count + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE room_id = ? AND enabled = 1 AND name = ?
            """, (trigger_count, self.room_id, device_name))

            cursor.execute("""
                SELECT trigger_remaining_count
                FROM devices 
                WHERE room_id = ? AND enabled = 1 AND name = ?
            """, (self.room_id, device_name))
            updated_device = cursor.fetchone()

            conn.commit()
            conn.close()

            remaining_count = updated_device[0] if updated_device else original_count + trigger_count
            return {
                'name': device_name,
                'original_count': original_count,
                'remaining_count': remaining_count
            }
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 更新编程设备触发次数失败: {e}")
            return None

    def _handle_unknown_gift(self, msg_id: int, gift_count: int, gift_diamond: int, gift_name: str = "未知礼物"):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT trigger_count, device_config FROM gift_triggers WHERE room_id = ? AND gift_name = '未知礼物'",
                (self.room_id,)
            )
            row = c.fetchone()
            conn.close()

            if not row:
                self._mark_gift_processed(msg_id, "无未知礼物配置")
                return

            threshold = 10
            if row[1]:
                try:
                    config = json.loads(row[1])
                    threshold = config.get('threshold', 10)
                except Exception:
                    pass

            if gift_diamond < threshold:
                self._mark_gift_processed(msg_id, f"礼物价值{gift_diamond}低于阈值{threshold}")
                return

            total_value = gift_count * gift_diamond
            if threshold <= 0:
                self._mark_gift_processed(msg_id, "阈值无效")
                return

            actual_trigger_count = math.ceil(total_value / threshold)
            if actual_trigger_count < 1:
                self._mark_gift_processed(msg_id, f"未达阈值: total_value={total_value}, threshold={threshold}")
                return

            device_info = self._update_device_trigger_count(actual_trigger_count)
            if device_info:
                self._log_trigger_event(device_info['name'], gift_name, gift_count,
                                       actual_trigger_count, device_info['original_count'],
                                       device_info['remaining_count'])
            self._mark_gift_processed(msg_id, "未知礼物触发成功")
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 处理未知礼物失败: {e}")

    def _log_trigger_event(self, device_name: str, gift_name: str,
                          gift_count: int, trigger_count: int,
                          original_count: int, remaining_count: int):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO gift_trigger_logs 
                (room_id, device_name, gift_name, gift_count, trigger_count, 
                 original_count, remaining_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.room_id, device_name, gift_name, gift_count, trigger_count,
                  original_count, remaining_count, local_time))

            cursor.execute("""
                DELETE FROM gift_trigger_logs 
                WHERE id NOT IN (
                    SELECT id FROM gift_trigger_logs 
                    ORDER BY created_at DESC 
                    LIMIT 500
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 记录触发日志失败: {e}")

    def _is_message_expired(self, created_at) -> bool:
        try:
            now = datetime.now()
            if isinstance(created_at, str):
                created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            time_diff = now - created_at
            return time_diff.total_seconds() / 60 > self.trigger_timeout
        except Exception:
            return False

    def _mark_message_processed(self, msg_id: int, reason: str = ""):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("UPDATE messages SET triggered = 1 WHERE id = ?", (msg_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 标记消息失败(ID={msg_id}): {e}")

    def _mark_gift_processed(self, msg_id: int, reason: str = ""):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("UPDATE gifts SET triggered = 1 WHERE id = ?", (msg_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 标记礼物消息失败(ID={msg_id}): {e}")

    def _process_trigger_queue(self):
        pending_triggers = self._read_pending_triggers()
        if not pending_triggers:
            return

        online_triggers = []
        offline_triggers = []

        for trigger in pending_triggers:
            if self.device_manager:
                room = self.device_manager.rooms.get(trigger.room_id)
                if room and room.online:
                    online_triggers.append(trigger)
                else:
                    offline_triggers.append(trigger)
            else:
                online_triggers.append(trigger)

        for trigger in online_triggers:
            try:
                self._execute_device_control(trigger)
            except Exception as e:
                self.logger.error(f"RoomWorker[房间{self.room_id}] 触发执行失败: device={trigger.device_name}, error={e}")

        all_triggers = online_triggers + offline_triggers
        if all_triggers:
            self._update_trigger_states(all_triggers)

    def _read_pending_triggers(self) -> List[PendingTrigger]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    d.id, d.room_id, d.name, d.pin,
                    d.trigger_on_duration, d.trigger_off_duration,
                    d.trigger_remaining_count, d.trigger_state,
                    d.last_trigger_time, d.next_trigger_time
                FROM devices d
                WHERE d.room_id = ? AND d.enabled = 1 
                  AND d.trigger_off_duration > 0 
                  AND (d.trigger_remaining_count > 0 OR d.trigger_state = 1)
                ORDER BY d.next_trigger_time ASC
            """, (self.room_id,))

            devices = cursor.fetchall()
            if not devices:
                return []

            current_time = datetime.now()
            pending_triggers = []

            for device in devices:
                device_dict = dict(device)
                next_trigger_time = device_dict.get('next_trigger_time')
                if next_trigger_time:
                    next_time = datetime.fromisoformat(next_trigger_time)
                    if next_time > current_time + timedelta(seconds=0.05):
                        continue

                pending_trigger = PendingTrigger(
                    device_id=device_dict['id'],
                    room_id=device_dict['room_id'],
                    device_name=device_dict['name'],
                    trigger_on_duration=device_dict['trigger_on_duration'],
                    trigger_off_duration=device_dict['trigger_off_duration'],
                    current_state=device_dict['trigger_state'],
                    remaining_count=device_dict['trigger_remaining_count'],
                    next_trigger_time=next_trigger_time,
                    room_ip=self.room_ip,
                    room_port=self.room_port
                )
                pending_triggers.append(pending_trigger)

            return pending_triggers
        finally:
            conn.close()

    def _execute_device_control(self, trigger: PendingTrigger):
        try:
            new_state = not bool(trigger.current_state)
            action = 'on' if new_state else 'off'

            self.logger.info(f"RoomWorker[房间{self.room_id}] 执行触发: device={trigger.device_name}, state={trigger.current_state}->{new_state}")

            play_sound = False
            sound_delay = 0
            if new_state and self.trigger_sound_player:
                room = self.device_manager.rooms.get(trigger.room_id)
                if room and trigger.device_name in room.devices:
                    play_sound = room.devices[trigger.device_name].trigger_sound
                    sound_delay = room.devices[trigger.device_name].trigger_sound_delay

            self._control_device(trigger.room_id, trigger.device_name, action, trigger.trigger_on_duration, play_sound=play_sound, sound_delay=sound_delay)
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 执行设备控制失败: device={trigger.device_name}, error={e}")

    def _update_trigger_states(self, triggers: List[PendingTrigger]):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            current_time = datetime.now()
            for trigger in triggers:
                new_state = not bool(trigger.current_state)
                if new_state:
                    cursor.execute("""
                        UPDATE devices 
                        SET trigger_state = 1,
                            trigger_remaining_count = CASE WHEN trigger_remaining_count > 0 THEN trigger_remaining_count - 1 ELSE 0 END,
                            last_trigger_time = ?,
                            next_trigger_time = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        current_time.isoformat(),
                        (current_time + timedelta(seconds=trigger.trigger_on_duration)).isoformat(),
                        current_time.isoformat(),
                        trigger.device_id
                    ))
                else:
                    remaining_count = trigger.remaining_count
                    if remaining_count > 0:
                        next_trigger_time = current_time + timedelta(seconds=trigger.trigger_off_duration)
                    else:
                        next_trigger_time = None

                    cursor.execute("""
                        UPDATE devices 
                        SET trigger_state = 0,
                            last_trigger_time = ?,
                            next_trigger_time = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        current_time.isoformat(),
                        next_trigger_time.isoformat() if next_trigger_time else None,
                        current_time.isoformat(),
                        trigger.device_id
                    ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"RoomWorker[房间{self.room_id}] 更新触发状态失败: {e}")
        finally:
            conn.close()

    def _control_device(self, room_id: int, device_name: str, action: str, duration: float = None, play_sound: bool = False, sound_delay: float = 0):
        if self.device_manager:
            success = self.device_manager.control_device(room_id, device_name, action, duration, play_sound=play_sound, sound_delay=sound_delay)
            if not success:
                raise Exception(f"设备控制失败: room_id={room_id}, device={device_name}, action={action}")

    def _check_and_execute_loop(self):
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute

        room = self.device_manager.rooms.get(self.room_id)
        if not room:
            return

        device = room.devices.get('always')
        if not device:
            return

        if device.loop_action == 'manual':
            return
        if not device.loop_minute or device.loop_duration <= 0:
            return

        state = self._get_loop_state(self.room_id, 'always')

        if state.is_active:
            elapsed = time.time() - state.action_start_time
            if elapsed >= device.loop_duration:
                self._finish_loop_action(self.room_id, device, state)
            return

        if state.last_executed_hour == current_hour and state.last_executed_minute == current_minute:
            return

        if self._should_execute_loop_now(device.loop_minute, current_minute):
            self._start_loop_action(self.room_id, device, state, current_hour, current_minute)

    def _should_execute_loop_now(self, loop_minute: str, current_minute: int) -> bool:
        if not loop_minute or not loop_minute.strip():
            return False
        parts = [p.strip() for p in loop_minute.split('|') if p.strip()]
        for part in parts:
            try:
                num = int(part)
            except ValueError:
                continue
            if 0 <= num <= 9:
                if current_minute % 10 == num:
                    return True
            elif 10 <= num <= 59:
                if current_minute == num:
                    return True
        return False

    def _get_loop_state(self, room_id: int, device_name: str) -> LoopTriggerState:
        key = f"{room_id}_{device_name}"
        with self.loop_lock:
            if key not in self.loop_states:
                self.loop_states[key] = LoopTriggerState()
            return self.loop_states[key]

    def _start_loop_action(self, room_id: int, device, state: LoopTriggerState,
                           current_hour: int, current_minute: int):
        try:
            with self.loop_lock:
                state.last_executed_hour = current_hour
                state.last_executed_minute = current_minute
                state.is_active = True
                state.action_start_time = time.time()

            play_sound = device.trigger_sound if device else False
            sound_delay = device.trigger_sound_delay if device else 0
            if device.loop_action == 'open':
                self.device_manager.control_device(room_id, 'always', 'on', play_sound=play_sound, sound_delay=sound_delay)
            elif device.loop_action == 'close':
                self.device_manager.control_device(room_id, 'always', 'off')
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 循环触发启动失败: {e}")
            with self.loop_lock:
                state.is_active = False

    def _finish_loop_action(self, room_id: int, device, state: LoopTriggerState):
        try:
            if device.loop_action == 'open':
                self.device_manager.control_device(room_id, 'always', 'off')
            elif device.loop_action == 'close':
                play_sound = device.trigger_sound if device else False
                sound_delay = device.trigger_sound_delay if device else 0
                self.device_manager.control_device(room_id, 'always', 'on', play_sound=play_sound, sound_delay=sound_delay)
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 循环触发结束失败: {e}")
        finally:
            with self.loop_lock:
                state.is_active = False

    def update_loop_device_config(self, room_id: int, device_name: str):
        key = f"{room_id}_{device_name}"
        with self.loop_lock:
            if key in self.loop_states:
                self.loop_states[key].is_active = False

    def is_loop_active(self, room_id: int, device_name: str) -> bool:
        state = self._get_loop_state(room_id, device_name)
        return state.is_active

    def _check_idle_timeout(self):
        triggers_to_execute = []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT room_id, trigger_count, device_config
                FROM gift_triggers
                WHERE gift_name = '闲置触发' AND room_id = ?
            """, (self.room_id,))
            idle_configs = cursor.fetchall()

            if not idle_configs:
                conn.close()
                return

            for config in idle_configs:
                trigger_count = config[1]
                device_config = json.loads(config[2]) if config[2] else {}
                timeout_seconds = device_config.get('timeout_seconds', 60)

                room = self.device_manager.rooms.get(self.room_id)
                if not room or not room.online:
                    continue

                cursor.execute("""
                    SELECT created_at
                    FROM gift_trigger_logs
                    WHERE room_id = ? AND device_name = 'trigger'
                    ORDER BY id DESC
                    LIMIT 1
                """, (self.room_id,))
                last_trigger = cursor.fetchone()

                if last_trigger:
                    try:
                        last_time = datetime.fromisoformat(last_trigger[0])
                    except (ValueError, TypeError):
                        last_time = self.service_start_time
                else:
                    last_time = self.service_start_time

                if last_time < self.service_start_time:
                    last_time = self.service_start_time

                time_diff = (datetime.now() - last_time).total_seconds()
                if time_diff >= timeout_seconds:
                    triggers_to_execute.append({
                        'trigger_count': trigger_count,
                        'timeout_seconds': timeout_seconds
                    })

            conn.close()
        except Exception as e:
            self.logger.error(f"RoomWorker[房间{self.room_id}] 空闲检测失败: {e}")
            return

        for trigger_info in triggers_to_execute:
            try:
                device_info = self._update_device_trigger_count(trigger_info['trigger_count'])
                if device_info:
                    self._log_trigger_event(
                        device_info['name'], '闲置触发', 1,
                        trigger_info['trigger_count'],
                        device_info['original_count'],
                        device_info['remaining_count']
                    )
            except Exception as e:
                self.logger.error(f"RoomWorker[房间{self.room_id}] 执行空闲触发失败: {e}")
