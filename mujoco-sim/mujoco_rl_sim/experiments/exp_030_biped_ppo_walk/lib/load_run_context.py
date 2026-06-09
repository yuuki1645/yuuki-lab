"""チェックポイントまたは Hydra YAML から ``ExperimentContext`` を復元する。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from conf.schema import AppConfig, build_app_config
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


def build_eval_app_config(base: AppConfig) -> AppConfig:
  """eval 用 ``AppConfig``（wandb 無効・学習 DR 無効）。

  Hydra を再初期化しない。``train.py`` の post-train eval や
  ``run_checkpoint_eval`` から ``base`` に ckpt run の学習設定を渡す。
  """
  app = replace(
    base,
    wandb=replace(base.wandb, enabled=False),
    training=replace(base.training, training_dr=False),
  )
  # ``build_app_config`` と同様に PPO gamma 計算用の参照を同期する。
  app.ppo._sim = app.sim
  return app


def build_eval_context(base: AppConfig) -> ExperimentContext:
  """``base`` を学習設定のまま引き継ぎ、eval 向け override だけ適用する。"""
  return build_experiment_context(build_eval_app_config(base))


def eval_ctx(base: AppConfig | None = None) -> ExperimentContext:
  """公式 eval 用コンテキスト。

  Args:
    base: 学習 run の ``AppConfig``（推奨）。省略時は ``conf`` 既定を compose する
      （``scripts/eval.py`` 等の **別プロセス** 向け。``@hydra.main`` 内では使わない）。
  """
  if base is not None:
    return build_eval_context(base)
  # 別プロセス専用: compose はここだけ（@hydra.main 内から呼ばないこと）
  return build_experiment_context(
    compose_app_config(["wandb=disabled", "training.training_dr=false"])
  )
