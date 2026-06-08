"""Hydra 設定の保存・復元ユーティリティ。"""

from __future__ import annotations

from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from conf.schema import AppConfig, build_app_config

HYDRA_DIRNAME = ".hydra"
HYDRA_CONFIG_FILENAME = "config.yaml"


def hydra_config_path(run_dir: str | Path) -> Path:
  """run ディレクトリ内の解決済み Hydra 設定パス。"""
  return Path(run_dir) / HYDRA_DIRNAME / HYDRA_CONFIG_FILENAME


def save_hydra_config(run_dir: str | Path, cfg: DictConfig) -> Path:
  """run ディレクトリへ Hydra の最終設定 YAML を保存する（``.hydra/config.yaml``）。"""
  out_dir = Path(run_dir) / HYDRA_DIRNAME
  out_dir.mkdir(parents=True, exist_ok=True)
  out_path = out_dir / HYDRA_CONFIG_FILENAME
  OmegaConf.save(config=cfg, f=str(out_path))
  return out_path


def load_cfg_from_yaml(path: str | Path) -> AppConfig:
  """保存済み YAML から AppConfig を復元する。"""
  loaded = OmegaConf.load(str(path))
  return build_app_config(loaded)
