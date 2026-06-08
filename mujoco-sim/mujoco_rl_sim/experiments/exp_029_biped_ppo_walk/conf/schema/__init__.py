"""Hydra Structured Config 公開 API。"""

from conf.schema.app_config import AppConfig, build_app_config

__all__ = ["AppConfig", "build_app_config"]
