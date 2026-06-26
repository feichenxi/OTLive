import threading
import logging
from typing import Dict, Optional
from .room_worker import RoomWorker

logger = logging.getLogger('IoT_Voice_Control')


class RoomWorkerManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RoomWorkerManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self.workers: Dict[int, RoomWorker] = {}
        self._worker_lock = threading.Lock()
        self.device_manager = None
        self.trigger_sound_player = None
        self.socketio = None
        self.db_manager = None

    def configure(self, device_manager=None, trigger_sound_player=None,
                  socketio=None, db_manager=None):
        self.device_manager = device_manager
        self.trigger_sound_player = trigger_sound_player
        self.socketio = socketio
        self.db_manager = db_manager

    def start_room(self, room_id: int, room_ip: str, room_port: int):
        with self._worker_lock:
            if room_id in self.workers:
                logger.warning(f"RoomWorkerManager: 房间{room_id}的Worker已存在")
                return self.workers[room_id]

            worker = RoomWorker(
                room_id=room_id,
                room_ip=room_ip,
                room_port=room_port,
                device_manager=self.device_manager,
                trigger_sound_player=self.trigger_sound_player,
                socketio=self.socketio,
                db_manager=self.db_manager,
            )
            worker.start()
            self.workers[room_id] = worker
            logger.info(f"RoomWorkerManager: 房间{room_id}的Worker已启动")
            return worker

    def stop_room(self, room_id: int):
        with self._worker_lock:
            worker = self.workers.pop(room_id, None)
            if worker:
                worker.stop()
                logger.info(f"RoomWorkerManager: 房间{room_id}的Worker已停止")

    def get_worker(self, room_id: int) -> Optional[RoomWorker]:
        return self.workers.get(room_id)

    def start_all_rooms(self):
        if not self.db_manager:
            logger.error("RoomWorkerManager: db_manager未配置")
            return

        rooms = self.db_manager.get_all_rooms()
        for room in rooms:
            if not room.get('enabled', True):
                logger.info(f"RoomWorkerManager: 房间{room['id']}已关闭，跳过启动Worker")
                continue
            room_id = room['id']
            room_ip = room.get('ip', '')
            room_port = room.get('port', 8080)
            if room_ip:
                self.start_room(room_id, room_ip, room_port)

        logger.info(f"RoomWorkerManager: 已启动{len(self.workers)}个房间Worker")

    def stop_all_rooms(self):
        with self._worker_lock:
            for room_id, worker in list(self.workers.items()):
                worker.stop()
            self.workers.clear()
            logger.info("RoomWorkerManager: 所有房间Worker已停止")

    def add_trigger(self, room_id: int, device_id: int, count: int):
        worker = self.get_worker(room_id)
        if worker:
            worker.add_trigger(device_id, count)
        else:
            logger.warning(f"RoomWorkerManager: 房间{room_id}的Worker不存在，无法添加触发")

    def clear_trigger(self, room_id: int, device_id: int):
        worker = self.get_worker(room_id)
        if worker:
            worker.clear_trigger(device_id)
        else:
            logger.warning(f"RoomWorkerManager: 房间{room_id}的Worker不存在，无法清空触发")

    def get_device_status(self, room_id: int, device_id: int) -> Optional[Dict]:
        worker = self.get_worker(room_id)
        if worker:
            return worker.get_device_status(device_id)
        return None

    def is_loop_active(self, room_id: int, device_name: str) -> bool:
        worker = self.get_worker(room_id)
        if worker:
            return worker.is_loop_active(room_id, device_name)
        return False

    def update_loop_device_config(self, room_id: int, device_name: str):
        worker = self.get_worker(room_id)
        if worker:
            worker.update_loop_device_config(room_id, device_name)

    def restart_room(self, room_id: int, room_ip: str = None, room_port: int = None):
        if room_ip is None or room_port is None:
            if self.db_manager:
                room = self.db_manager.get_room(room_id)
                if room:
                    room_ip = room_ip or room.get('ip', '')
                    room_port = room_port or room.get('port', 8080)
                else:
                    logger.error(f"RoomWorkerManager: 房间{room_id}不存在")
                    return
            else:
                logger.error("RoomWorkerManager: db_manager未配置")
                return

        self.stop_room(room_id)
        self.start_room(room_id, room_ip, room_port)

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            if cls._instance:
                cls._instance.stop_all_rooms()
            cls._instance = None
