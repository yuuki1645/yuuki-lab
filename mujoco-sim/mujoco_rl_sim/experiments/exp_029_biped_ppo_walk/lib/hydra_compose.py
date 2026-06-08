"""テスト・補助 CLI 向け Hydra compose ヘルパ。"""

from __future__ import annotations

from pathlib import Path

from hydra import compose, initialize_config_dir
from omegaconf import DictConfig, OmegaConf

from conf.schema import AppConfig, build_app_config
from conf.schema.register import register_config_store
from lib.dispatch_cfg_merge import merge_dispatch_overrides

_EXP_ROOT = Path(__file__).resolve().parent.parent
_CONF_DIR = str((_EXP_ROOT / "conf").resolve())


def compose_cfg(
  overrides: list[str] | None = None,
  *,
  apply_dispatch_env: bool = False,
) -> DictConfig:
  """``conf/config.yaml`` をベースに設定を合成する。"""
  register_config_store()
  with initialize_config_dir(config_dir=_CONF_DIR, version_base=None):
    cfg = compose(config_name="config", overrides=list(overrides or []))
  if apply_dispatch_env:
    cfg = merge_dispatch_overrides(cfg)
  return cfg


def compose_app_config(
  overrides: list[str] | None = None,
  *,
  apply_dispatch_env: bool = False,
) -> AppConfig:
  """合成結果を ``AppConfig`` として返す。"""
  return build_app_config(compose_cfg(overrides, apply_dispatch_env=apply_dispatch_env))


def cfg_to_dict(cfg: AppConfig) -> dict:
  """W&B 等へ渡す plain dict。"""
  return OmegaConf.to_container(OmegaConf.structured(cfg), resolve=True)  # type: ignore[arg-type]
