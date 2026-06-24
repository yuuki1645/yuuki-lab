# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""ステップ報酬（exp_030 sim/reward.py + conf/reward/baseline.yaml 由来・torch 版）。"""

from __future__ import annotations

import torch

from .episode_state import BipedStepContext


def compute_milestone_bonus(
    total_displacement: torch.Tensor,
    milestone_level: torch.Tensor,
    targets: tuple[float, ...],
    scales: tuple[float, ...],
) -> tuple[torch.Tensor, torch.Tensor]:
    """エピソード累積 +X 移動距離のマイルストーン到達ボーナス [num_envs]。

    同一マイルストーンは 1 回だけ付与するため milestone_level で到達済みを管理する。
    """
    bonus = torch.zeros_like(total_displacement)
    new_level = milestone_level.clone()
    for idx, (target_m, scale) in enumerate(zip(targets, scales, strict=True)):
        newly_reached = (total_displacement >= target_m) & (new_level <= idx)
        bonus = bonus + torch.where(newly_reached, torch.full_like(bonus, scale), torch.zeros_like(bonus))
        new_level = torch.where(newly_reached, torch.full_like(new_level, idx + 1), new_level)
    return bonus, new_level


def compute_effort_penalty(applied_torque: torch.Tensor, joint_vel: torch.Tensor, dt: float, scale: float) -> torch.Tensor:
    """|τ·q̇| 積分に比例するペナルティ [num_envs]。"""
    # 簡易版: 正規化なしのパワー近似（PhysX トルク飽和はアクチュエータ側で処理）
    power = torch.sum(torch.abs(applied_torque * joint_vel), dim=-1) * dt
    return power * scale


def compute_step_reward(
    *,
    cfg,
    max_dx_per_step: float,
    dx: torch.Tensor,
    root_vel_x: torch.Tensor,
    left_foot_dx: torch.Tensor,
    right_foot_dx: torch.Tensor,
    upright: torch.Tensor,
    lean_fwd_body: torch.Tensor,
    heading_align: torch.Tensor,
    tilt_horiz: torch.Tensor,
    imu_z: torch.Tensor,
    left_foot_z: torch.Tensor,
    right_foot_z: torch.Tensor,
    left_knee: torch.Tensor,
    right_knee: torch.Tensor,
    biped: BipedStepContext,
    progress_m: torch.Tensor,
    imu_dz: torch.Tensor,
    left_knee_vel: torch.Tensor,
    right_knee_vel: torch.Tensor,
    left_toe_z: torch.Tensor,
    left_heel_z: torch.Tensor,
    right_toe_z: torch.Tensor,
    right_heel_z: torch.Tensor,
    effort_penalty: torch.Tensor,
    imu_gyro: torch.Tensor | None = None,
    root_vel_y: torch.Tensor | None = None,
    episode_step: torch.Tensor | None = None,
    max_episode_steps: int | None = None,
    total_displacement: torch.Tensor | None = None,
    milestone_level: torch.Tensor | None = None,
    survival_milestone_level: torch.Tensor | None = None,
    current_action: torch.Tensor | None = None,
    prev_step_action: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """1 制御ステップの報酬を計算する。

    Returns:
        total: 合計報酬 [num_envs]
        forward: 前進報酬（forward_imu + forward_foot）[num_envs]
        effort_term: effort ペナルティ量（合計報酬では減算される）[num_envs]
        new_milestone_level: 更新後マイルストーン到達レベル [num_envs]
        new_survival_milestone_level: 更新後生存ステップマイルストーンレベル [num_envs]
    """
    max_dx = max_dx_per_step
    new_milestone_level = milestone_level if milestone_level is not None else torch.zeros_like(dx, dtype=torch.long)
    new_survival_milestone_level = (
        survival_milestone_level if survival_milestone_level is not None else torch.zeros_like(dx, dtype=torch.long)
    )

    forward_allowed = upright >= cfg.forward_min_upright
    if cfg.forward_require_foot_contact:
        forward_allowed = forward_allowed & biped.any_foot_on_floor
    if cfg.forward_require_single_support:
        forward_allowed = forward_allowed & biped.single_support
    # 両足支持の前転中は IMU +X 増加でも前進報酬を与えない
    if getattr(cfg, "forward_block_lean_both_feet", None) is not None:
        fall_block = biped.both_feet_on_floor & (lean_fwd_body > cfg.forward_block_lean_both_feet)
        forward_allowed = forward_allowed & (~fall_block)
    # 片脚側固定の degenerate gait では前進報酬を遮断
    block_streak = getattr(cfg, "forward_block_same_side_streak", 0)
    if block_streak > 0:
        forward_allowed = forward_allowed & (biped.same_side_streak <= block_streak)

    dx_clipped = torch.clamp(dx, -max_dx, max_dx)
    forward_imu = torch.zeros_like(dx)
    if cfg.enable_forward:
        forward_imu = torch.where(
            forward_allowed & (dx_clipped >= cfg.forward_min_dx),
            torch.clamp(dx_clipped, min=0.0) * cfg.forward_reward_scale,
            torch.zeros_like(dx),
        )

    forward_vel = torch.zeros_like(dx)
    if cfg.enable_forward_vel:
        vel_clipped = torch.clamp(root_vel_x, min=0.0, max=cfg.forward_vel_max)
        forward_vel = torch.where(forward_allowed, vel_clipped * cfg.forward_vel_reward_scale, torch.zeros_like(dx))

    stance_foot_dx = torch.zeros_like(dx)
    stance_foot_dx = torch.where(
        biped.single_support & (biped.single_support_side == 1),
        torch.clamp(left_foot_dx, min=0.0),
        stance_foot_dx,
    )
    stance_foot_dx = torch.where(
        biped.single_support & (biped.single_support_side == -1),
        torch.clamp(right_foot_dx, min=0.0),
        stance_foot_dx,
    )
    forward_foot = torch.zeros_like(dx)
    if cfg.enable_forward_foot:
        foot_dx_clipped = torch.clamp(stance_foot_dx, -max_dx, max_dx)
        forward_foot = torch.where(
            forward_allowed & (foot_dx_clipped >= cfg.forward_min_dx),
            foot_dx_clipped * cfg.forward_reward_scale,
            torch.zeros_like(dx),
        )

    # shaping は forward 条件 + 最小前進量を満たすときのみ付与（静止立位での報酬ハックを抑制）
    shaping_allowed = forward_allowed
    if cfg.shaping_require_forward_motion:
        shaping_allowed = shaping_allowed & (dx >= cfg.shaping_min_dx)

    # --- shaping（ENABLE フラグで段階的に有効化可能）---
    upright_bonus = torch.zeros_like(dx)
    if cfg.enable_upright_bonus:
        upright_bonus = torch.clamp(upright - cfg.upright_bonus_thresh, min=0.0) * cfg.upright_bonus_scale
        upright_bonus = torch.where(
            shaping_allowed & (dx >= cfg.upright_bonus_min_dx),
            upright_bonus,
            torch.zeros_like(dx),
        )

    push_off_bonus = torch.zeros_like(dx)
    landing_bonus = torch.zeros_like(dx)
    alternating_landing_bonus = torch.zeros_like(dx)
    right_landing_bonus = torch.zeros_like(dx)
    right_ss_bonus = torch.zeros_like(dx)
    foot_swap_bonus = torch.zeros_like(dx)
    duration_bonus = torch.zeros_like(dx)
    milestone_bonus = torch.zeros_like(dx)
    survival_milestone_bonus = torch.zeros_like(dx)
    swing_clearance_bonus = torch.zeros_like(dx)
    progress_bonus = torch.zeros_like(dx)

    if cfg.enable_walk_shaping:
        # push-off
        foot_dx_ss = torch.where(
            biped.single_support_side == 1, left_foot_dx, torch.where(biped.single_support_side == -1, right_foot_dx, dx)
        )
        knee_vel_ss = torch.where(
            biped.single_support_side == 1,
            left_knee_vel,
            torch.where(biped.single_support_side == -1, right_knee_vel, dx),
        )
        push_ok = shaping_allowed & biped.single_support & (foot_dx_ss >= cfg.push_off_min_foot_dx)
        push_ok = push_ok & ((knee_vel_ss < -cfg.push_off_min_knee_ext_vel) | (imu_dz >= cfg.push_off_min_imu_dz))
        push_off_bonus = torch.where(push_ok, torch.full_like(dx, cfg.push_off_bonus_scale), torch.zeros_like(dx))

        # landing
        toe_z = torch.where(biped.left_landed, left_toe_z, torch.where(biped.right_landed, right_toe_z, dx))
        heel_z = torch.where(biped.left_landed, left_heel_z, torch.where(biped.right_landed, right_heel_z, dx))
        land_ok = shaping_allowed & (biped.left_landed | biped.right_landed)
        land_ok = land_ok & (toe_z <= cfg.landing_max_toe_z) & (heel_z <= cfg.landing_max_heel_z)
        land_ok = land_ok & (lean_fwd_body <= cfg.landing_max_forward_lean)
        landing_bonus = torch.where(land_ok, torch.full_like(dx, cfg.landing_bonus_scale), torch.zeros_like(dx))

        alternating_landing_bonus = torch.where(
            shaping_allowed & biped.alternating_landing,
            torch.full_like(dx, cfg.alternating_landing_bonus_scale),
            torch.zeros_like(dx),
        )

        # 右足着地ボーナス（交互歩行の右側フェーズを強化）
        if getattr(cfg, "right_landing_bonus_scale", 0.0) > 0.0:
            right_land_ok = shaping_allowed & biped.right_landed
            right_land_ok = right_land_ok & (right_toe_z <= cfg.landing_max_toe_z) & (right_heel_z <= cfg.landing_max_heel_z)
            right_landing_bonus = torch.where(
                right_land_ok,
                torch.full_like(dx, cfg.right_landing_bonus_scale),
                torch.zeros_like(dx),
            )

        # 右足片脚支持中の前進ボーナス（左ピボット偏重からの脱却）
        right_ss_bonus = torch.zeros_like(dx)
        if getattr(cfg, "right_single_support_bonus_scale", 0.0) > 0.0:
            rss_min_dx = getattr(cfg, "right_single_support_min_dx", cfg.forward_min_dx)
            rss_ok = shaping_allowed & biped.single_support & (biped.single_support_side == -1)
            rss_ok = rss_ok & (dx >= rss_min_dx)
            right_ss_bonus = torch.where(
                rss_ok,
                torch.full_like(dx, cfg.right_single_support_bonus_scale),
                torch.zeros_like(dx),
            )

        # 左↔右片脚支持の切り替え（交互歩行サイクル）
        if getattr(cfg, "foot_swap_bonus_scale", 0.0) > 0.0:
            swap_ok = shaping_allowed & biped.foot_swap
            foot_swap_bonus = torch.where(
                swap_ok,
                torch.full_like(dx, cfg.foot_swap_bonus_scale),
                torch.zeros_like(dx),
            )

        swing_z = torch.where(
            biped.single_support & (biped.single_support_side == 1) & (~biped.right_landed),
            right_foot_z,
            torch.where(
                biped.single_support & (biped.single_support_side == -1) & (~biped.left_landed),
                left_foot_z,
                dx,
            ),
        )
        clearance = swing_z - cfg.swing_min_foot_z
        swing_clearance_bonus = torch.clamp(clearance, min=0.0) * cfg.swing_clearance_bonus_scale
        swing_clearance_bonus = torch.where(
            shaping_allowed & biped.single_support,
            swing_clearance_bonus,
            torch.zeros_like(dx),
        )

    if cfg.enable_progress:
        progress_bonus = torch.where(shaping_allowed, progress_m * cfg.progress_reward_scale, torch.zeros_like(dx))

    # 長時間立位＋前進の持続を促す（15 m 歩行には転倒せず長く生き残ることが前提）
    if getattr(cfg, "enable_duration_bonus", False) and episode_step is not None and max_episode_steps:
        dur_frac = episode_step.float() / float(max_episode_steps)
        dur_ok = (upright >= cfg.alive_min_upright) & (dx >= cfg.shaping_min_dx)
        duration_bonus = torch.where(
            dur_ok,
            dur_frac * cfg.duration_bonus_scale,
            torch.zeros_like(dx),
        )

    # 累積移動距離マイルストーン（2 / 5 / 10 / 15 m）
    if getattr(cfg, "enable_displacement_milestones", False) and total_displacement is not None:
        milestone_bonus, new_milestone_level = compute_milestone_bonus(
            total_displacement,
            new_milestone_level,
            cfg.displacement_milestone_targets,
            cfg.displacement_milestone_scales,
        )

    # 生存ステップ数マイルストーン（転倒せず長く立つことを直接報酬）
    if getattr(cfg, "enable_survival_milestones", False) and episode_step is not None:
        survival_milestone_bonus, new_survival_milestone_level = compute_milestone_bonus(
            episode_step.float(),
            new_survival_milestone_level,
            tuple(float(t) for t in cfg.survival_milestone_targets),
            cfg.survival_milestone_scales,
        )

    backward_lean_penalty = torch.zeros_like(dx)
    forward_lean_penalty = torch.zeros_like(dx)
    heading_misalign_penalty = torch.zeros_like(dx)
    lateral_tilt_penalty = torch.zeros_like(dx)
    height_penalty = torch.zeros_like(dx)
    knee_hyperflex_penalty = torch.zeros_like(dx)

    if cfg.enable_posture_penalties:
        backward_lean_penalty = torch.clamp(-lean_fwd_body - cfg.lean_backward_thresh, min=0.0) * cfg.lean_backward_penalty_scale
        # 両足支持中の前傾（足を出さない前転）を強く抑制
        ds_forward_lean_penalty = torch.zeros_like(dx)
        if getattr(cfg, "ds_forward_lean_penalty_scale", 0.0) > 0.0:
            ds_forward_lean_penalty = torch.where(
                biped.both_feet_on_floor,
                torch.clamp(lean_fwd_body - cfg.ds_forward_lean_thresh, min=0.0) * cfg.ds_forward_lean_penalty_scale,
                torch.zeros_like(dx),
            )
        forward_lean_penalty = torch.where(
            (~biped.any_foot_on_floor) & (biped.aerial_steps >= cfg.lean_forward_min_aerial_steps),
            torch.clamp(lean_fwd_body - cfg.lean_forward_thresh, min=0.0) * cfg.lean_forward_penalty_scale,
            torch.zeros_like(dx),
        )
        heading_misalign_penalty = (
            torch.clamp(cfg.heading_align_min - heading_align, min=0.0) * cfg.heading_misalign_penalty_scale
        )
        lateral_tilt_penalty = torch.clamp(tilt_horiz - cfg.lateral_tilt_thresh, min=0.0) * cfg.lateral_tilt_penalty_scale

        target_z = torch.full_like(imu_z, cfg.target_imu_z)
        target_z = torch.where(biped.single_support, torch.full_like(imu_z, cfg.target_imu_z_single_stance), target_z)
        target_z = torch.where(biped.both_feet_on_floor, torch.full_like(imu_z, cfg.target_imu_z_double_stance), target_z)
        height_penalty = torch.clamp(target_z - imu_z, min=0.0) * cfg.imu_height_penalty_scale
        height_penalty = torch.where(
            ~biped.any_foot_on_floor,
            torch.where(
                imu_z < cfg.height_penalty_aerial_crash_z,
                torch.clamp(cfg.target_imu_z - imu_z, min=0.0) * cfg.imu_height_penalty_scale * 1.5,
                torch.clamp(cfg.target_imu_z - imu_z, min=0.0) * cfg.imu_height_penalty_scale,
            ),
            height_penalty,
        )

        knee = torch.maximum(left_knee, right_knee)
        knee_excess = torch.clamp(knee - cfg.knee_hyperflex_max_rad, min=0.0)
        knee_hyperflex_penalty = knee_excess * cfg.knee_hyperflex_penalty_scale
        if cfg.knee_hyperflex_aerial_only:
            knee_hyperflex_penalty = torch.where(biped.any_foot_on_floor, torch.zeros_like(dx), knee_hyperflex_penalty)

    double_support_penalty = torch.zeros_like(dx)
    if cfg.enable_double_support:
        forward_motion = torch.maximum(
            torch.clamp(dx, min=0.0),
            torch.maximum(torch.clamp(left_foot_dx, min=0.0), torch.clamp(right_foot_dx, min=0.0)),
        )
        double_support_penalty = torch.where(
            biped.both_feet_on_floor,
            cfg.double_support_penalty_scale * 0.5
            + torch.where(
                forward_motion < cfg.double_support_min_forward,
                torch.zeros_like(dx),
                forward_motion * cfg.double_support_penalty_scale,
            ),
            torch.zeros_like(dx),
        )

    # 前転ハック: 両足支持 + 前傾 + 前方向移動
    # 同じ片脚側が長く続く degenerate gait（左足ピボット等）
    same_side_streak_penalty = torch.zeros_like(dx)
    streak_after = getattr(cfg, "same_side_streak_penalty_after", 0)
    streak_scale = getattr(cfg, "same_side_streak_penalty_scale", 0.0)
    if streak_after > 0 and streak_scale > 0.0:
        over_streak = biped.same_side_streak.float() - float(streak_after)
        same_side_streak_penalty = torch.where(
            over_streak > 0.0,
            over_streak * streak_scale,
            torch.zeros_like(dx),
        )

    # 左右接地の偏り: 左片脚ピボットが続く degenerate gait を段階ペナルティ
    contact_imbalance_penalty = torch.zeros_like(dx)
    imb_scale = getattr(cfg, "contact_imbalance_penalty_scale", 0.0)
    imb_after = getattr(cfg, "contact_imbalance_streak_after", 0)
    if imb_scale > 0.0 and imb_after > 0:
        left_pivot = biped.single_support & (biped.single_support_side == 1)
        streak_over = biped.same_side_streak.float() - float(imb_after)
        contact_imbalance_penalty = torch.where(
            left_pivot & (streak_over > 0.0),
            streak_over * imb_scale,
            torch.zeros_like(dx),
        )

    # 直立姿勢での後退ペナルティ（前進学習の方向性を固定）
    backward_dx_penalty = torch.zeros_like(dx)
    bwd_scale = getattr(cfg, "backward_dx_penalty_scale", 0.0)
    bwd_thresh = getattr(cfg, "backward_dx_thresh", 0.0)
    if bwd_scale > 0.0:
        backward_dx_penalty = torch.where(
            (upright >= cfg.forward_min_upright) & (dx < -bwd_thresh),
            (-dx) * bwd_scale,
            torch.zeros_like(dx),
        )

    # 横方向ドリフト・姿勢角速度（転倒前のふらつき抑制）
    lateral_vel_penalty = torch.zeros_like(dx)
    if getattr(cfg, "lateral_vel_penalty_scale", 0.0) > 0.0 and root_vel_y is not None:
        lateral_vel_penalty = torch.abs(root_vel_y) * cfg.lateral_vel_penalty_scale
    ang_vel_penalty = torch.zeros_like(dx)
    if getattr(cfg, "ang_vel_penalty_scale", 0.0) > 0.0 and imu_gyro is not None:
        ang_vel_penalty = torch.norm(imu_gyro, dim=-1) * cfg.ang_vel_penalty_scale
        ang_vel_penalty = torch.where(upright >= cfg.alive_min_upright, ang_vel_penalty, torch.zeros_like(dx))

    # 行動の急激な変化を抑える（関節目標のジャーク低減 → 転倒抑制）
    action_rate_penalty = torch.zeros_like(dx)
    rate_scale = getattr(cfg, "action_rate_penalty_scale", 0.0)
    if rate_scale > 0.0 and current_action is not None and prev_step_action is not None:
        action_rate_penalty = torch.sum(torch.abs(current_action - prev_step_action), dim=-1) * rate_scale

    fall_forward_penalty = torch.zeros_like(dx)
    if getattr(cfg, "fall_forward_penalty_scale", 0.0) > 0.0:
        fall_hack = biped.both_feet_on_floor & (lean_fwd_body > cfg.fall_forward_lean_thresh)
        fall_forward_penalty = torch.where(
            fall_hack,
            torch.clamp(lean_fwd_body - cfg.fall_forward_lean_thresh, min=0.0) * cfg.fall_forward_penalty_scale
            + torch.clamp(dx, min=0.0) * cfg.fall_forward_penalty_scale,
            torch.zeros_like(dx),
        )

    flight_duration_penalty = torch.zeros_like(dx)
    if cfg.enable_flight_duration:
        over = biped.aerial_steps.float() - float(cfg.aerial_duration_penalty_after_steps)
        flight_duration_penalty = torch.where(
            (~biped.any_foot_on_floor) & (over > 0.0),
            over * cfg.aerial_duration_penalty_scale,
            torch.zeros_like(dx),
        )

    alive_bonus = torch.zeros_like(dx)
    if getattr(cfg, "enable_alive_bonus", False):
        alive_ok = (upright >= cfg.alive_min_upright) & (imu_z >= cfg.alive_min_imu_z)
        alive_scale = torch.full_like(dx, cfg.alive_bonus_scale)
        # エピソード後半ほど生存報酬を増幅（長距離歩行の持続を促す）
        if episode_step is not None and max_episode_steps:
            alive_scale = alive_scale * (1.0 + episode_step.float() / float(max_episode_steps))
        alive_bonus = torch.where(alive_ok, alive_scale, torch.zeros_like(dx))

    shaping = (
        upright_bonus
        + push_off_bonus
        + landing_bonus
        + alternating_landing_bonus
        + right_landing_bonus
        + right_ss_bonus
        + foot_swap_bonus
        + duration_bonus
        + milestone_bonus
        + survival_milestone_bonus
        + swing_clearance_bonus
        + progress_bonus
        + alive_bonus
        - backward_lean_penalty
        - forward_lean_penalty
        - ds_forward_lean_penalty
        - fall_forward_penalty
        - same_side_streak_penalty
        - contact_imbalance_penalty
        - backward_dx_penalty
        - lateral_vel_penalty
        - ang_vel_penalty
        - action_rate_penalty
        - height_penalty
        - flight_duration_penalty
        - knee_hyperflex_penalty
        - heading_misalign_penalty
        - lateral_tilt_penalty
        - double_support_penalty
    )

    forward = forward_imu + forward_foot + forward_vel
    effort_term = effort_penalty if cfg.enable_effort else torch.zeros_like(dx)
    total = forward + shaping - effort_term
    return total, forward, effort_term, new_milestone_level, new_survival_milestone_level
