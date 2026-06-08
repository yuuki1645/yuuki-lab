"""Hydra ConfigStore 登録。"""

from __future__ import annotations

from hydra.core.config_store import ConfigStore

from conf.schema.app_config import AppConfig


def register_config_store() -> None:
  """AppConfig を ConfigStore に登録する。"""
  cs = ConfigStore.instance()
  cs.store(name="app_config", node=AppConfig)
