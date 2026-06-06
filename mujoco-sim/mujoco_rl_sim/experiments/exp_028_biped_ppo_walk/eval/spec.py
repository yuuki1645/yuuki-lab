"""exp_028 評価仕様（evaluation setup）の定数。

v0: 10 seed × 5 ep = 50 試行（日常 ckpt 評価用）。学習コードには影響しない。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

# 評価仕様 ID（eval_report.json に記録）
EVAL_SPEC_ID = "biped_walk_eval_v0"

# 日常 ckpt 評価（将来は 10×10 等へ拡張）
EVAL_SEEDS: tuple[int, ...] = (101, 102, 103, 104, 105, 106, 107, 108, 109, 110)
EPISODES_PER_SEED = 5

# 初期姿勢ノイズ（stand keyframe 適用後）
ROOT_YAW_NOISE_DEG = 3.0
JOINT_NOISE_DEG = 2.0
ROOT_LIN_VEL_NOISE_M_S = 0.05
ROOT_ANG_VEL_NOISE_RAD_S = 0.1

# ルート X/Y 位置ノイズは平面タスクのため意図的に無し
APPLY_ROOT_XY_POSITION_NOISE = False

DEG2RAD = float(np.pi / 180.0)
ROOT_YAW_NOISE_RAD = ROOT_YAW_NOISE_DEG * DEG2RAD
JOINT_NOISE_RAD = JOINT_NOISE_DEG * DEG2RAD

# 主指標名（eval_report.json / 将来 W&B 用）
PRIMARY_METRIC_NAME = "eval/displacement_x_mean"


@dataclass(frozen=True)
class EvalTrialPlan:
  """1 試行（eval_seed × ep_index）。"""

  eval_seed: int
  ep_index: int
  trial_index: int


def iter_eval_trials(
  *,
  eval_seeds: Sequence[int] = EVAL_SEEDS,
  episodes_per_seed: int = EPISODES_PER_SEED,
) -> tuple[EvalTrialPlan, ...]:
  """評価試行の一覧（順序固定）。"""
  plans: list[EvalTrialPlan] = []
  trial_index = 0
  for eval_seed in eval_seeds:
    for ep_index in range(episodes_per_seed):
      plans.append(
        EvalTrialPlan(
          eval_seed=int(eval_seed),
          ep_index=int(ep_index),
          trial_index=trial_index,
        )
      )
      trial_index += 1
  return tuple(plans)


def make_episode_rng(eval_seed: int, ep_index: int) -> np.random.Generator:
  """試行ごとに再現可能な RNG（学習 seed とは独立）。"""
  return np.random.default_rng([int(eval_seed), int(ep_index)])
