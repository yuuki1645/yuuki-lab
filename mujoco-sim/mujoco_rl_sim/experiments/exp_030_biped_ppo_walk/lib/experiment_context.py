"""実験共通コンテキスト。"""

from __future__ import annotations

from dataclasses import dataclass

from conf.schema import AppConfig
from package_meta import CHECKPOINT_ROOT, EXP_NAME


@dataclass(frozen=True)
class ExperimentContext:
  """run 中で共有する不変コンテキスト。"""

  cfg: AppConfig
  exp_name: str
  xml_path: str
  checkpoint_root: str
  telemetry_schema: str


def build_experiment_context(cfg: AppConfig) -> ExperimentContext:
  """Hydra 設定から実験コンテキストを構築する。"""
  # contract.session との循環 import を避けるため遅延 import
  from contract import TELEMETRY_CONTRACT

  return ExperimentContext(
    cfg=cfg,
    exp_name=EXP_NAME,
    xml_path=str(cfg.xml_path),
    checkpoint_root=str(CHECKPOINT_ROOT),
    telemetry_schema=str(TELEMETRY_CONTRACT.schema_id),
  )
