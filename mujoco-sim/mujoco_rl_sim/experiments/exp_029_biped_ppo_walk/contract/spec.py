"""契約のデータ構造（観測レイアウト・報酬ログキー・テレメトリ）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SliceKind = Literal["scalar", "vector"]


@dataclass(frozen=True)
class ObservationSlice:
  """観測ベクトル内の 1 ブロック（Hub テレメトリキーと対応）。"""

  telemetry_key: str
  start: int
  end: int
  kind: SliceKind
  description: str = ""


@dataclass(frozen=True)
class ObservationSpec:
  """ポリシー入力ベクトルのレイアウト定義。"""

  obs_dim: int
  slices: tuple[ObservationSlice, ...]

  def validate_layout(self) -> None:
    expected = 0
    for s in self.slices:
      if s.start != expected:
        raise ValueError(
          f"Observation layout gap: expected start {expected}, "
          f"got {s.start} for {s.telemetry_key}"
        )
      expected = s.end
    if expected != self.obs_dim:
      raise ValueError(
        f"Observation layout ends at {expected}, obs_dim={self.obs_dim}"
      )


@dataclass(frozen=True)
class RewardLogTerm:
  """step_info / Hub / wandb で共有する報酬項 ID。"""

  key: str
  label: str
  hub_scalar: bool = True


@dataclass(frozen=True)
class RewardLogSpec:
  terms: tuple[RewardLogTerm, ...]

  @property
  def keys(self) -> frozenset[str]:
    return frozenset(t.key for t in self.terms)


@dataclass(frozen=True)
class TelemetryContract:
  """Hub Socket.IO 向けスキーマ + 観測・報酬ログの契約。"""

  schema_id: str
  observation: ObservationSpec
  reward_log: RewardLogSpec
  include_legacy_gyro_alias: bool = True

  def validate(self) -> None:
    self.observation.validate_layout()
