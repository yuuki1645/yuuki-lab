"""学習時 Domain Randomization（A: 初期姿勢 / B: 足底摩擦 / C: kp・kv）。

- エピソードごとに ``EnvBipedPPO.reset(episode_index=...)`` から適用
- eval（``reset_eval``）には影響しない（適用前に名目値へ復元）
- RNG: ``training_seed`` + ``episode_index``（eval seed とは独立）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mujoco
import numpy as np

from lib.actuators import ACTUATOR_NAMES
from lib.experiment_context import ExperimentContext, build_experiment_context
from conf.schema import build_app_config

# eval RNG 系列と区別するための第三成分
_DR_RNG_TAG = 0x4452


@dataclass(frozen=True)
class _FootFrictionNominal:
  """足底 geom の slide friction 名目値。"""

  geom_name: str
  geom_id: int
  slide: float


@dataclass(frozen=True)
class _ActuatorNominal:
  """position アクチュエータの kp / kv 名目値（MuJoCo biasprm 形式）。"""

  actuator_name: str
  act_id: int
  kp: float
  bias_kp: float
  bias_kv: float


def make_episode_dr_rng(
  training_seed: int | None,
  episode_index: int,
) -> np.random.Generator:
  """エピソード DR 用 RNG（``training_seed`` 未設定時は非決定的）。"""
  if training_seed is not None:
    return np.random.default_rng(
      [int(training_seed), int(episode_index), _DR_RNG_TAG]
    )
  return np.random.default_rng()


_DEFAULT_CTX: ExperimentContext | None = None


def _resolve_ctx(ctx: ExperimentContext | None) -> ExperimentContext:
  global _DEFAULT_CTX
  if ctx is not None:
    return ctx
  if _DEFAULT_CTX is None:
    # 既存 API 互換: ctx 省略時は既定 AppConfig を使う。
    _DEFAULT_CTX = build_experiment_context(build_app_config())
  return _DEFAULT_CTX


def training_dr_spec_dict(ctx: ExperimentContext | None = None) -> dict[str, Any]:
  """config_effective / W&B 用の DR 仕様サマリ。"""
  resolved = _resolve_ctx(ctx)
  return {
    "enabled": bool(resolved.cfg.training.training_dr),
    "pose_scale": float(resolved.cfg.training.training_dr_pose_scale),
    "foot_friction_geom_names": list(resolved.cfg.training.training_dr_foot_friction_geoms),
    "friction_slide_mult_range": list(resolved.cfg.training.training_dr_friction_slide_mult_range),
    "actuator_kp_mult_range": list(resolved.cfg.training.training_dr_actuator_kp_mult_range),
    "actuator_kv_mult_range": list(resolved.cfg.training.training_dr_actuator_kv_mult_range),
  }


class TrainingDomainRandomization:
  """MuJoCo model の名目物理パラメータを保持し、エピソードごとにサンプルする。"""

  def __init__(self, model: mujoco.MjModel, ctx: ExperimentContext) -> None:
    self._ctx = ctx
    self._foot_friction: tuple[_FootFrictionNominal, ...] = tuple(
      self._snapshot_foot_friction(model, name)
      for name in self._ctx.cfg.training.training_dr_foot_friction_geoms
    )
    self._actuators: tuple[_ActuatorNominal, ...] = tuple(
      self._snapshot_actuator(model, name) for name in ACTUATOR_NAMES
    )

  @staticmethod
  def _snapshot_foot_friction(model: mujoco.MjModel, geom_name: str) -> _FootFrictionNominal:
    geom_id = int(model.geom(geom_name).id)
    slide = float(model.geom_friction[geom_id, 0])
    return _FootFrictionNominal(geom_name, geom_id, slide)

  @staticmethod
  def _snapshot_actuator(model: mujoco.MjModel, actuator_name: str) -> _ActuatorNominal:
    act_id = int(model.actuator(actuator_name).id)
    return _ActuatorNominal(
      actuator_name=actuator_name,
      act_id=act_id,
      kp=float(model.actuator_gainprm[act_id, 0]),
      bias_kp=float(model.actuator_biasprm[act_id, 1]),
      bias_kv=float(model.actuator_biasprm[act_id, 2]),
    )

  def restore_nominal(self, model: mujoco.MjModel) -> None:
    """XML 名目値へ戻す（eval / visualize 前にも呼ぶ）。"""
    for foot in self._foot_friction:
      model.geom_friction[foot.geom_id, 0] = foot.slide
    for act in self._actuators:
      model.actuator_gainprm[act.act_id, 0] = act.kp
      model.actuator_biasprm[act.act_id, 1] = act.bias_kp
      model.actuator_biasprm[act.act_id, 2] = act.bias_kv

  def apply_for_episode(
    self,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    rng: np.random.Generator,
  ) -> dict[str, Any]:
    """名目値復元 → 摩擦・kp/kv サンプル → 初期姿勢ノイズ（eval 同レンジ × scale）。"""
    self.restore_nominal(model)

    applied: dict[str, Any] = {}

    foot_mult: dict[str, float] = {}
    lo_f, hi_f = self._ctx.cfg.training.training_dr_friction_slide_mult_range
    for foot in self._foot_friction:
      mult = float(rng.uniform(lo_f, hi_f))
      model.geom_friction[foot.geom_id, 0] = foot.slide * mult
      foot_mult[foot.geom_name] = mult
    applied["foot_friction_slide_mult"] = foot_mult

    lo_kp, hi_kp = self._ctx.cfg.training.training_dr_actuator_kp_mult_range
    lo_kv, hi_kv = self._ctx.cfg.training.training_dr_actuator_kv_mult_range
    actuator_mult: list[dict[str, float | str]] = []
    for act in self._actuators:
      kp_mult = float(rng.uniform(lo_kp, hi_kp))
      kv_mult = float(rng.uniform(lo_kv, hi_kv))
      model.actuator_gainprm[act.act_id, 0] = act.kp * kp_mult
      model.actuator_biasprm[act.act_id, 1] = act.bias_kp * kp_mult
      model.actuator_biasprm[act.act_id, 2] = act.bias_kv * kv_mult
      actuator_mult.append(
        {
          "name": act.actuator_name,
          "kp_mult": kp_mult,
          "kv_mult": kv_mult,
        }
      )
    applied["actuator_mult"] = actuator_mult

    # eval パッケージとの循環 import を避けるため遅延 import
    from eval.noise import apply_initial_pose_noise

    applied["pose"] = apply_initial_pose_noise(
      model,
      data,
      rng,
      scale=float(self._ctx.cfg.training.training_dr_pose_scale),
    )
    return applied
