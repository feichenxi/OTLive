import os
import logging
from typing import Optional, Dict
from configparser import ConfigParser

logger = logging.getLogger('aiwav')


class VoiceCloningService:
    """语音复刻服务 - 负责创建克隆音色"""

    def __init__(self, config: Dict):
        """
        初始化语音复刻服务

        Args:
            config: 配置字典，包含以下键：
                - enabled: 是否启用
                - api_key: DashScope API密钥
                - model: 目标模型
                - websocket_endpoint: WebSocket API地址
                - http_endpoint: HTTP API地址
                - timeout: 请求超时时间（秒）
        """
        self.enabled = config.get('enabled', False)
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', '')
        self.websocket_endpoint = config.get('websocket_endpoint', '')
        self.http_endpoint = config.get('http_endpoint', '')
        self.timeout = config.get('timeout', 60)

        self.logger = logger

        if self.enabled and self.api_key:
            self._init_dashscope()

    @classmethod
    def from_config_parser(cls, config: ConfigParser) -> Optional['VoiceCloningService']:
        """
        从ConfigParser对象创建服务实例

        Args:
            config: ConfigParser对象

        Returns:
            VoiceCloningService 实例，如果配置无效则返回 None
        """
        try:
            if not config.has_section('aiwav'):
                logger.warning("配置文件缺少 [aiwav] 节点")
                return None

            aiwav_config = {
                'enabled': True,
                'api_key': config.get('aiwav', 'api_key', fallback=''),
                'model': config.get('aiwav', 'model', fallback=''),
                'websocket_endpoint': config.get('aiwav', 'websocket_endpoint', fallback=''),
                'http_endpoint': config.get('aiwav', 'http_endpoint', fallback=''),
                'timeout': config.getint('aiwav', 'timeout', fallback=60)
            }

            service = cls(aiwav_config)
            return service
        except Exception as e:
            logger.error(f"从配置初始化语音复刻服务失败: {e}")
            return None

    @classmethod
    def from_config_file(cls, config_path: str) -> Optional['VoiceCloningService']:
        """
        从配置文件创建服务实例

        Args:
            config_path: 配置文件路径

        Returns:
            VoiceCloningService 实例，如果配置无效则返回 None
        """
        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}")
            return None

        try:
            config = ConfigParser()
            config.read(config_path, encoding='utf-8')
            return cls.from_config_parser(config)
        except Exception as e:
            logger.error(f"从配置文件初始化语音复刻服务失败: {e}")
            return None

    def _init_dashscope(self):
        """初始化 DashScope SDK"""
        try:
            import dashscope
            if self.api_key:
                dashscope.api_key = self.api_key
            if self.websocket_endpoint:
                dashscope.base_websocket_api_url = self.websocket_endpoint
            if self.http_endpoint:
                dashscope.base_http_api_url = self.http_endpoint
        except ImportError:
            self.logger.error("DashScope SDK 未安装，请运行: pip install dashscope")
        except Exception as e:
            self.logger.error(f"DashScope SDK 初始化失败: {e}")

    def create_voice(self, prefix: str, audio_url: str) -> Optional[str]:
        """
        创建克隆音色

        Args:
            prefix: 音色前缀（如 room123）
            audio_url: 音频样本URL

        Returns:
            voice_id: 克隆成功返回音色ID，失败返回None
        """
        if not self.enabled:
            self.logger.warning("语音复刻功能未启用")
            return None

        if not self.api_key:
            self.logger.error("DashScope API Key 未配置")
            return None

        if not prefix or not audio_url:
            self.logger.error("缺少必要参数: prefix 或 audio_url")
            return None

        try:
            import sys
            import io
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            try:
                from dashscope.audio.tts_v2 import VoiceEnrollmentService

                self.logger.info(f"开始语音复刻: prefix={prefix}, model={self.model}")

                service = VoiceEnrollmentService()
                voice_id = service.create_voice(
                    target_model=self.model,
                    prefix=prefix,
                    url=audio_url
                )

                if voice_id:
                    self.logger.info(f"语音复刻成功: voice_id={voice_id}")
                    return voice_id
                else:
                    self.logger.error("语音复刻失败: 返回空ID")
                    return None
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

        except ImportError:
            self.logger.error("DashScope SDK 未安装，请运行: pip install dashscope")
            return None
        except Exception as e:
            self.logger.error(f"语音复刻失败: {e}")
            return None

    def is_enabled(self) -> bool:
        """检查服务是否可用"""
        return self.enabled and bool(self.api_key)
