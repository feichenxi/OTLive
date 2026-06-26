import threading
import time
import sqlite3
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger('IoT_Voice_Control')

# 尝试导入性能日志记录器，如果失败则使用替代方案
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from utils.performance_logger import get_performance_logger
    HAS_PERF_LOGGER = True
except ImportError:
    HAS_PERF_LOGGER = False
    
    # 定义一个替代的 get_performance_logger 函数
    def get_performance_logger():
        return None


@dataclass
class PendingTrigger:
    """待执行的触发任务"""
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


class TriggerQueueManager:
    """触发装置队列管理器
    
    负责管理所有触发装置的执行队列，从数据库读取待触发任务，
    按照时间顺序执行触发操作，并更新数据库状态。
    """
    
    def __init__(self, db_path: str, device_manager=None, trigger_sound_player=None):
        self.db_path = db_path
        self.device_manager = device_manager
        self.trigger_sound_player = trigger_sound_player
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.device_states: Dict[int, Dict] = {}
        self._executor = ThreadPoolExecutor(max_workers=12, thread_name_prefix="trigger")
        
    def start(self):
        """启动触发队列管理器"""
        if self.running:
            logger.warning("触发队列管理器已在运行")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("触发队列管理器已启动")
        
    def stop(self):
        """停止触发队列管理器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self._executor.shutdown(wait=False)
        logger.info("触发队列管理器已停止")
        
    def _run_loop(self):
        """主循环"""
        while self.running:
            try:
                self._process_trigger_queue()
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"处理触发队列时出错: {e}", exc_info=True)
                time.sleep(1)
                
    def _process_trigger_queue(self):
        """处理触发队列"""
        start_time = time.time()
        
        # 阶段1: 在锁内读取待处理的设备列表
        pending_triggers = self._read_pending_triggers()
        
        if not pending_triggers:
            time.sleep(0.1)
            return
        
        # 分离在线和离线设备
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
                # DeviceManager 不可用，默认按在线处理
                online_triggers.append(trigger)
        
        # 阶段2: 在锁外执行设备控制（并发友好）
        # 关键修改：无论在线设备发送命令成功与否，都要更新状态
        processed_online_triggers = []
        if online_triggers:
            futures = {}
            for trigger in online_triggers:
                future = self._executor.submit(self._execute_device_control, trigger)
                futures[future] = trigger

            for future in as_completed(futures):
                trigger = futures[future]
                try:
                    future.result()  # 不管成功失败，都处理
                except Exception as e:
                    logger.error(f"并发触发失败: device_id={trigger.device_id}, device={trigger.device_name}, error={e}")
                # 无论成功失败，都加入到要更新的列表
                processed_online_triggers.append(trigger)
        
        # 关键：所有待处理的触发（无论在线离线、成功失败）都要更新状态
        all_triggers_to_update = processed_online_triggers + offline_triggers
        
        # 阶段3: 在锁内批量更新数据库
        if all_triggers_to_update:
            self._update_trigger_states(all_triggers_to_update)
        
        # 记录整体耗时
        total_time_ms = (time.time() - start_time) * 1000
        logger.debug(f"触发队列处理完成: 在线={len(online_triggers)}, 离线={len(offline_triggers)}, 已处理在线={len(processed_online_triggers)}, 总更新={len(all_triggers_to_update)}, 耗时={total_time_ms:.2f}ms")
    
    def _read_pending_triggers(self) -> List[PendingTrigger]:
        """从数据库读取待触发的设备列表（在锁内执行）"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            try:
                # 获取所有待触发的装置
                cursor.execute("""
                    SELECT 
                        d.id,
                        d.room_id,
                        d.name,
                        d.pin,
                        d.trigger_on_duration,
                        d.trigger_off_duration,
                        d.trigger_remaining_count,
                        d.trigger_state,
                        d.last_trigger_time,
                        d.next_trigger_time,
                        r.ip as room_ip,
                        r.port as room_port
                    FROM devices d
                    JOIN rooms r ON d.room_id = r.id
                    WHERE d.enabled = 1 
                      AND d.trigger_off_duration > 0 
                      AND (d.trigger_remaining_count > 0 OR d.trigger_state = 1)
                    ORDER BY d.next_trigger_time ASC
                """)
                
                devices = cursor.fetchall()
                
                if not devices:
                    return []
                    
                current_time = datetime.now()
                pending_triggers = []
                
                for device in devices:
                    device_dict = dict(device)
                    device_id = device_dict['id']
                    
                    # 检查是否到达触发时间
                    next_trigger_time = device_dict.get('next_trigger_time')
                    if next_trigger_time:
                        next_time = datetime.fromisoformat(next_trigger_time)
                        if next_time > current_time + timedelta(seconds=0.05):
                            # 还未到触发时间，跳过
                            continue
                    
                    # 构建待触发对象
                    pending_trigger = PendingTrigger(
                        device_id=device_id,
                        room_id=device_dict['room_id'],
                        device_name=device_dict['name'],
                        trigger_on_duration=device_dict['trigger_on_duration'],
                        trigger_off_duration=device_dict['trigger_off_duration'],
                        current_state=device_dict['trigger_state'],
                        remaining_count=device_dict['trigger_remaining_count'],
                        next_trigger_time=next_trigger_time,
                        room_ip=device_dict['room_ip'],
                        room_port=device_dict['room_port']
                    )
                    pending_triggers.append(pending_trigger)
                
                return pending_triggers
                
            finally:
                conn.close()
    
    def _execute_device_control(self, trigger: PendingTrigger) -> bool:
        """执行设备控制（在锁外执行）"""
        start_time = time.time()
        
        try:
            new_state = not bool(trigger.current_state)
            action = 'on' if new_state else 'off'
            
            logger.info(f"执行触发: device_id={trigger.device_id}, device_name={trigger.device_name}, state={trigger.current_state} -> {new_state}")
            
            play_sound = False
            sound_delay = 0
            if new_state and self.trigger_sound_player:
                room = self.device_manager.rooms.get(trigger.room_id)
                if room and trigger.device_name in room.devices:
                    play_sound = room.devices[trigger.device_name].trigger_sound
                    sound_delay = room.devices[trigger.device_name].trigger_sound_delay
            
            self._control_device(trigger.room_id, trigger.device_name, action, trigger.trigger_on_duration, play_sound=play_sound, sound_delay=sound_delay)
            
            perf_logger = get_performance_logger()
            exec_time_ms = (time.time() - start_time) * 1000
            if perf_logger:
                perf_logger.log_trigger(
                    f"device_trigger_{action}",
                    exec_time_ms,
                    extra_info={
                        'device_id': trigger.device_id,
                        'device_name': trigger.device_name,
                        'action': action,
                        'remaining_count': trigger.remaining_count
                    }
                )
            
            return True
            
        except Exception as e:
            logger.error(f"执行设备控制失败: device_id={trigger.device_id}, error={e}", exc_info=True)
            perf_logger = get_performance_logger()
            if perf_logger:
                perf_logger.log_error(f"device_trigger_error_{trigger.device_id}", e)
            return False
    
    def _update_trigger_states(self, triggers: List[PendingTrigger]):
        """批量更新设备触发状态（在锁内执行）"""
        with self.lock:
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
                        
                        cursor.execute("SELECT trigger_remaining_count FROM devices WHERE id = ?", (trigger.device_id,))
                        new_remaining = cursor.fetchone()[0]
                        
                        if new_remaining == 0:
                            logger.info(f"设备 {trigger.device_id} 已打开（最后一次），等待 {trigger.trigger_on_duration} 秒后关闭")
                        else:
                            logger.info(f"设备 {trigger.device_id} 已打开，剩余 {new_remaining} 次")
                        
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
                        
                        logger.info(f"设备 {trigger.device_id} 已关闭")
                
                conn.commit()
                
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()
                
    def _control_device(self, room_id: int, device_name: str, action: str, duration: float = None, play_sound: bool = False, sound_delay: float = 0):
        """控制设备开关"""
        if self.device_manager:
            success = self.device_manager.control_device(room_id, device_name, action, duration, play_sound=play_sound, sound_delay=sound_delay)
            if not success:
                raise Exception(f"设备控制失败: room_id={room_id}, device_name={device_name}, action={action}")
        else:
            raise Exception("DeviceManager 未初始化")
        
    def add_trigger(self, device_id: int, count: int):
        """添加触发任务"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                # 获取设备信息
                cursor.execute("""
                    SELECT trigger_on_duration, trigger_off_duration, trigger_state
                    FROM devices WHERE id = ?
                """, (device_id,))
                
                result = cursor.fetchone()
                if not result:
                    raise ValueError(f"设备不存在: {device_id}")
                    
                trigger_on_duration, trigger_off_duration, current_state = result
                
                # 更新触发计数
                cursor.execute("""
                    UPDATE devices 
                    SET trigger_remaining_count = trigger_remaining_count + ?,
                        updated_at = ?
                    WHERE id = ?
                """, (count, datetime.now().isoformat(), device_id))
                
                # 如果设备当前没有在运行，设置下次触发时间
                cursor.execute("""
                    SELECT trigger_remaining_count, next_trigger_time
                    FROM devices WHERE id = ?
                """, (device_id,))
                
                remaining_count, next_trigger_time = cursor.fetchone()
                
                if next_trigger_time is None and remaining_count > 0:
                    # 设置立即触发
                    cursor.execute("""
                        UPDATE devices 
                        SET next_trigger_time = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), datetime.now().isoformat(), device_id))
                    
                conn.commit()
                logger.info(f"添加触发任务: device_id={device_id}, count={count}")
                
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()
                
    def clear_trigger(self, device_id: int):
        """清空触发任务"""
        with self.lock:
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
                logger.info(f"清空触发任务: device_id={device_id}")
                
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()
                
    def get_device_status(self, device_id: int) -> Optional[Dict]:
        """获取设备状态"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id,
                    name,
                    trigger_remaining_count,
                    trigger_state,
                    last_trigger_time,
                    next_trigger_time
                FROM devices 
                WHERE id = ?
            """, (device_id,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
            
        finally:
            conn.close()
