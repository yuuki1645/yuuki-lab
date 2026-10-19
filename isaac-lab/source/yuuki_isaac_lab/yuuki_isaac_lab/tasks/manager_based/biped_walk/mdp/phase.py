"""歩幅の時計。1周期が左右1歩ずつの1ストライド。

位相は角度 [rad]。観測には sin と cos を出し、360度で値が飛ばないようにする。
最初の周期は 1 秒。前進指令 0.3 m/s なら、1周期の歩幅は約 0.3 m。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv

# 成人のストライドは 1.0〜1.2 秒。この脚は短いので、最初は 1 秒。
PERIOD_S = 1.0
# 最初の学習は一定速度。ヨーは 0。速度を変えるときは周期も一緒に見直す。
FORWARD_SPEED_MPS = 0.3


def phase_angle(env: ManagerBasedRLEnv) -> torch.Tensor:
    """エピソード開始からの位相 [rad]。形は (環境数,)。リセットで 0 に戻る。"""
    elapsed = env.episode_length_buf.to(dtype=torch.float32) * env.step_dt
    return (2.0 * math.pi * elapsed / PERIOD_S) % (2.0 * math.pi)


def phase_sincos(env: ManagerBasedRLEnv) -> torch.Tensor:
    """方策へ渡す位相。形は (環境数, 2) で、列は sin, cos。"""
    angle = phase_angle(env)
    return torch.stack((torch.sin(angle), torch.cos(angle)), dim=-1)
