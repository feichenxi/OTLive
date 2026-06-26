import uuid
import hashlib
import hmac
import time
import json
import threading
import sys
import os
from datetime import datetime, timedelta
from common.logger import get_logger

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

try:
    import ctypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

logger = get_logger()

# 检查是否启用调试模式（通过环境变量或命令行参数）
def is_debug_mode():
    """检查是否处于调试模式"""
    return (
        os.environ.get('OTLive_DEBUG', '').lower() == 'true' or
        '--debug' in sys.argv or
        '-d' in sys.argv
    )

LICENSE_ENABLED = not is_debug_mode()
VERIFY_INTERVAL_HOURS = 1
RETRY_INTERVAL_MINUTES = 10
MAX_FAILURES = 3
TIMESTAMP_VALID_SECONDS = 5
SECRET_KEY = b'otlive-license-secret-key-2026-v1'

if not LICENSE_ENABLED:
    logger.warning("=" * 60)
    logger.warning("警告: 授权验证已禁用（调试模式）")
    logger.warning("=" * 60)


class LicenseVerifier:
    def __init__(self, mysql_config):
        self.mysql_config = mysql_config
        self.mysql_connection = None
        self._machine_code = None
        self._running = False
        self._verify_thread = None
        self._failure_count = 0
        self._shutdown_callback = None
        self._last_verify_success = False
        self._license_id = None

    def _get_cpu_id(self):
        """获取CPU ID"""
        if HAS_WMI and sys.platform == 'win32':
            try:
                c = wmi.WMI()
                for processor in c.Win32_Processor():
                    if processor.ProcessorId:
                        cpu_id = processor.ProcessorId.strip().upper()
                        logger.debug(f"获取到CPU ID: {cpu_id}")
                        return cpu_id
            except Exception as e:
                logger.warning(f"获取CPU ID失败: {e}")
        
        raise RuntimeError("无法获取CPU ID")

    def get_machine_code(self):
        if self._machine_code is None:
            cpu_id = self._get_cpu_id()
            self._machine_code = hashlib.md5(cpu_id.encode('utf-8')).hexdigest()
        
        return self._machine_code

    def get_raw_mac_address(self):
        mac = uuid.getnode()
        return ':'.join(('%012X' % mac)[i:i + 2] for i in range(0, 12, 2))

    def get_license_id(self):
        """获取当前机器的license_id"""
        return self._license_id

    def _encrypt_data(self, data):
        data_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
        timestamp = int(time.time())
        message = f"{data_str}|{timestamp}".encode('utf-8')
        signature = hmac.new(SECRET_KEY, message, hashlib.sha256).hexdigest()
        encrypted = f"{data_str}|{timestamp}|{signature}"
        return encrypted

    def _decrypt_data(self, encrypted_str):
        try:
            parts = encrypted_str.split('|')
            if len(parts) != 3:
                return None, "数据格式错误"

            data_str, timestamp_str, signature = parts
            timestamp = int(timestamp_str)

            current_time = int(time.time())
            if abs(current_time - timestamp) > TIMESTAMP_VALID_SECONDS:
                return None, "时间戳无效或已过期"

            message = f"{data_str}|{timestamp}".encode('utf-8')
            expected_signature = hmac.new(SECRET_KEY, message, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                return None, "签名验证失败"

            data = json.loads(data_str)
            return data, None
        except Exception as e:
            logger.error(f"解密数据失败: {e}")
            return None, f"解密失败: {str(e)}"

    def _init_mysql_connection(self):
        try:
            self.mysql_connection = pymysql.connect(
                host=self.mysql_config['host'],
                port=self.mysql_config['port'],
                database=self.mysql_config['db'],
                user=self.mysql_config['user'],
                password=self.mysql_config['password'],
                charset=self.mysql_config.get('charset', 'utf8mb4'),
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=10
            )
            logger.info("MySQL授权服务器连接成功")
            return True
        except Exception as e:
            logger.error(f"MySQL授权服务器连接失败: {e}")
            self.mysql_connection = None
            return False

    def _get_mysql_connection(self):
        if self.mysql_connection is None:
            self._init_mysql_connection()
        else:
            try:
                self.mysql_connection.ping(reconnect=True)
            except:
                self._init_mysql_connection()
        return self.mysql_connection

    def _update_verify_log(self, machine_code, success, message):
        try:
            conn = self._get_mysql_connection()
            if not conn:
                return

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE license 
                    SET last_verify_at = NOW(), 
                        verify_count = verify_count + 1,
                        remark = %s
                    WHERE machine_code = %s
                """, (message, machine_code))
            conn.commit()
        except Exception as e:
            logger.warning(f"更新验证日志失败: {e}")

    def _verify_once(self):
        machine_code = self.get_machine_code()
        raw_mac = self.get_raw_mac_address()

        conn = self._get_mysql_connection()
        if not conn:
            return False, "无法连接授权服务器"

        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT id, machine_code, expire_date, license_type, 
                           max_rooms, features, status
                    FROM license 
                    WHERE machine_code = %s AND status = 1
                """
                cursor.execute(query, (machine_code,))
                result = cursor.fetchone()

                if not result:
                    self._update_verify_log(machine_code, False, "未找到授权记录")
                    return False, "未找到授权记录"

                self._license_id = result['id']
                expire_date = result['expire_date']
                if expire_date < datetime.now().date():
                    self._update_verify_log(machine_code, False, f"授权已过期({expire_date})")
                    return False, f"授权已过期(到期日期:{expire_date})"

                self._update_verify_log(machine_code, True, "验证成功")

                response_data = {
                    'machine_code': machine_code,
                    'raw_mac': raw_mac,
                    'result': 'success',
                    'expire_date': str(expire_date),
                    'license_type': result['license_type'],
                    'max_rooms': result['max_rooms']
                }

                encrypted_response = self._encrypt_data(response_data)

                decrypted_data, decrypt_error = self._decrypt_data(encrypted_response)
                if decrypt_error:
                    return False, decrypt_error

                if decrypted_data['machine_code'] != machine_code:
                    return False, "授权验证失败: 机器码不匹配"

                if decrypted_data['result'] != 'success':
                    return False, "授权验证失败"

                return True, "授权验证成功"

        except Exception as e:
            logger.error(f"授权验证异常: {e}")
            return False, f"验证异常: {str(e)}"

    def verify_on_startup(self):
        if not LICENSE_ENABLED:
            logger.info("授权验证已禁用")
            return True, "授权验证已禁用"

        logger.info("开始启动授权验证...")

        success, message = self._verify_once()

        if not success:
            machine_code = self.get_machine_code()
            raw_mac = self.get_raw_mac_address()
            encrypted_mac = self._encrypt_data({'machine_code': machine_code, 'raw_mac': raw_mac})
            self._show_license_error(message, encrypted_mac)
            return False, message

        logger.info("启动授权验证成功")
        self._failure_count = 0
        self._last_verify_success = True
        return True, message

    def _show_license_error(self, message, encrypted_mac):
        logger.error(f"授权验证失败: {message}")

        error_text = f"""
{'='*60}
授权验证失败
{'='*60}

错误信息: {message}

请将以下机器码复制给管理员进行授权:

{encrypted_mac}

{'='*60}
"""
        
        # 尝试使用Windows MessageBox
        if HAS_CTYPES and sys.platform == 'win32':
            try:
                # 尝试使用Windows API显示消息框
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"{message}\n\n机器码已保存到日志文件，请联系管理员授权。",
                    "授权验证失败",
                    0x10 | 0x0
                )
            except Exception as e:
                logger.error(f"显示Windows消息框失败: {e}")
        
        # 始终打印到日志和控制台
        print(error_text)
        logger.error(error_text)
        
        # 将机器码写入文件方便复制（保存到exe所在目录）
        try:
            # 获取exe所在目录（支持打包后的exe和普通python脚本）
            if getattr(sys, 'frozen', False):
                # 打包后的exe
                exe_dir = os.path.dirname(sys.executable)
            else:
                # 普通python脚本
                exe_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
            license_file = os.path.join(exe_dir, 'license_request.txt')
            with open(license_file, 'w', encoding='utf-8') as f:
                f.write(f"机器码: {encrypted_mac}\n")
                f.write(f"MAC地址: {self.get_raw_mac_address()}\n")
                f.write(f"请求时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            logger.info(f"机器码已保存到: {license_file}")
        except Exception as e:
            logger.error(f"保存机器码文件失败: {e}")

    def start_periodic_verify(self, shutdown_callback=None):
        if not LICENSE_ENABLED:
            return

        self._shutdown_callback = shutdown_callback
        self._running = True
        self._verify_thread = threading.Thread(target=self._periodic_verify_loop, daemon=True, name="LicenseVerifyThread")
        self._verify_thread.start()
        logger.info("周期性授权验证线程已启动")

    def _periodic_verify_loop(self):
        while self._running:
            try:
                if self._last_verify_success:
                    wait_seconds = VERIFY_INTERVAL_HOURS * 3600
                else:
                    wait_seconds = RETRY_INTERVAL_MINUTES * 60

                logger.info(f"等待 {wait_seconds} 秒后进行下次授权验证...")

                for _ in range(wait_seconds):
                    if not self._running:
                        break
                    time.sleep(1)

                if not self._running:
                    break

                success, message = self._verify_once()

                if success:
                    logger.info(f"周期性授权验证成功: {message}")
                    self._failure_count = 0
                    self._last_verify_success = True
                else:
                    logger.warning(f"周期性授权验证失败: {message}")
                    self._last_verify_success = False
                    self._failure_count += 1

                    if self._failure_count >= MAX_FAILURES:
                        logger.critical(f"授权验证连续失败 {MAX_FAILURES} 次，即将停止服务")
                        self._show_shutdown_warning(message)
                        if self._shutdown_callback:
                            self._shutdown_callback()
                        break

            except Exception as e:
                logger.error(f"周期性授权验证异常: {e}")
                self._last_verify_success = False

    def _show_shutdown_warning(self, message):
        if HAS_CTYPES and sys.platform == 'win32':
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"授权验证连续失败，服务即将停止\n\n错误信息: {message}",
                    "授权验证失败 - 服务停止",
                    0x10 | 0x0
                )
            except:
                print(f"\n{'!'*60}")
                print("授权验证连续失败，服务即将停止")
                print(f"错误信息: {message}")
                print(f"{'!'*60}\n")
        else:
            print(f"\n{'!'*60}")
            print("授权验证连续失败，服务即将停止")
            print(f"错误信息: {message}")
            print(f"{'!'*60}\n")

    def stop(self):
        self._running = False
        if self._verify_thread and self._verify_thread.is_alive():
            self._verify_thread.join(timeout=5)
        logger.info("授权验证线程已停止")
