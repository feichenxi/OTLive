import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


class Logger:
    _instance = None
    _logger = None
    _file_handler = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._logger is None:
            self._setup_logger()

    def _setup_logger(self, log_file=None, level=logging.WARNING, max_bytes=1048576, backup_count=0):
        import tempfile
        if log_file is None:
            log_file = os.path.join(tempfile.gettempdir(), 'logs', 'system.log')
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        self._logger = logging.getLogger('IoT_Voice_Control')
        self._logger.setLevel(level)

        if not self._logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            self._file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8',
                delay=True
            )
            self._file_handler.setFormatter(formatter)
            self._file_handler.setLevel(level)
            self._logger.addHandler(self._file_handler)

            # 阻止日志传递给父 logger，避免重复输出
            self._logger.propagate = False

    def close(self):
        if self._file_handler:
            self._file_handler.close()
            self._file_handler = None

    def debug(self, message):
        self._logger.debug(message)

    def info(self, message):
        self._logger.info(message)

    def warning(self, message):
        self._logger.warning(message)

    def error(self, message):
        self._logger.error(message)

    def critical(self, message):
        self._logger.critical(message)

    def exception(self, message):
        self._logger.exception(message)


def get_logger():
    return Logger()
