#!/usr/bin/env python3
import sys
import os
import threading

os.environ['PYTHONUNBUFFERED'] = '1'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)

import signal
import time
import logging
import io

if sys.platform == 'win32':
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR)
for handler in werkzeug_logger.handlers[:]:
    werkzeug_logger.removeHandler(handler)
werkzeug_logger.propagate = False

from web.app import WebApp
from common.logger import get_logger
from common.database_manager import get_database_manager
from common.license_verifier import LicenseVerifier

try:
    from ai.ai_manager import AIManager
    HAS_AI_MANAGER = True
except ImportError:
    HAS_AI_MANAGER = False

from utils.path_helper import PathHelper
HAS_PATH_HELPER = True

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

class IoTVoiceControlSystem:
    def __init__(self):
        self.logger = get_logger()
        self.config = get_database_manager()
        self.web_app = None
        self.license_verifier = None
        self.ai_manager = None
        self.running = False
        self.webview_window = None

    def _get_mysql_config(self):
        mysql_config = {
            'host': 'YOUR_MYSQL_HOST',
            'port': 3306,
            'db': 'YOUR_MYSQL_DB',
            'user': 'YOUR_MYSQL_USER',
            'password': 'YOUR_MYSQL_PASSWORD',
            'charset': 'utf8mb4'
        }
        return mysql_config

    def _shutdown_system(self):
        self.logger.critical("授权验证失败，正在关闭系统...")
        self.running = False
        self.shutdown()
        os._exit(1)

    def initialize(self):
        print("╔" + "═" * 58 + "╗")
        print("║" + " " * 58 + "║")
        print("║" + "      [系统] 规模化直播矩阵系统服务启动中...".ljust(50) + "║")
        print("║" + " " * 58 + "║")
        print("╚" + "═" * 58 + "╝")

        self.logger.info("=" * 60)
        self.logger.info("规模化直播矩阵系统启动中...")
        self.logger.info("=" * 60)
        
        system_config = self.config.get_system_config()
        self.logger.info(f"系统版本: {system_config.get('version', '1.0.0')}")
        self.logger.info(f"调试模式: {system_config.get('debug', False)}")
        self.logger.info(f"模拟模式: {system_config.get('simulation_mode', False)}")

        mysql_config = self._get_mysql_config()
        self.license_verifier = LicenseVerifier(mysql_config)
        
        success, message = self.license_verifier.verify_on_startup()
        if not success:
            self.logger.error(f"授权验证失败: {message}")
            return False

        self.web_app = WebApp()

        if not self.web_app.initialize():
            self.logger.error("系统初始化失败")
            return False
        
        self._init_ai_manager()

        self.license_verifier.start_periodic_verify(shutdown_callback=self._shutdown_system)

        self.logger.info("系统初始化成功")
        return True

    def _init_ai_manager(self):
        if not HAS_AI_MANAGER:
            self.logger.warning("AIManager模块未找到，跳过AI管理器初始化")
            return
        
        try:
            license_id = self.license_verifier.get_license_id() if self.license_verifier else None
            
            if not license_id:
                self.logger.warning("无法获取license_id，AI管理器不会处理消息")
            
            self.ai_manager = AIManager(license_id=license_id, database_manager=self.config)
            self.web_app.ai_manager = self.ai_manager
            
            ai_voice_player = self.web_app.get_ai_voice_player()
            if ai_voice_player:
                self.ai_manager.set_ai_voice_player(ai_voice_player)
            self.ai_manager.start()
            self.logger.info(f"AI管理器已启动 (license_id={license_id})")
                
        except Exception as e:
            self.logger.warning(f"初始化AI管理器失败，系统将继续运行: {e}")
            import traceback
            self.logger.warning(traceback.format_exc())
            self.ai_manager = None
            self.web_app.ai_manager = None

    def _on_webview_closed(self):
        self.logger.info("Webview窗口已关闭，正在关闭系统...")
        self.shutdown()
        sys.exit(0)

    def run(self):
        if not self.initialize():
            self.logger.error("无法启动系统")
            sys.exit(1)

        self.running = True
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        server_config = self.config.get_server_config()
        bind_host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 5000)
        debug = self.config.get_system_config().get('debug', False)
        
        access_host = '127.0.0.1'

        self.logger.info(f"Web服务器启动: http://{access_host}:{port}")

        def start_flask_server():
            try:
                self.web_app.run(host=bind_host, port=port, debug=debug, allow_unsafe_werkzeug=True)
            except Exception as e:
                self.logger.error(f"Flask服务器运行错误: {e}")

        flask_thread = threading.Thread(target=start_flask_server, daemon=True)
        flask_thread.start()

        time.sleep(2)

        if HAS_WEBVIEW:
            try:
                self.logger.info("正在启动Webview窗口...")
                
                self.webview_window = webview.create_window(
                    title='规模化直播矩阵系统',
                    url=f'http://{access_host}:{port}',
                    width=1280,
                    height=720,
                    resizable=True,
                    confirm_close=True
                )
                
                self.logger.info("Webview窗口已创建，正在启动...")
                webview.start(
                    localization={
                        'global.quitConfirmation': '确定要退出系统吗？',
                        'global.ok': '确定',
                        'global.quit': '退出',
                        'global.cancel': '取消'
                    }
                )
                
                self._on_webview_closed()
                
            except Exception as e:
                self.logger.error(f"Webview启动失败，回退到命令行模式: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                self._fallback_mode(bind_host, port)
        else:
            self.logger.warning("Webview库未安装，使用命令行模式")
            self._fallback_mode(bind_host, port)

    def _fallback_mode(self, host, port):
        self.logger.info(f"Web服务器运行在: http://{host}:{port}")
        self.logger.info("按 Ctrl+C 停止系统")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("接收到中断信号")
        except Exception as e:
            self.logger.error(f"系统运行错误: {e}")
        finally:
            self.shutdown()

    def _signal_handler(self, signum, frame):
        self.logger.info(f"接收到信号 {signum}")
        self.running = False
        self.shutdown()
        sys.exit(0)

    def shutdown(self):
        if not self.running:
            return

        self.logger.info("正在关闭系统...")
        
        if self.ai_manager:
            self.ai_manager.stop()
        
        if self.license_verifier:
            self.license_verifier.stop()
        
        if self.web_app:
            self.web_app.shutdown()

        self.logger.info("系统已关闭")
        self.logger.info("=" * 60)


def main():
    system = IoTVoiceControlSystem()
    system.run()


if __name__ == '__main__':
    main()
