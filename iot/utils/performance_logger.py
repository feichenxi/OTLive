#!/usr/bin/env python3
"""
性能日志记录器 - IoT 模块专用
用于诊断触发装置延迟问题
"""

import os
import time
import logging
import threading
import gc
import tempfile
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Optional


class PerformanceLogger:
    """性能日志记录器"""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = None, threshold_ms: int = 50, force_init: bool = False):
        """初始化性能日志记录器
        
        Args:
            log_dir: 日志目录路径
            threshold_ms: 慢操作阈值（毫秒）
            force_init: 强制重新初始化（用于代码更新后）
        """
        if PerformanceLogger._initialized and not force_init:
            return

        if log_dir is None:
            # 默认在 temp/logs/ 目录
            log_dir = os.path.join(tempfile.gettempdir(), 'logs')

        self.log_dir = log_dir
        self.threshold_ms = threshold_ms
        self.last_trigger_time = None
        self.trigger_count = 0

        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)

        # 创建性能日志文件
        log_file = os.path.join(log_dir, 'trigger_performance.log')

        # 配置性能日志记录器
        self.logger = logging.getLogger('IoT.Performance')
        self.logger.setLevel(logging.DEBUG)

        # 禁止向上传播到根记录器（避免输出到控制台）
        self.logger.propagate = False

        # 清除现有处理器
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # 使用翻转文件处理器，限制文件大小为1M，不保留备份
        handler = RotatingFileHandler(
            log_file,
            maxBytes=1048576,
            backupCount=0,
            encoding='utf-8',
            delay=True
        )
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        PerformanceLogger._initialized = True

        # GC统计
        self.gc_stats = {'collections': 0}

        self.logger.info("=" * 80)
        self.logger.info("IoT 性能日志记录器启动")
        self.logger.info(f"慢操作阈值: {threshold_ms}ms")
        self.logger.info("=" * 80)

    def log_trigger(self, operation: str, exec_time_ms: float, extra_info: Dict = None):
        """记录触发操作"""
        self.trigger_count += 1
        current_time = time.time()

        # 计算间隔偏差（预期1秒间隔）
        interval_deviation_ms = 0
        if self.last_trigger_time:
            expected_interval = 1000  # 预期1秒间隔
            actual_interval = (current_time - self.last_trigger_time) * 1000
            interval_deviation_ms = actual_interval - expected_interval

        self.last_trigger_time = current_time

        # 构建基础日志
        log_msg = f"TRIGGER #{self.trigger_count:04d} | {operation:20s} | " \
                  f"exec={exec_time_ms:6.1f}ms | interval_dev={interval_deviation_ms:+7.1f}ms"

        # 判断是否慢操作（超过阈值或间隔偏差大）
        is_slow = exec_time_ms > self.threshold_ms or abs(interval_deviation_ms) > self.threshold_ms

        if is_slow:
            log_msg += " | [SLOW]"
            self.logger.warning(log_msg)
            # 记录详细上下文
            self._log_detailed_context(operation, exec_time_ms, interval_deviation_ms, extra_info)
        else:
            self.logger.info(log_msg)

    def _log_detailed_context(self, operation: str, exec_time_ms: float,
                              interval_deviation_ms: float, extra_info: Dict = None):
        """记录详细上下文信息"""
        self.logger.info("-" * 80)

        # 1. 线程状态
        self._log_thread_status()

        # 2. GC信息
        self._log_gc_info()

        # 3. 额外信息
        if extra_info:
            self.logger.info("EXTRA INFO:")
            for key, value in extra_info.items():
                self.logger.info(f"  {key}: {value}")

        self.logger.info("-" * 80)

    def _log_thread_status(self):
        """记录线程状态"""
        threads = threading.enumerate()
        self.logger.info(f"THREADS: {len(threads)} total")
        for thread in threads:
            thread_info = f"  - {thread.name:20s}"
            if hasattr(thread, '_target') and thread._target:
                thread_info += f" | target={thread._target.__name__}"
            self.logger.info(thread_info)

    def _log_gc_info(self):
        """记录GC信息"""
        gc_counts = gc.get_count()
        self.logger.info(f"GC INFO:")
        self.logger.info(f"  collections: {gc_counts}")
        self.logger.info(f"  thresholds: {gc.get_threshold()}")

        # 统计GC次数
        total_collections = sum(gc_counts)
        if total_collections > self.gc_stats['collections']:
            new_collections = total_collections - self.gc_stats['collections']
            self.gc_stats['collections'] = total_collections
            self.logger.info(f"  [注意] 发生了 {new_collections} 次GC")

    def log_error(self, error_msg: str, exception: Exception = None):
        """记录错误"""
        self.logger.error(f"ERROR: {error_msg}")
        if exception:
            self.logger.error(f"EXCEPTION: {type(exception).__name__}: {exception}")


# 全局实例
_performance_logger: Optional[PerformanceLogger] = None


def get_performance_logger() -> PerformanceLogger:
    """获取性能日志记录器实例"""
    global _performance_logger
    if _performance_logger is None:
        # 首次调用时强制初始化，确保文件处理器正确创建
        _performance_logger = PerformanceLogger(force_init=True)
    return _performance_logger


def init_performance_logger(log_dir: str = None, threshold_ms: int = 50, force_init: bool = False):
    """初始化性能日志记录器
    
    Args:
        log_dir: 日志目录路径
        threshold_ms: 慢操作阈值（毫秒）
        force_init: 强制重新初始化（用于代码更新后）
    """
    global _performance_logger
    _performance_logger = PerformanceLogger(log_dir, threshold_ms, force_init)
    return _performance_logger
