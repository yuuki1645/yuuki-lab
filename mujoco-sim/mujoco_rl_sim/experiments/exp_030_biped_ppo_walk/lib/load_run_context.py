"""チェックポイントまたは Hydra YAML から ``ExperimentContext`` を復元する。"""

from __future__ import annotations

from pathlib import Path

from conf.schema import build_app_config
from lib.experiment_context import ExperimentContext, build_experiment_context
from lib.hydra_checkpoint import hydra_config_path, load_cfg_from_yaml
from lib.hydra_compose import compose_app_config


def default_ctx() -> ExperimentContext:
  """``conf/config.yaml`` 既定の実験コンテキスト。"""
  return build_experiment_context(compose_app_config())


def ctx_from_hydra_yaml(path: str | Path) -> ExperimentContext:
  """``.hydra/config.yaml`` 等からコンテキストを構築する。"""
  return build_experiment_context(load_cfg_from_yaml(path))


def ctx_from_checkpoint(ckpt_path: str | Path) -> ExperimentContext:
  """ckpt の親 run ディレクトリに ``.hydra/config.yaml`` があればそれを読む。"""
  ckpt = Path(ckpt_path).resolve()
  hydra_yaml = hydra_config_path(ckpt.parent)
  if hydra_yaml.is_file():
    return ctx_from_hydra_yaml(hydra_yaml)
  return default_ctx()


def eval_ctx() -> ExperimentContext:
  """公式 eval 用（学習 DR 無効・wandb 無効の compose）。"""
  return build_experiment_context(
    compose_app_config(["wandb=disabled", "training.training_dr=false"])
  )
