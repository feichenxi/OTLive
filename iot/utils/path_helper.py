"""
跨平台路径工具
处理Windows和Linux的路径差异
"""
import os
import sys


class PathHelper:
    """路径助手类"""

    @staticmethod
    def get_base_dir():
        """获取程序基础目录"""
        if getattr(sys, 'frozen', False):
            # EXE运行模式
            return os.path.dirname(sys.executable)
        else:
            # 开发模式
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def get_config_ini_path():
        """获取config.ini路径"""
        # 优先检查环境变量
        if 'IOT_CONFIG_PATH' in os.environ:
            env_path = os.environ['IOT_CONFIG_PATH']
            if os.path.exists(env_path):
                return env_path

        # EXE运行模式 - 从打包内部读取
        if getattr(sys, 'frozen', False):
            meipass_config = os.path.join(sys._MEIPASS, 'config.ini')
            if os.path.exists(meipass_config):
                return meipass_config

        base_dir = PathHelper.get_base_dir()

        # 可能的路径列表 - 仅Windows平台
        possible_paths = [
            os.path.join(base_dir, 'config.ini'),
            os.path.join(base_dir, 'iot', 'config.ini'),
            os.path.join(base_dir, '..', 'config.ini')
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # 默认返回项目根目录的config.ini
        return os.path.join(base_dir, 'config.ini')

    @staticmethod
    def get_config_db_path():
        if 'IOT_DB_PATH' in os.environ:
            env_path = os.environ['IOT_DB_PATH']
            if os.path.exists(env_path):
                return env_path

        base_dir = PathHelper.get_base_dir()

        possible_paths = [
            os.path.join(base_dir, 'iot', 'database', 'config.db'),
            os.path.join(base_dir, 'database', 'config.db'),
            os.path.join(base_dir, 'config.db'),
            os.path.join(base_dir, 'iot', 'config.db'),
            os.path.join(base_dir, '..', 'config.db')
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return os.path.join(base_dir, 'database', 'config.db')

    @staticmethod
    def get_log_dir():
        """获取日志目录"""
        import tempfile
        log_dir = os.path.join(tempfile.gettempdir(), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    @staticmethod
    def get_warn_log_dir():
        """获取warn日志目录 - 始终在exe同级目录"""
        base_dir = PathHelper.get_base_dir()
        log_dir = os.path.join(base_dir, 'log')
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    @staticmethod
    def is_windows():
        """判断是否为Windows平台"""
        return sys.platform == 'win32'

    @staticmethod
    def is_linux():
        """判断是否为Linux平台"""
        return sys.platform.startswith('linux')

    @staticmethod
    def get_local_ip():
        """获取本机IP地址"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
