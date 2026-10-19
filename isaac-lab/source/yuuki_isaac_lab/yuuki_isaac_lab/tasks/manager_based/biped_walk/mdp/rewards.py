"""最初の歩行報酬。重みは仮説で、学習の結果を見てから変える。

位相の sin が正のあいだ右足が接地、負のあいだ左足が接地、という時計に合わせる。
接地中の圧力中心は、かかと（x が負）からつま先（x が正）へ進むことを望む。
遊脚の膝は曲げる。カゴは立てたまま、胸の向きに進んだ正味の距離を増やす。
左右の足は、板の内側が約 4 cm 空く間隔で並ぶ。重なった深さは減点になる。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import torch

from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.math import quat_apply, quat_apply_inverse

if TYPE_CHECKING:
    from isaaclab.assets import Articulation
    from isaaclab.envs import ManagerBasedRLEnv

from yuuki_isaac_lab.assets.robots.yuuki_legs.model_size import (
    HIP_SEPARATION_M,
    LEG_LENGTH_HIP_TO_ANKLE_M,
    PLATE_WIDTH_Y_M,
)

from .feet import PLATE_HALF_X_M, stance_load_kg
from .phase import phase_angle

# 左右の股軸間隔、足裏の幅、股から足首までの長さは yaml から読む。
# 足裏までの高さを変えても、開脚角の脚長は股ロール軸から足首ロール軸までなので変わらない。
# 実機は、板が触れないところまで開いて安定してから歩き始める。学習の初期姿勢もそこにする。
INNER_CLEARANCE_M = 0.04
# 中心間隔。板幅に、実機で残している内側すき間を足す。
TARGET_FEET_GAP_M = PLATE_WIDTH_Y_M + INNER_CLEARANCE_M
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


def track_forward_progress(
    env: ManagerBasedRLEnv,
    command_name: str,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """胸が向いている水平方向へ進んだ距離。重み 1.5 なら、0.1 m/s を保つと毎秒 1.5 点。

    その瞬間の前方向き速度に点を出すと、前へ倒してすぐ戻る揺れでも点が残る。
    戻るあいだを 0 にすると、正味の移動が 0 でも平均点は高い。
    ここでは一歩ごとの移動を足す。同じ速さで戻すと、進んだ点と同じ大きさだけ減る。
    指令速度より速い前進は 1 で頭打ちにする。後退に下限は付けない。
    報酬マネージャが step_dt を掛けるので、返す値は「速度 / 指令速度」にする。
    """
    robot: Articulation = env.scene[asset_cfg.name]
    # 世界座標の水平位置。ビューのまま覚えると、次の差が常に 0 になる。
    pos_xy = robot.data.root_pos_w.torch[:, :2]
    # 体の +x を世界へ回し、床平面の成分だけを進行方向にする。真上を向いた瞬間は長さ 0 になり得る。
    body_forward = pos_xy.new_zeros(env.num_envs, 3)
    body_forward[:, 0] = 1.0
    forward_w = quat_apply(robot.data.root_quat_w.torch, body_forward)
    forward_xy = forward_w[:, :2]
    forward_norm = forward_xy.norm(dim=-1, keepdim=True).clamp(min=1.0e-6)
    forward_xy = forward_xy / forward_norm

    prev_xy = getattr(env, "_forward_progress_prev_xy", None)
    valid = getattr(env, "_forward_progress_valid", None)
    if prev_xy is None or valid is None:
        # 最初の1歩は比較する位置がまだ無い。出現位置そのものを距離にしない。
        prev_xy = pos_xy.detach().clone()
        valid = torch.zeros(env.num_envs, dtype=torch.bool, device=pos_xy.device)
        env._forward_progress_prev_xy = prev_xy
        env._forward_progress_valid = valid

    traveled_m = torch.where(
        valid,
        (pos_xy - prev_xy).mul(forward_xy).sum(dim=-1),
        torch.zeros(env.num_envs, device=pos_xy.device),
    )
    env._forward_progress_prev_xy = pos_xy.detach().clone()
    env._forward_progress_valid = torch.ones(env.num_envs, dtype=torch.bool, device=pos_xy.device)
    # 報酬のあとで出現位置へ戻る。戻した瞬間の大きな差は、次の一歩では距離に入れない。
    # 最初の reset 直後は reset_buf がまだ無い。そのときは出現位置を覚えただけなので、差は 0。
    reset_buf = getattr(env, "reset_buf", None)
    if reset_buf is not None:
        env._forward_progress_valid[reset_buf] = False

    command = env.command_manager.get_command(command_name)[:, 0]
    command_abs = command.clamp(min=1.0e-3)
    # step_dt で割って速度にし、指令速度で割って 0.1 m/s のとき 1 にする。
    rate = traveled_m / (env.step_dt * command_abs)
    return rate.clamp(max=1.0)


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
    """板の内側が約 4 cm 空くと 1。接すると 0。重なった深さに比例してマイナス。

    頂点は中心間隔 0.21 m。板幅 0.17 m で内側が接する。
    狭い側は、目標の 4 cm を 1、接触を 0、さらに 4 cm 重なると -1 にする。
    重みが 1 なら、板が深く重なったまま進むより、開いて立つ方が点になる。
    広い側は加点のまま下げる。目標より内側すき間がさらに 8 cm 広いところで約 0.5。
    """
    gap_m = feet_lateral_gap_m(env, asset_cfg)
    delta = gap_m - target_y_m
    # 内側 4 cm。この幅を 1 点の単位にする。
    inner_target_m = target_y_m - plate_width_m
    # 狭い側は重なりの深さそのもの。接触で 0、4 cm の重なりで -1。
    narrow = 1.0 + delta / inner_target_m
    # 広い側は、内側すき間が目標よりさらに 8 cm 広いところで約 0.5。マイナスにはしない。
    wide_span = 2.0 * inner_target_m
    wide_var = wide_span**2 / math.log(2.0)
    wide = torch.exp(-torch.square(delta) / wide_var)
    return torch.where(delta < 0.0, narrow, wide)


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
