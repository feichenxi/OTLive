import threading
import time
import logging
import re
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from common.database_manager import get_database_manager

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

logger = logging.getLogger('IoT_Voice_Control')


class GiftTriggerService:
    """礼物触发服务
    
    定期从MySQL查询未触发的礼物消息，根据gift_triggers配置更新devices表
    """
    
    def __init__(self, config: Dict):
        """
        初始化礼物触发服务
        
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
        
        self.idle_check_thread = None
        self.idle_check_interval = 1.0
        self.service_start_time = datetime.now()
        
        self._init_mysql_connection()
    
    def _extract_gift_name(self, content: str) -> str:
        """从礼物消息中提取礼物名称
        
        Args:
            content: 礼物消息内容，例如 "送了1个小可爱"
            
        Returns:
            礼物名称，例如 "小可爱"
        """
        # 匹配 "送了X个Y" 格式
        match = re.search(r'送了\d+个(.+)', content)
        if match:
            return match.group(1)
        return content
        
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
            self.logger.info("MySQL连接成功")
        except Exception as e:
            self.logger.warning(f"MySQL连接失败: {e}，服务将在后台尝试重连")
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
        """启动礼物触发服务"""
        if not self.enabled:
            self.logger.info("礼物触发服务未启用")
            return
            
        if self.running:
            self.logger.warning("礼物触发服务已在运行")
            return
            
        self.logger.info(f"准备启动礼物触发服务线程，enabled={self.enabled}, running={self.running}")
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="GiftTriggerService")
        self.thread.start()
        self.logger.info(f"礼物触发服务线程已启动，thread={self.thread}, alive={self.thread.is_alive()}")
        
        self._start_idle_check_thread()
        
    def stop(self):
        """停止礼物触发服务"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        self._stop_idle_check_thread()
        
        if self.mysql_connection:
            try:
                self.mysql_connection.close()
            except:
                pass
        
        self.logger.info("礼物触发服务已停止")
    
    def _start_idle_check_thread(self):
        """启动空闲超时检测线程"""
        self.idle_check_thread = threading.Thread(
            target=self._idle_check_loop, 
            daemon=True, 
            name="IdleTriggerService"
        )
        self.idle_check_thread.start()
        self.logger.info("空闲超时检测线程已启动")
    
    def _stop_idle_check_thread(self):
        """停止空闲超时检测线程"""
        if self.idle_check_thread and self.idle_check_thread.is_alive():
            self.idle_check_thread.join(timeout=2)
            self.logger.info("空闲超时检测线程已停止")
    
    def _idle_check_loop(self):
        """空闲超时检测主循环（1秒/次）"""
        self.logger.info("空闲超时检测线程主循环开始")
        while self.running:
            try:
                self._check_idle_timeout()
                time.sleep(self.idle_check_interval)
            except Exception as e:
                self.logger.error(f"空闲检测出错: {e}")
                time.sleep(1)
        self.logger.info("空闲超时检测线程主循环结束")
    
    def _check_idle_timeout(self):
        """检查所有房间的空闲超时"""
        import json
        triggers_to_execute = []
        
        try:
            with self.sqlite_db._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT room_id, trigger_count, device_config
                    FROM gift_triggers
                    WHERE gift_name = '闲置触发'
                """)
                idle_configs = cursor.fetchall()
                
                if not idle_configs:
                    return
                
                for config in idle_configs:
                    room_id = config[0]
                    trigger_count = config[1]
                    device_config = json.loads(config[2]) if config[2] else {}
                    timeout_seconds = device_config.get('timeout_seconds', 60)
                    
                    cursor.execute("SELECT online, enabled FROM rooms WHERE id = ?", (room_id,))
                    online_row = cursor.fetchone()
                    if not online_row or online_row[0] != 1:
                        continue
                    if not bool(online_row[1] if len(online_row) > 1 else 1):
                        continue
                    
                    cursor.execute("""
                        SELECT created_at
                        FROM gift_trigger_logs
                        WHERE room_id = ? AND device_name = 'trigger'
                        ORDER BY id DESC
                        LIMIT 1
                    """, (room_id,))
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
                        cursor.execute("SELECT ip FROM rooms WHERE id = ?", (room_id,))
                        room_row = cursor.fetchone()
                        if not room_row:
                            continue
                        room_ip = room_row[0]
                        triggers_to_execute.append({
                            'room_id': room_id,
                            'room_ip': room_ip,
                            'trigger_count': trigger_count,
                            'timeout_seconds': timeout_seconds
                        })
        
        except Exception as e:
            self.logger.error(f"空闲检测失败: {e}", exc_info=True)
            return
        
        for trigger_info in triggers_to_execute:
            try:
                device_info = self._update_device_trigger_count(
                    trigger_info['room_ip'], 
                    trigger_info['trigger_count']
                )
                
                if device_info:
                    self._log_trigger_event(
                        trigger_info['room_ip'], 
                        device_info['name'], 
                        '闲置触发',
                        1,
                        trigger_info['trigger_count'],
                        device_info['original_count'],
                        device_info['remaining_count'],
                        room_id=trigger_info['room_id']
                    )
            except Exception as e:
                self.logger.error(f"执行空闲触发失败: {e}", exc_info=True)
        
    def _run_loop(self):
        """主循环"""
        self.logger.info("礼物触发服务主循环开始")
        loop_count = 0
        while self.running:
            try:
                loop_count += 1
                self.logger.info(f"主循环执行第{loop_count}次，开始处理礼物消息...")
                self._process_gift_messages()
                self.logger.info(f"主循环执行第{loop_count}次完成，等待{self.poll_interval}秒...")
                time.sleep(self.poll_interval)
            except Exception as e:
                self.logger.error(f"处理礼物消息时出错: {e}", exc_info=True)
                time.sleep(5)
        self.logger.info(f"礼物触发服务主循环结束，共执行{loop_count}次")
    
    def _process_gift_messages(self):
        """处理礼物消息"""
        with self.lock:
            mysql_conn = self._get_mysql_connection()
            if not mysql_conn:
                self.logger.error("无法获取MySQL连接")
                return
            
            try:
                # 提交任何挂起的事务，确保读取最新数据
                mysql_conn.commit()

                with mysql_conn.cursor() as cursor:
                    # 获取MySQL当前时间
                    cursor.execute("SELECT NOW() as mysql_now")
                    mysql_now = cursor.fetchone()['mysql_now']

                    # 计算时间阈值（当前时间减去超时时间）
                    time_threshold = datetime.now() - timedelta(minutes=self.trigger_timeout)

                    self.logger.info(f"[GIFT DEBUG] Python当前时间: {datetime.now()}, MySQL当前时间: {mysql_now}")
                    self.logger.info(f"[GIFT DEBUG] 时间阈值: {time_threshold}, 超时时间: {self.trigger_timeout}分钟")

                    # 先查询所有未触发的礼物消息（不看时间）
                    cursor.execute("SELECT COUNT(*) as cnt FROM msg WHERE type = 'gif' AND `trigger` = 0")
                    total_untriggered = cursor.fetchone()['cnt']
                    self.logger.info(f"[GIFT DEBUG] 所有未触发礼物总数: {total_untriggered}")

                    # 查询最新的未触发礼物
                    cursor.execute("SELECT id, created_at FROM msg WHERE type = 'gif' AND `trigger` = 0 ORDER BY created_at DESC LIMIT 1")
                    latest = cursor.fetchone()
                    if latest:
                        self.logger.info(f"[GIFT DEBUG] 最新未触发礼物: ID={latest['id']}, created_at={latest['created_at']}")
                        # 比较时间
                        time_diff = latest['created_at'] - time_threshold
                        self.logger.info(f"[GIFT DEBUG] 最新记录时间 - 时间阈值 = {time_diff.total_seconds()/60:.1f}分钟")
                        self.logger.info(f"[GIFT DEBUG] 条件检查: {latest['created_at']} >= {time_threshold} ? {latest['created_at'] >= time_threshold}")

                    # 查询未触发的礼物消息，且在时间范围内，且giftcount>0
                    query = """
                        SELECT id, room, name, giftname, giftcount, giftdiamond, created_at
                        FROM msg
                        WHERE type = 'gif'
                          AND `trigger` = 0
                          AND created_at >= %s
                          AND giftcount > 0
                        ORDER BY created_at DESC
                        LIMIT 100
                    """
                    cursor.execute(query, (time_threshold,))
                    gift_messages = cursor.fetchall()

                    self.logger.info(f"[GIFT DEBUG] 查询到 {len(gift_messages)} 条未触发的礼物消息，时间阈值: {time_threshold}")

                    if not gift_messages:
                        self.logger.info("[GIFT DEBUG] 没有未触发的礼物消息，跳过处理")
                        return

                    self.logger.info(f"[GIFT DEBUG] 发现 {len(gift_messages)} 条未触发的礼物消息")
                    
                    # 处理每条礼物消息
                    for msg in gift_messages:
                        self._process_single_gift(cursor, msg)
                    
                    mysql_conn.commit()
                    
            except Exception as e:
                mysql_conn.rollback()
                self.logger.error(f"处理礼物消息失败: {e}", exc_info=True)
    
    def _process_single_gift(self, cursor, msg: Dict):
        """处理单条礼物消息
        
        Args:
            cursor: MySQL游标
            msg: 礼物消息字典
        """
        msg_id = msg['id']
        room = msg['room']
        gift_name = msg.get('giftname', '')  # 直接从giftname字段获取
        gift_count = msg.get('giftcount', 0)  # 获取礼物数量
        gift_diamond = msg.get('giftdiamond', 0)  # 获取礼物价值
        created_at = msg['created_at']
        
        try:
            self.logger.info(f"开始处理礼物消息: ID={msg_id}, room={room}, gift={gift_name}, count={gift_count}, value={gift_diamond}")
            
            # 再次检查消息是否超时（防止处理过程中超时）
            if self._is_message_expired(created_at):
                self.logger.info(f"消息已超时，跳过处理: ID={msg_id}, created_at={created_at}")
                # 标记为已触发（即使超时也标记，避免重复查询）
                self._mark_message_processed(cursor, msg_id, "消息超时")
                return

            # 检查房间是否已关闭
            room_id = self._get_room_id_by_ip(room)
            if room_id:
                with self.sqlite_db._get_connection() as conn:
                    enabled_row = conn.execute("SELECT enabled FROM rooms WHERE id = ?", (room_id,)).fetchone()
                    if enabled_row and not bool(enabled_row[0]):
                        self.logger.info(f"房间{room_id}已关闭，跳过礼物触发: ID={msg_id}")
                        self._mark_message_processed(cursor, msg_id, "房间已关闭")
                        return

            # 查询gift_triggers表，找到匹配的触发配置（传入gift_count用于计算实际触发次数）
            gift_trigger = self._find_gift_trigger(room, gift_name, gift_count)

            if gift_trigger:
                # 找到特定礼物配置，按配置触发
                trigger_count = gift_trigger['trigger_count']  # 已经是计算后的实际触发次数
                device_type = gift_trigger.get('device_type', 'main')
                device_config = gift_trigger.get('device_config', None)
                
                self.logger.info(f"匹配到特定礼物配置: room={room}, gift={gift_name}, base_count={gift_trigger.get('base_count', 0)}, gift_count={gift_count}, total_count={trigger_count}, device_type={device_type}")

                # 根据 device_type 调用不同的处理方法
                if device_type == 'programmable':
                    # 编程设备：更新指定的 prog 设备
                    device_info = self._update_programmable_device(room, trigger_count, device_config)
                    if device_info:
                        self._log_trigger_event(room, device_info['name'], gift_name, gift_count, 
                                               trigger_count, device_info['original_count'], 
                                               device_info['remaining_count'])
                else:
                    # 主触发装置（默认）：更新 gift_event 不为空的设备
                    device_info = self._update_device_trigger_count(room, trigger_count)
                    if device_info:
                        self._log_trigger_event(room, device_info['name'], gift_name, gift_count,
                                               trigger_count, device_info['original_count'],
                                               device_info['remaining_count'])

                # 标记消息为已处理
                self._mark_message_processed(cursor, msg_id, "成功处理")
            else:
                # 未找到特定礼物配置，尝试未知礼物兜底
                self._handle_unknown_gift(cursor, msg_id, room, gift_count, gift_diamond, gift_name)
            
        except Exception as e:
            self.logger.error(f"处理礼物消息失败 (ID={msg_id}): {e}", exc_info=True)
    
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
                # 【修复】使用本地时间而不是 UTC 时间
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
    
    def _handle_unknown_gift(self, cursor, msg_id: int, room: str, gift_count: int, gift_diamond: int, gift_name: str = "未知礼物") -> None:
        """处理未知礼物触发（兜底策略）
        
        Args:
            cursor: MySQL游标
            msg_id: 消息ID
            room: 房间IP
            gift_count: 礼物数量
            gift_diamond: 单个礼物价值
            gift_name: 礼物名称（默认为"未知礼物"）
        """
        try:
            # 获取房间ID
            room_id = self._get_room_id_by_ip(room)
            if not room_id:
                self.logger.info(f"未找到房间配置: room={room}")
                self._mark_message_processed(cursor, msg_id, "未找到房间配置")
                return
            
            # 查询是否启用未知礼物触发
            with self.sqlite_db._get_connection() as conn:
                sqlite_cursor = conn.cursor()
                sqlite_cursor.execute(
                    "SELECT device_config FROM gift_triggers WHERE room_id = ? AND gift_name = '未知礼物'",
                    (room_id,)
                )
                row = sqlite_cursor.fetchone()
            
            if not row or not row[0]:
                self.logger.info(f"房间 {room_id} 未启用未知礼物触发")
                self._mark_message_processed(cursor, msg_id, "未启用未知礼物触发")
                return
            
            # 解析配置
            import json
            try:
                config = json.loads(row[0])
                threshold = config.get('threshold', 10)
            except json.JSONDecodeError:
                self.logger.error(f"未知礼物配置解析失败: {row[0]}")
                self._mark_message_processed(cursor, msg_id, "配置解析失败")
                return
            
            # 计算总价值和触发次数
            total_value = gift_count * gift_diamond
            if threshold <= 0:
                self.logger.info(f"阈值无效: threshold={threshold}")
                self._mark_message_processed(cursor, msg_id, "阈值无效")
                return
            
            trigger_count = total_value / threshold
            
            # 只有 >=1 才触发
            if trigger_count < 1:
                self.logger.info(f"未达阈值不触发: room={room_id}, total_value={total_value}, threshold={threshold}, trigger_count={trigger_count}")
                self._mark_message_processed(cursor, msg_id, "未达阈值")
                return
            
            # 向上取整
            import math
            actual_trigger_count = math.ceil(trigger_count)
            
            self.logger.info(f"未知礼物触发: room={room_id}, gift_count={gift_count}, gift_value={gift_diamond}, "
                           f"total_value={total_value}, threshold={threshold}, trigger_count={actual_trigger_count}")
            
            # 触发主触发装置
            device_info = self._update_device_trigger_count(room, actual_trigger_count)
            if device_info:
                self._log_trigger_event(room, device_info['name'], gift_name, gift_count,
                                       actual_trigger_count, device_info['original_count'],
                                       device_info['remaining_count'])
            
            # 标记消息为已处理
            self._mark_message_processed(cursor, msg_id, "未知礼物触发成功")
            
        except Exception as e:
            self.logger.error(f"处理未知礼物失败: {e}", exc_info=True)
            self._mark_message_processed(cursor, msg_id, "处理失败")
    
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
        """检查消息是否超时

        Args:
            created_at: 消息创建时间

        Returns:
            True表示超时，False表示未超时
        """
        try:
            now = datetime.now()
            # 如果created_at是字符串，转换为datetime对象
            if isinstance(created_at, str):
                created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')

            # 计算时间差
            time_diff = now - created_at
            expired_minutes = time_diff.total_seconds() / 60

            is_expired = expired_minutes > self.trigger_timeout
            self.logger.info(f"[GIFT DEBUG] 时间检查: now={now}, created_at={created_at}, diff={expired_minutes:.2f}分钟, timeout={self.trigger_timeout}分钟, is_expired={is_expired}")

            return is_expired
        except Exception as e:
            self.logger.error(f"检查消息超时失败: {e}", exc_info=True)
            return False
    
    def _find_gift_trigger(self, room: str, gift_name: str, gift_count: int = 1) -> Optional[Dict]:
        """查找礼物触发配置
        
        使用包含匹配：如果 gift_triggers 表中的 gift_name 包含在传入的 gift_name 中，则匹配成功
        实际触发次数 = 配置表中的trigger_count × msg表中的giftcount
        
        Args:
            room: 房间IP地址
            gift_name: 礼物名称（从msg.giftname字段获取）
            gift_count: 礼物数量（从msg.giftcount字段获取）
            
        Returns:
            触发配置字典，如果未找到返回None
        """
        try:
            # 从SQLite数据库查询
            with self.sqlite_db._get_connection() as conn:
                cursor = conn.cursor()

                # 先通过IP地址查找room_id
                cursor.execute("""
                    SELECT id FROM rooms WHERE ip = ?
                """, (room,))
                room_row = cursor.fetchone()

                if not room_row:
                    self.logger.info(f"[GIFT DEBUG] 未找到房间配置: room={room}")
                    # 列出所有可用的房间
                    cursor.execute("SELECT id, ip, name FROM rooms")
                    all_rooms = cursor.fetchall()
                    self.logger.info(f"[GIFT DEBUG] 可用房间列表: {all_rooms}")
                    return None

                room_id = room_row[0]
                self.logger.info(f"[GIFT DEBUG] 找到房间配置: room={room}, room_id={room_id}")

                # 查询该房间的所有礼物触发配置
                cursor.execute("""
                    SELECT room_id, gift_name, trigger_count, device_type, device_config
                    FROM gift_triggers
                    WHERE room_id = ?
                """, (room_id,))
                all_configs = cursor.fetchall()
                
                self.logger.info(f"[GIFT DEBUG] 房间 {room_id} 的所有礼物配置: {all_configs}")
                self.logger.info(f"[GIFT DEBUG] 正在查找包含 '{gift_name}' 的配置...")
                
                # 使用包含匹配：检查传入的gift_name是否包含配置的gift_name
                for row in all_configs:
                    config_gift_name = row[1]  # gift_name 字段
                    base_trigger_count = row[2]  # 基础触发次数
                    
                    # 模糊匹配：配置的gift_name包含在传入的gift_name中
                    if config_gift_name and config_gift_name in gift_name:
                        # 计算实际触发次数 = 基础次数 × 礼物数量
                        actual_trigger_count = base_trigger_count * gift_count
                        
                        self.logger.info(f"[GIFT DEBUG] 找到匹配的配置: room_id={room_id}, config_gift_name='{config_gift_name}', input_gift_name='{gift_name}', base_count={base_trigger_count}, gift_count={gift_count}, actual_count={actual_trigger_count}, device_type={row[3]}")
                        return {
                            'room_id': row[0],
                            'gift_name': row[1],
                            'trigger_count': actual_trigger_count,  # 实际触发次数
                            'base_count': base_trigger_count,  # 基础触发次数（用于日志）
                            'device_type': row[3],
                            'device_config': row[4]
                        }

                # 未找到配置
                self.logger.info(f"[GIFT DEBUG] 未找到包含 '{gift_name}' 的礼物触发配置")
                return None
        except Exception as e:
            self.logger.error(f"查询礼物触发配置失败: {e}", exc_info=True)
            return None
    
    def _update_device_trigger_count(self, room: str, trigger_count: int) -> Optional[Dict]:
        """更新设备的触发剩余次数
        
        只更新 name='trigger' 的主触发装置，而不是房间内所有设备
        
        Args:
            room: 房间IP地址
            trigger_count: 触发次数
            
        Returns:
            设备信息字典，包含name, original_count, remaining_count，如果失败返回None
        """
        try:
            with self.sqlite_db._get_connection() as conn:
                cursor = conn.cursor()
                
                # 先通过IP地址查找room_id
                cursor.execute("""
                    SELECT id FROM rooms WHERE ip = ?
                """, (room,))
                room_row = cursor.fetchone()
                
                if not room_row:
                    self.logger.warning(f"未找到房间配置: room={room}")
                    return None
                
                room_id = room_row[0]
                
                # 只更新 name='trigger' 的主触发装置
                self.logger.info(f"准备更新主触发装置: room_id={room_id}, add_count={trigger_count}")
                
                # 查询更新前的值（只查 name='trigger' 的设备）
                cursor.execute("""
                    SELECT id, name, trigger_remaining_count, gift_event
                    FROM devices 
                    WHERE room_id = ? AND enabled = 1 AND name = 'trigger'
                """, (room_id,))
                before_devices = cursor.fetchall()
                before_list = [(row[0], row[1], row[2], row[3]) for row in before_devices]
                self.logger.info(f"更新前的主触发装置状态: {before_list}")
                
                # 如果没有找到主触发装置，记录警告
                if not before_devices:
                    self.logger.warning(f"房间 {room_id} 没有找到 name='trigger' 的主触发装置")
                    # 列出该房间的所有设备供调试
                    cursor.execute("""
                        SELECT id, name, enabled, gift_event
                        FROM devices 
                        WHERE room_id = ?
                    """, (room_id,))
                    all_devices = cursor.fetchall()
                    all_list = [(row[0], row[1], row[2], row[3]) for row in all_devices]
                    self.logger.info(f"房间 {room_id} 的所有设备: {all_list}")
                    return None
                
                # 获取更新前的触发次数
                original_count = before_devices[0][2] if before_devices else 0
                device_name = before_devices[0][1] if before_devices else 'trigger'
                
                # 只更新 name='trigger' 的主触发装置
                # 同时设置 next_trigger_time 为当前时间，让 TriggerQueueManager 立即执行
                current_time = datetime.now().isoformat()
                cursor.execute("""
                    UPDATE devices
                    SET trigger_remaining_count = trigger_remaining_count + ?,
                        next_trigger_time = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE room_id = ? AND enabled = 1 AND name = 'trigger'
                """, (trigger_count, current_time, room_id))
                
                affected_rows = cursor.rowcount
                
                # 验证更新结果
                cursor.execute("""
                    SELECT id, name, trigger_remaining_count, gift_event
                    FROM devices 
                    WHERE room_id = ? AND enabled = 1 AND name = 'trigger'
                """, (room_id,))
                updated_devices = cursor.fetchall()
                updated_list = [(row[0], row[1], row[2], row[3]) for row in updated_devices]
                self.logger.info(f"更新后的主触发装置状态: {updated_list}")
                
                if affected_rows > 0:
                    self.logger.info(f"更新了 {affected_rows} 个主触发装置的触发次数: room={room}, add={trigger_count}")
                    remaining_count = updated_devices[0][2] if updated_devices else original_count + trigger_count
                    return {
                        'name': device_name,
                        'original_count': original_count,
                        'remaining_count': remaining_count
                    }
                else:
                    self.logger.warning(f"没有找到启用的主触发装置: room={room}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"更新设备触发次数失败: {e}", exc_info=True)
            return None

    def _update_programmable_device(self, room: str, trigger_count: int, device_config: str) -> Optional[Dict]:
        """更新可编程设备的触发剩余次数
        
        根据 device_config 中的 device_name 更新对应的编程设备
        
        Args:
            room: 房间IP地址
            trigger_count: 触发次数
            device_config: 设备配置JSON字符串，如 {"device_name": "prog1", "trigger_on_duration": 1, "trigger_off_duration": 1}
            
        Returns:
            设备信息字典，包含name, original_count, remaining_count，如果失败返回None
        """
        try:
            import json
            config = json.loads(device_config) if device_config else {}
            device_name = config.get('device_name', '')
            
            if not device_name:
                self.logger.warning(f"device_config 中没有 device_name: {device_config}")
                return None
            
            with self.sqlite_db._get_connection() as conn:
                cursor = conn.cursor()
                
                # 先通过IP地址查找room_id
                cursor.execute("""
                    SELECT id FROM rooms WHERE ip = ?
                """, (room,))
                room_row = cursor.fetchone()
                
                if not room_row:
                    self.logger.warning(f"未找到房间配置: room={room}")
                    return None
                
                room_id = room_row[0]
                
                self.logger.info(f"准备更新编程设备: room_id={room_id}, device_name={device_name}, add_count={trigger_count}")
                
                # 查询更新前的值
                cursor.execute("""
                    SELECT id, name, trigger_remaining_count
                    FROM devices 
                    WHERE room_id = ? AND enabled = 1 AND name = ?
                """, (room_id, device_name))
                before_device = cursor.fetchone()
                
                if before_device:
                    self.logger.info(f"更新前的编程设备状态: id={before_device[0]}, name={before_device[1]}, count={before_device[2]}")
                else:
                    self.logger.warning(f"房间 {room_id} 没有找到编程设备: {device_name}")
                    # 列出该房间的所有设备供调试
                    cursor.execute("""
                        SELECT id, name, enabled
                        FROM devices 
                        WHERE room_id = ?
                    """, (room_id,))
                    all_devices = cursor.fetchall()
                    all_list = [(row[0], row[1], row[2]) for row in all_devices]
                    self.logger.info(f"房间 {room_id} 的所有设备: {all_list}")
                    return None
                
                # 获取更新前的触发次数
                original_count = before_device[2] if before_device else 0
                
                # 更新指定的编程设备
                cursor.execute("""
                    UPDATE devices
                    SET trigger_remaining_count = trigger_remaining_count + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE room_id = ? AND enabled = 1 AND name = ?
                """, (trigger_count, room_id, device_name))
                
                affected_rows = cursor.rowcount
                
                # 验证更新结果
                cursor.execute("""
                    SELECT id, name, trigger_remaining_count
                    FROM devices 
                    WHERE room_id = ? AND enabled = 1 AND name = ?
                """, (room_id, device_name))
                updated_device = cursor.fetchone()
                
                if updated_device:
                    self.logger.info(f"更新后的编程设备状态: id={updated_device[0]}, name={updated_device[1]}, count={updated_device[2]}")
                
                if affected_rows > 0:
                    self.logger.info(f"更新了编程设备的触发次数: room={room}, device={device_name}, add={trigger_count}")
                    remaining_count = updated_device[2] if updated_device else original_count + trigger_count
                    return {
                        'name': device_name,
                        'original_count': original_count,
                        'remaining_count': remaining_count
                    }
                else:
                    self.logger.warning(f"没有找到编程设备: room={room}, device={device_name}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"更新编程设备触发次数失败: {e}", exc_info=True)
            return None
    
    def _mark_message_processed(self, cursor, msg_id: int, reason: str = ""):
        """标记消息为已处理

        Args:
            cursor: MySQL游标
            msg_id: 消息ID
            reason: 标记原因，用于调试
        """
        try:
            cursor.execute("UPDATE msg SET `trigger` = 1 WHERE id = %s", (msg_id,))
            self.logger.info(f"[GIFT DEBUG] 标记消息为已处理: ID={msg_id}, reason={reason}")
        except Exception as e:
            self.logger.error(f"标记消息处理状态失败 (ID={msg_id}): {e}", exc_info=True)


def create_gift_trigger_service(config: Dict) -> Optional[GiftTriggerService]:
    """创建礼物触发服务实例
    
    Args:
        config: 配置字典
        
    Returns:
        GiftTriggerService实例，如果未启用或pymysql不可用返回None
    """
    if not config.get('enabled', False):
        return None
    
    if not PYMYSQL_AVAILABLE:
        logger.warning("pymysql库未安装，礼物触发服务无法启动")
        return None
    
    return GiftTriggerService(config)
