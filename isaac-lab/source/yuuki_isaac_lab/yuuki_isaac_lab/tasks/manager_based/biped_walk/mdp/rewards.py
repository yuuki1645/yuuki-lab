"""最初の歩行報酬。重みは仮説で、学習の結果を見てから変える。

位相の sin が正のあいだ右足が接地、負のあいだ左足が接地、という時計に合わせる。
接地中の圧力中心は、かかと（x が負）からつま先（x が正）へ進むことを望む。
遊脚の膝は曲げる。カゴは立てたまま、指令の前進速度へ近づける。
左右の足は、板の内側が約 4 cm 空く間隔で並ぶ。板が重なると、この項はほぼ 0 になる。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import torch

from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.math import quat_apply_inverse

if TYPE_CHECKING:
    from isaaclab.assets import Articulation
    from isaaclab.envs import ManagerBasedRLEnv

from .feet import PLATE_HALF_X_M, stance_load_kg
from .phase import phase_angle

# カゴ座標の左右。左股関節は y=+0.09 m、右股関節は y=-0.09 m（yuuki_biped.urdf）。
# 関節が 0 のとき、足リンクの左右差は 0.18 m。板の左右幅は 0.17 m なので、すき間は約 1 cm。
# 実機は、板が触れないところまで開いて安定してから歩き始める。学習の初期姿勢もそこにする。
HIP_SEPARATION_M = 0.18
PLATE_WIDTH_Y_M = 0.17
INNER_CLEARANCE_M = 0.04
# 中心間隔。板幅 0.17 m に内側すき間 0.04 m を足す。
TARGET_FEET_GAP_M = PLATE_WIDTH_Y_M + INNER_CLEARANCE_M
# 股ロール軸から足首ロール軸まで。股ピッチ、膝、足首ピッチ、足首ロールの z 間隔の和。
LEG_LENGTH_HIP_TO_ANKLE_M = 0.065 + 0.226 + 0.226 + 0.065
# 片足を (0.21-0.18)/2 m だけ外へ出す角度。正の股ロールは左右とも開く（右の軸は -X）。
# 足首ロールは逆符号にして、板を床と平行に戻す。
OPEN_STANCE_ROLL_RAD = math.asin(
    (TARGET_FEET_GAP_M - HIP_SEPARATION_M) / (2.0 * LEG_LENGTH_HIP_TO_ANKLE_M)
)


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


def feet_lateral_gap_m(env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg) -> torch.Tensor:
    """カゴから見た、左足の左右位置から右足の左右位置を引いた差（m）。

    asset_cfg.body_ids は左足、右足の順。開いて並んでいれば正、重なれば 0 付近、交差すれば負。
    世界座標の左右ではなくカゴの左右なので、体がヨーしても「自分の左に左足」のまま測れる。
    """
    robot: Articulation = env.scene[asset_cfg.name]
    # 足リンク原点。板の中心は足から前と下にずれているが、左右のずれは 0 なので、間隔は原点で足りる。
    foot_pos_w = robot.data.body_pos_w.torch[:, asset_cfg.body_ids, :]
    root_pos_w = robot.data.root_pos_w.torch
    root_quat_w = robot.data.root_quat_w.torch
    delta_w = foot_pos_w - root_pos_w[:, None, :]
    # root_quat_w は (x, y, z, w)。逆回転で、世界の差をカゴ座標へ移す。
    quat = root_quat_w[:, None, :].expand(-1, delta_w.shape[1], -1)
    foot_pos_b = quat_apply_inverse(quat, delta_w)
    left_y = foot_pos_b[:, 0, 1]
    right_y = foot_pos_b[:, 1, 1]
    return left_y - right_y


def feet_apart(
    env: ManagerBasedRLEnv,
    asset_cfg: SceneEntityCfg,
    target_y_m: float = TARGET_FEET_GAP_M,
    plate_width_m: float = PLATE_WIDTH_Y_M,
) -> torch.Tensor:
    """板の内側が約 4 cm 空くほど 1。板が接する間隔ではほぼ 0。大きく開きすぎると下がる。

    頂点は中心間隔 0.21 m。板幅 0.17 m（内側が接触）では exp(-4) で約 0.02。
    狭い側はこの 4 cm で急に落ちる。広い側は、さらに 8 cm 開いても約 0.5 が残る。
    股関節の真下（0.18 m、すき間約 1 cm）は約 0.1 なので、接した立ち方では点がほぼ入らない。
    """
    gap_m = feet_lateral_gap_m(env, asset_cfg)
    delta = gap_m - target_y_m
    # 接する位置までの差の二乗を 4 で割り、そこで約 0.02 にする。
    narrow_var = (target_y_m - plate_width_m) ** 2 / 4.0
    # 広い側は、内側すき間が目標よりさらに 8 cm 広いところで約 0.5。
    wide_span = 2.0 * (target_y_m - plate_width_m)
    wide_var = wide_span**2 / math.log(2.0)
    variance = torch.where(
        delta < 0.0,
        torch.full_like(delta, narrow_var),
        torch.full_like(delta, wide_var),
    )
    return torch.exp(-torch.square(delta) / variance)


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
