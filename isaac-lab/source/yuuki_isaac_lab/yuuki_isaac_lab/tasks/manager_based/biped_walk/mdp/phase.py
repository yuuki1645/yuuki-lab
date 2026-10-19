"""歩幅の時計。1周期が左右1歩ずつの1ストライド。

位相は角度 [rad]。観測には sin と cos を出し、360度で値が飛ばないようにする。
倒し切りの速度は 0.2 m/s。周期 2 秒なら、片足が前に出る時間は 1 秒、
1周期の進みは約 0.2 m。10 秒だと約 2 m。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv

# 普通の歩きで、一歩に約 1 秒。左右で 1 周期なので 2 秒。
PERIOD_S = 2.0
# スティックを倒し切った速さ。0.1 m/s では進みが遅すぎたので 2 倍。ヨーは 0。
FORWARD_SPEED_MPS = 0.2


def phase_angle(env: ManagerBasedRLEnv) -> torch.Tensor:
    """エピソード開始からの位相 [rad]。形は (環境数,)。リセットで 0 に戻る。"""
    elapsed = env.episode_length_buf.to(dtype=torch.float32) * env.step_dt
    return (2.0 * math.pi * elapsed / PERIOD_S) % (2.0 * math.pi)


def phase_sincos(env: ManagerBasedRLEnv) -> torch.Tensor:
    """方策へ渡す位相。形は (環境数, 2) で、列は sin, cos。"""
    angle = phase_angle(env)
    return torch.stack((torch.sin(angle), torch.cos(angle)), dim=-1)
