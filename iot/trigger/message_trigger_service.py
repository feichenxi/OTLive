import threading
import time
import logging
import json
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from common.database_manager import get_database_manager

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

logger = logging.getLogger('IoT_Voice_Control')


class MessageTriggerService:
    """文字消息触发服务
    
    定期从MySQL查询未触发的文字消息，根据devices表中的gift_event配置（JSON格式）更新devices表
    """
    
    def __init__(self, config: Dict):
        """
        初始化文字消息触发服务
        
        Args:
            config: 配置字典，包含MySQL连接信息和轮询间隔
        """
        self.logger = logger
        self.enabled = config.get('enabled', True)
        self.poll_interval = config.get('poll_interval', 2.0)
        self.trigger_timeout = config.get('trigger_timeout', 10)
        
        self.mysql_config = {
            'host': config.get('mysql_host'),
            'port': config.get('mysql_port'),
            'db': config.get('mysql_db'),
            'user': config.get('mysql_user'),
            'password': config.get('mysql_password'),
            'charset': 'utf8mb4'
        }
        
        self.sqlite_db = get_database_manager()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.mysql_connection = None
        
        self._init_mysql_connection()
    
    def _init_mysql_connection(self):
        """初始化MySQL连接"""
        try:
            self.mysql_connection = pymysql.connect(
                host=self.mysql_config['host'],
                port=self.mysql_config['port'],
                database=self.mysql_config['db'],
                user=self.mysql_config['user'],
                password=self.mysql_config['password'],
                charset=self.mysql_config['charset'],
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=5
            )
            self.logger.info("MySQL连接成功 (文字触发服务)")
        except Exception as e:
            self.logger.warning(f"MySQL连接失败 (文字触发服务): {e}，服务将在后台尝试重连")
            self.mysql_connection = None
    
    def _reconnect_mysql(self):
        """重新连接MySQL"""
        if self.mysql_connection:
            try:
                self.mysql_connection.close()
            except:
                pass
        
        self._init_mysql_connection()
    
    def _get_mysql_connection(self):
        """获取MySQL连接，如果断开则重连"""
        if self.mysql_connection is None:
            self._init_mysql_connection()
        else:
            try:
                self.mysql_connection.ping(reconnect=True)
            except:
                self._reconnect_mysql()
        
        return self.mysql_connection
    
    def start(self):
        """启动文字消息触发服务"""
        if not self.enabled:
            self.logger.info("文字触发服务未启用")
            return
            
        if self.running:
            self.logger.warning("文字触发服务已在运行")
            return
            
        self.logger.info(f"准备启动文字触发服务线程，enabled={self.enabled}, running={self.running}")
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="MessageTriggerService")
        self.thread.start()
        self.logger.info(f"文字触发服务线程已启动，thread={self.thread}, alive={self.thread.is_alive()}")
        
    def stop(self):
        """停止文字消息触发服务"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        if self.mysql_connection:
            try:
                self.mysql_connection.close()
            except:
                pass
        
        self.logger.info("文字触发服务已停止")
        
    def _run_loop(self):
        """主循环"""
        self.logger.info("文字触发服务主循环开始")
        loop_count = 0
        while self.running:
            try:
                loop_count += 1
                self.logger.info(f"文字触发主循环执行第{loop_count}次，开始处理文字消息...")
                self._process_message_messages()
                self.logger.info(f"文字触发主循环执行第{loop_count}次完成，等待{self.poll_interval}秒...")
                time.sleep(self.poll_interval)
            except Exception as e:
                self.logger.error(f"处理文字消息时出错: {e}", exc_info=True)
                time.sleep(5)
        self.logger.info(f"文字触发服务主循环结束，共执行{loop_count}次")
    
    def _process_message_messages(self):
        """处理文字消息"""
        with self.lock:
            mysql_conn = self._get_mysql_connection()
            if not mysql_conn:
                self.logger.error("无法获取MySQL连接 (文字触发)")
                return
            
            try:
                mysql_conn.commit()

                with mysql_conn.cursor() as cursor:
                    time_threshold = datetime.now() - timedelta(minutes=self.trigger_timeout)

                    cursor.execute("SELECT COUNT(*) as cnt FROM msg WHERE type = 'msg' AND `trigger` = 0")
                    total_untriggered = cursor.fetchone()['cnt']
                    self.logger.info(f"[MSG DEBUG] 所有未触发文字消息总数: {total_untriggered}")

                    query = """
                        SELECT id, room, name, content, created_at
                        FROM msg
                        WHERE type = 'msg'
                          AND `trigger` = 0
                          AND created_at >= %s
                        ORDER BY created_at DESC
                        LIMIT 100
                    """
                    cursor.execute(query, (time_threshold,))
                    message_messages = cursor.fetchall()

                    self.logger.info(f"[MSG DEBUG] 查询到 {len(message_messages)} 条未触发的文字消息，时间阈值: {time_threshold}")

                    if not message_messages:
                        self.logger.info("[MSG DEBUG] 没有未触发的文字消息，跳过处理")
                        return

                    self.logger.info(f"[MSG DEBUG] 发现 {len(message_messages)} 条未触发的文字消息")
                    
                    for msg in message_messages:
                        self._process_single_message(cursor, msg)
                    
                    mysql_conn.commit()
                    
            except Exception as e:
                mysql_conn.rollback()
                self.logger.error(f"处理文字消息失败: {e}", exc_info=True)
    
    def _process_single_message(self, cursor, msg: Dict):
        """处理单条文字消息
        
        Args:
            cursor: MySQL游标
            msg: 文字消息字典
        """
        msg_id = msg['id']
        room_ip = msg['room']
        message_content = msg.get('content', '')
        created_at = msg['created_at']
        
        try:
            self.logger.info(f"开始处理文字消息: ID={msg_id}, room={room_ip}, content={message_content}")
            
            if self._is_message_expired(created_at):
                self.logger.info(f"文字消息已超时，跳过处理: ID={msg_id}, created_at={created_at}")
                self._mark_message_processed(cursor, msg_id, "消息超时")
                return

            triggered_devices = self._find_and_trigger_devices(room_ip, message_content)
            
            if triggered_devices:
                self._mark_message_processed(cursor, msg_id, f"成功触发{len(triggered_devices)}个设备")
            else:
                self._mark_message_processed(cursor, msg_id, "无匹配配置")
            
        except Exception as e:
            self.logger.error(f"处理文字消息失败 (ID={msg_id}): {e}", exc_info=True)
    
    def _find_and_trigger_devices(self, room_ip: str, message_content: str) -> List[Dict]:
        """查找并触发匹配的设备
        
        Args:
            room_ip: 房间IP
            message_content: 消息内容
            
        Returns:
            触发的设备信息列表
        """
        triggered_devices = []
        
        try:
            room_id = self._get_room_id_by_ip(room_ip)
            if not room_id:
                return triggered_devices
            
            # 检查房间是否已关闭
            with self.sqlite_db._get_connection() as conn:
                enabled_row = conn.execute("SELECT enabled FROM rooms WHERE id = ?", (room_id,)).fetchone()
                if enabled_row and not bool(enabled_row[0]):
                    return triggered_devices
            
            with self.sqlite_db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, trigger_remaining_count, gift_event
                    FROM devices
                    WHERE room_id = ? AND enabled = 1 AND gift_event IS NOT NULL AND gift_event != ''
                """, (room_id,))
                devices = cursor.fetchall()
                
                for device_row in devices:
                    device_id, device_name, original_count, gift_event = device_row
                    
                    trigger_text = self._parse_message_trigger(gift_event)
                    if not trigger_text:
                        continue
                    
                    if trigger_text not in message_content:
                        continue
                    
                    self.logger.info(f"文字消息匹配成功: device={device_name}, trigger_text={trigger_text}, content={message_content}")
                    
                    device_info = self._update_programmable_device(room_ip, 1, json.dumps({'device_name': device_name}))
                    if device_info:
                        # 记录触发日志
                        self._log_trigger_event(room_ip, device_name, "文字触发", 1, 1, original_count, device_info['remaining_count'])
                        triggered_devices.append({
                            'name': device_name,
                            'original_count': original_count,
                            'remaining_count': device_info['remaining_count']
                        })
        
        except Exception as e:
            self.logger.error(f"查找触发设备失败: {e}", exc_info=True)
        
        return triggered_devices

    def _log_trigger_event(self, room: str, device_name: str, gift_name: str, 
                          gift_count: int, trigger_count: int, 
                          original_count: int, remaining_count: int,
                          room_id: int = None):
        """记录触发日志到数据库
        
        Args:
            room: 房间IP地址
            device_name: 设备名称
            gift_name: 礼物名称
            gift_count: 礼物数量
            trigger_count: 触发次数
            original_count: 原剩余次数
            remaining_count: 更新后剩余次数
            room_id: 房间ID（可选，如果不提供则通过IP查询）
        """
        try:
            if not room_id:
                room_id = self._get_room_id_by_ip(room)
            if not room_id:
                self.logger.warning(f"记录触发日志失败: 未找到房间ID, room={room}")
                return
            
            with self.sqlite_db._get_connection() as conn:
                cursor = conn.cursor()
                local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    INSERT INTO gift_trigger_logs 
                    (room_id, device_name, gift_name, gift_count, trigger_count, 
                     original_count, remaining_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (room_id, device_name, gift_name, gift_count, trigger_count,
                      original_count, remaining_count, local_time))
                
                # 只保留最近500条记录
                cursor.execute("""
                    DELETE FROM gift_trigger_logs 
                    WHERE id NOT IN (
                        SELECT id FROM gift_trigger_logs 
                        ORDER BY created_at DESC 
                        LIMIT 500
                    )
                """)
        except Exception as e:
            self.logger.error(f"记录触发日志失败: {e}", exc_info=True)
    
    def _parse_message_trigger(self, gift_event: str) -> Optional[str]:
        """解析gift_event，返回触发文字（如果是文字触发）
        
        Args:
            gift_event: gift_event字段值
            
        Returns:
            触发文字，如果不是文字触发返回None
        """
        if not gift_event:
            return None
        try:
            data = json.loads(gift_event)
            if data.get('type') == 'msg':
                return data.get('text', '')
        except:
            pass
        return None
    
    def _get_room_id_by_ip(self, room_ip: str) -> Optional[int]:
        """根据IP地址获取房间ID
        
        Args:
            room_ip: 房间IP地址
            
        Returns:
            房间ID，未找到返回None
        """
        try:
            with self.sqlite_db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM rooms WHERE ip = ?", (room_ip,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                return None
        except Exception as e:
            self.logger.error(f"获取房间ID失败: {e}")
            return None
    
    def _is_message_expired(self, created_at: datetime) -> bool:
        """检查消息是否超时"""
        try:
            now = datetime.now()
            if isinstance(created_at, str):
                created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')

            time_diff = now - created_at
            expired_minutes = time_diff.total_seconds() / 60
            is_expired = expired_minutes > self.trigger_timeout
            return is_expired
        except Exception as e:
            self.logger.error(f"检查消息超时失败: {e}", exc_info=True)
            return False
    
    def _update_programmable_device(self, room: str, trigger_count: int, device_config: str) -> Optional[Dict]:
        """更新可编程设备的触发剩余次数
        
        Args:
            room: 房间IP地址
            trigger_count: 触发次数
            device_config: 设备配置JSON字符串
            
        Returns:
            设备信息字典
        """
        try:
            config = json.loads(device_config) if device_config else {}
            device_name = config.get('device_name', '')
            
            if not device_name:
                return None
            
            with self.sqlite_db._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id FROM rooms WHERE ip = ?
                """, (room,))
                room_row = cursor.fetchone()
                
                if not room_row:
                    return None
                
                room_id = room_row[0]
                
                cursor.execute("""
                    SELECT id, name, trigger_remaining_count
                    FROM devices 
                    WHERE room_id = ? AND enabled = 1 AND name = ?
                """, (room_id, device_name))
                before_device = cursor.fetchone()
                
                if not before_device:
                    return None
                
                original_count = before_device[2] if before_device else 0
                
                current_time = datetime.now().isoformat()
                cursor.execute("""
                    UPDATE devices
                    SET trigger_remaining_count = trigger_remaining_count + ?,
                        next_trigger_time = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE room_id = ? AND enabled = 1 AND name = ?
                """, (trigger_count, current_time, room_id, device_name))
                
                affected_rows = cursor.rowcount
                
                cursor.execute("""
                    SELECT id, name, trigger_remaining_count
                    FROM devices 
                    WHERE room_id = ? AND enabled = 1 AND name = ?
                """, (room_id, device_name))
                updated_device = cursor.fetchone()
                
                if affected_rows > 0:
                    remaining_count = updated_device[2] if updated_device else original_count + trigger_count
                    self.logger.info(f"文字触发更新设备: device={device_name}, add={trigger_count}, original={original_count}, remaining={remaining_count}")
                    return {
                        'name': device_name,
                        'original_count': original_count,
                        'remaining_count': remaining_count
                    }
                else:
                    return None
                    
        except Exception as e:
            self.logger.error(f"更新设备触发次数失败: {e}", exc_info=True)
            return None
    
    def _mark_message_processed(self, cursor, msg_id: int, reason: str = ""):
        """标记消息为已处理"""
        try:
            cursor.execute("UPDATE msg SET `trigger` = 1 WHERE id = %s", (msg_id,))
            self.logger.info(f"[MSG DEBUG] 标记文字消息为已处理: ID={msg_id}, reason={reason}")
        except Exception as e:
            self.logger.error(f"标记消息处理状态失败 (ID={msg_id}): {e}", exc_info=True)


def create_message_trigger_service(config: Dict) -> Optional[MessageTriggerService]:
    """创建文字消息触发服务实例
    
    Args:
        config: 配置字典
        
    Returns:
        MessageTriggerService实例
    """
    if not config.get('enabled', False):
        return None
    
    if not PYMYSQL_AVAILABLE:
        logger.warning("pymysql库未安装，文字触发服务无法启动")
        return None
    
    return MessageTriggerService(config)
