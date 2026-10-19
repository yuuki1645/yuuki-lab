"""方策が見る量と、批評家だけが見る量。

方策は、腰の CoreS3 が自分で作れる量だけにする。関節角、IMU（傾きと角速度）、
四隅の kg、位相の sin / cos、前進速度とヨー角速度、直前に出した関節目標。
批評家はこれに加えて、根元の速度・高さ・関節速度を見る。実機には無い。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

from isaaclab.managers import SceneEntityCfg

if TYPE_CHECKING:
    from isaaclab.assets import Articulation
    from isaaclab.envs import ManagerBasedRLEnv

from .feet import foot_corner_kg
from .phase import phase_sincos


def command_forward_and_yaw(env: ManagerBasedRLEnv, command_name: str) -> torch.Tensor:
    """速度指令の前進 [m/s] とヨー角速度 [rad/s]。横速度は方策へ出さない。"""
    command = env.command_manager.get_command(command_name)
    return torch.stack((command[:, 0], command[:, 2]), dim=-1)


def root_height(env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg) -> torch.Tensor:
    """カゴ底の高さ [m]。批評家だけ。平らな床の世界座標。"""
    robot: Articulation = env.scene[asset_cfg.name]
    return robot.data.root_pos_w.torch[:, 2:3]
