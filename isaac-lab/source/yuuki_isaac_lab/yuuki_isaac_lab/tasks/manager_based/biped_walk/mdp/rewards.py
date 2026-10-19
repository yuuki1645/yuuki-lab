"""最初の歩行報酬。重みは仮説で、学習の結果を見てから変える。

位相の sin が正のあいだ右足が接地、負のあいだ左足が接地、という時計に合わせる。
接地中の圧力中心は、かかと（x が負）からつま先（x が正）へ進むことを望む。
遊脚の膝は曲げる。カゴは立てたまま、指令の前進速度へ近づける。
"""

from __future__ import annotations

import torch

from isaaclab.assets import Articulation
from isaaclab.envs import ManagerBasedRLEnv
from isaaclab.managers import SceneEntityCfg

from .feet import PLATE_HALF_X_M, stance_load_kg
from .phase import phase_angle


def upright(env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """カゴの上方向。直立で 1、横倒しで 0 付近。"""
    robot: Articulation = env.scene[asset_cfg.name]
    # 体座標の重力の z は、直立で -1。
    return (-robot.data.projected_gravity_b.torch[:, 2]).clamp(0.0, 1.0)


def track_forward_speed(
    env: ManagerBasedRLEnv,
    command_name: str,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """体座標の前進速度が、指令の前進速度に近いほど 1。"""
    robot: Articulation = env.scene[asset_cfg.name]
    command = env.command_manager.get_command(command_name)[:, 0]
    speed = robot.data.root_lin_vel_b.torch[:, 0]
    return torch.exp(-torch.square(speed - command) / 0.25)


def penalize_slide_and_yaw(env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """横速度とヨー角速度の二乗和。最初の指令はどちらも 0。"""
    robot: Articulation = env.scene[asset_cfg.name]
    lateral = robot.data.root_lin_vel_b.torch[:, 1]
    yaw_rate = robot.data.root_ang_vel_b.torch[:, 2]
    return torch.square(lateral) + torch.square(yaw_rate)


def stance_contact(
    env: ManagerBasedRLEnv,
    sensor_cfg: SceneEntityCfg,
    sole_cfg: SceneEntityCfg,
) -> torch.Tensor:
    """接地すべき足に荷重があり、遊脚が床を押していないほど正。"""
    left_kg, right_kg, _, _ = stance_load_kg(env, sensor_cfg, sole_cfg)
    # tanh(2 kg) はほぼ 1。満量で頭打ちしたセンサでも、接地の有無は残る。
    left = torch.tanh(left_kg)
    right = torch.tanh(right_kg)
    right_stance = torch.sin(phase_angle(env)) >= 0.0
    stance = torch.where(right_stance, right - left, left - right)
    return stance


def heel_to_toe(
    env: ManagerBasedRLEnv,
    sensor_cfg: SceneEntityCfg,
    sole_cfg: SceneEntityCfg,
) -> torch.Tensor:
    """接地中の圧力中心が、かかとからつま先へ半周期で進むほど 1。"""
    left_kg, right_kg, left_x, right_x = stance_load_kg(env, sensor_cfg, sole_cfg)
    angle = phase_angle(env)
    # 右接地は 0〜π、左接地は π〜2π。半周期の進みを 0〜1 にする。
    right_stance = torch.sin(angle) >= 0.0
    progress = torch.where(right_stance, angle / torch.pi, (angle - torch.pi) / torch.pi)
    progress = progress.clamp(0.0, 1.0)
    target_x = -PLATE_HALF_X_M + 2.0 * PLATE_HALF_X_M * progress
    cop_x = torch.where(right_stance, right_x, left_x)
    loaded = torch.where(right_stance, right_kg, left_kg) > 0.3
    error = torch.square((cop_x - target_x) / PLATE_HALF_X_M)
    score = torch.exp(-error / 0.25)
    return torch.where(loaded, score, torch.zeros_like(score))


def swing_knee(
    env: ManagerBasedRLEnv,
    asset_cfg: SceneEntityCfg,
) -> torch.Tensor:
    """遊脚の膝を曲げる。目標は位相の山で 0.8 rad、接地中は 0。"""
    robot: Articulation = env.scene[asset_cfg.name]
    knee = robot.data.joint_pos.torch[:, asset_cfg.joint_ids]
    sine = torch.sin(phase_angle(env))
    # joint_ids は左膝、右膝の順。sin が正のとき右が接地なので、左膝を曲げる。
    target = torch.stack((0.8 * torch.relu(sine), 0.8 * torch.relu(-sine)), dim=-1)
    error = torch.square(knee - target).mean(dim=-1)
    return torch.exp(-error / 0.4)
