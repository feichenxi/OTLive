import threading
import time
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger('IoT_Voice_Control')


class LoopTriggerState:
    """循环触发状态"""
    def __init__(self):
        self.last_executed_hour = -1  # 上次执行的小时
        self.last_executed_minute = -1  # 上次执行的分钟
        self.is_active = False  # 是否正在执行动作
        self.action_start_time = 0.0  # 动作开始时间


class LoopTriggerManager:
    """循环触发管理器
    
    负责管理主常动装置的循环触发功能
    """
    
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.states: Dict[str, LoopTriggerState] = {}  # room_id -> device_name -> state
        self.logger = logger
    
    def start(self):
        """启动循环触发管理器"""
        if self.running:
            self.logger.warning("循环触发管理器已在运行")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.logger.info("循环触发管理器已启动")
        
    def stop(self):
        """停止循环触发管理器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("循环触发管理器已停止")
        
    def _get_state(self, room_id: int, device_name: str) -> LoopTriggerState:
        """获取或创建设备状态"""
        key = f"{room_id}_{device_name}"
        with self.lock:
            if key not in self.states:
                self.states[key] = LoopTriggerState()
            return self.states[key]
    
    def _should_execute_now(self, loop_minute: str, current_hour: int, current_minute: int) -> bool:
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
    
    def _run_loop(self):
        """主循环"""
        while self.running:
            try:
                self._check_and_execute()
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"循环触发检查时出错: {e}", exc_info=True)
                time.sleep(1)
                
    def _check_and_execute(self):
        """检查并执行循环触发"""
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        
        # 遍历所有房间
        for room_id, room in self.device_manager.rooms.items():
            # 查找主常动装置
            device = room.devices.get('always')
            if not device:
                continue
            
            # 检查是否启用了循环触发
            if device.loop_action == 'manual':
                continue
            
            if not device.loop_minute or device.loop_duration <= 0:
                continue
            
            state = self._get_state(room_id, 'always')
            
            # 检查是否正在执行动作
            if state.is_active:
                # 检查是否应该结束动作
                elapsed = time.time() - state.action_start_time
                if elapsed >= device.loop_duration:
                    self._finish_action(room_id, device, state)
                continue
            
            # 检查是否应该开始新的执行
            # 避免同一分钟内重复执行
            if state.last_executed_hour == current_hour and state.last_executed_minute == current_minute:
                continue
            
            if self._should_execute_now(device.loop_minute, current_hour, current_minute):
                self._start_action(room_id, device, state, current_hour, current_minute)
    
    def _start_action(self, room_id: int, device, state: LoopTriggerState, 
                     current_hour: int, current_minute: int):
        """开始执行动作"""
        try:
            with self.lock:
                state.last_executed_hour = current_hour
                state.last_executed_minute = current_minute
                state.is_active = True
                state.action_start_time = time.time()
            
            # 根据动作模式执行
            if device.loop_action == 'open':
                # 定时开一下模式：打开设备
                self.logger.info(f"房间{room_id}主常动装置定时开一下")
                self.device_manager.control_device(room_id, 'always', 'on')
            elif device.loop_action == 'close':
                # 定时关一下模式：关闭设备
                self.logger.info(f"房间{room_id}主常动装置定时关一下")
                self.device_manager.control_device(room_id, 'always', 'off')
            
        except Exception as e:
            self.logger.error(f"开始动作失败: room_id={room_id}, error={e}", exc_info=True)
            # 失败也没关系，不影响下一次执行
            with self.lock:
                state.is_active = False
    
    def _finish_action(self, room_id: int, device, state: LoopTriggerState):
        """结束执行动作"""
        try:
            # 根据动作模式执行相反操作
            if device.loop_action == 'open':
                # 定时开一下模式：关闭设备
                self.logger.info(f"房间{room_id}主常动装置定时开一下结束")
                self.device_manager.control_device(room_id, 'always', 'off')
            elif device.loop_action == 'close':
                # 定时关一下模式：打开设备
                self.logger.info(f"房间{room_id}主常动装置定时关一下结束")
                self.device_manager.control_device(room_id, 'always', 'on')
            
        except Exception as e:
            self.logger.error(f"结束动作失败: room_id={room_id}, error={e}", exc_info=True)
            # 失败也没关系
        finally:
            with self.lock:
                state.is_active = False
    
    def update_device_config(self, room_id: int, device_name: str):
        """更新设备配置时调用，重置状态"""
        key = f"{room_id}_{device_name}"
        with self.lock:
            if key in self.states:
                self.states[key].is_active = False
        self.logger.info(f"已重置设备循环状态: room_id={room_id}, device={device_name}")
