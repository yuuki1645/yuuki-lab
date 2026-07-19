# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""BipedPpoWalk PPO task on ManagerBasedRLEnv."""

from __future__ import annotations

from collections.abc import Sequence

import torch

from isaaclab.envs import ManagerBasedRLEnv
from isaaclab.markers import VisualizationMarkers
from isaaclab.markers.config import FRAME_MARKER_CFG
from isaaclab.utils.math import quat_apply

from yuuki_isaac_lab.assets.robots.yuuki_biped.mjcf_utils import ensure_mjcf_importer_enabled

from .biped_ppo_walk_env_cfg import BipedPpoWalkEnvCfg
from .mdp.episode_state import BipedEpisodeState


class BipedPpoWalkEnv(ManagerBasedRLEnv):
    """12-DOF biped walk (+X alternating single support) on ManagerBasedRLEnv."""

    cfg: BipedPpoWalkEnvCfg

    def __init__(self, cfg: BipedPpoWalkEnvCfg, render_mode: str | None = None, **kwargs):
        # MJCF importer must be enabled before robot spawn (headless kit).
        ensure_mjcf_importer_enabled()
        super().__init__(cfg, render_mode, **kwargs)

        # Play 時など、設定で opacity < 1 のときロボット見た目を半透明にする。
        # IMU フレームマーカーがボディに隠れないようにするため（物理・観測は不変）。
        self._apply_robot_visual_opacity()

        # IMU サイトに追従する 3 軸フレームマーカー（X=赤 / Y=緑 / Z=青）。
        # USD のギズモと違い Fabric 上の物理更新にも追従できるように、
        # VisualizationMarkers を使って毎ステップ座標を書き込む方式にする。
        # GUI が無い（headless）場合は描画されないので生成自体をスキップする。
        self._imu_frame_marker: VisualizationMarkers | None = None
        if self.cfg.debug_vis_imu_frame and self.sim.has_gui():
            marker_cfg = FRAME_MARKER_CFG.copy()
            marker_cfg.prim_path = "/Visuals/IMUFrame"
            # FRAME_MARKER_CFG には frame と connecting_line の 2 プロトタイプが含まれるが、
            # 使うのは frame のみ。未使用プロトタイプが PointInstancer に残ると
            # omni.physx.fabric が "mismatched prototypes" 警告を出すため frame だけ残す。
            marker_cfg.markers = {"frame": marker_cfg.markers["frame"]}
            # ロボットが小型（IMU 高さ 0.2〜0.3 m 程度）なので軸長を縮める
            marker_cfg.markers["frame"].scale = (0.1, 0.1, 0.1)
            self._imu_frame_marker = VisualizationMarkers(marker_cfg)

    def _apply_robot_visual_opacity(self) -> None:
        """ロボット下の見た目メッシュ／Shader に ``robot_visual_opacity`` を適用する。

        MJCF 由来の PreviewSurface は ``inputs:opacity``、メッシュ側は
        ``displayOpacity`` を更新する。どちらも見た目専用で、PhysX の衝突には触らない。
        """
        opacity = float(self.cfg.robot_visual_opacity)
        if opacity >= 1.0 - 1e-6:
            return
        opacity = max(0.0, min(1.0, opacity))

        # pxr / isaaclab.sim は Kit 起動後にしか使えないため、ここで遅延 import する
        from pxr import Sdf, Usd, UsdGeom, UsdShade

        from isaaclab.sim.utils import find_matching_prim_paths, get_current_stage

        stage = get_current_stage()
        robot_paths = find_matching_prim_paths(self.scene["robot"].cfg.prim_path)
        for root_path in robot_paths:
            root = stage.GetPrimAtPath(root_path)
            if not root.IsValid():
                continue
            for prim in Usd.PrimRange(root):
                # Cube / Mesh など geom の表示不透明度（レガシー経路・補助）
                if prim.IsA(UsdGeom.Gprim):
                    UsdGeom.Gprim(prim).CreateDisplayOpacityAttr().Set([opacity])
                # UsdPreviewSurface 等の Shader opacity（RTX インタラクティブ描画で効く）
                if prim.IsA(UsdShade.Shader):
                    shader = UsdShade.Shader(prim)
                    opacity_input = shader.GetInput("opacity")
                    if opacity_input:
                        opacity_input.Set(opacity)
                    else:
                        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)

    def step(self, action: torch.Tensor):
        """1 制御ステップ実行後、IMU フレームマーカーの位置・姿勢を更新する。"""
        result = super().step(action)
        if self._imu_frame_marker is not None:
            self._update_imu_frame_marker()
        return result

    def _update_imu_frame_marker(self) -> None:
        """全 env の IMU サイトのワールド位置・姿勢をマーカーに反映する。

        IMU サイトはルートボディ（basket_thigh）にオフセット ``IMU_OFFSET`` で
        固定されているため、位置はルート位置 + 回転済みオフセット、
        姿勢はルートボディの姿勢そのものになる。
        """
        robot = self.scene["robot"]
        root_pos = robot.data.body_pos_w[:, self.biped_state.root_body_id]
        root_quat = robot.data.body_quat_w[:, self.biped_state.root_body_id]  # (w, x, y, z)
        imu_pos = root_pos + quat_apply(root_quat, self.biped_state.imu_off.unsqueeze(0).expand(self.num_envs, -1))
        self._imu_frame_marker.visualize(translations=imu_pos, orientations=root_quat)

    def load_managers(self) -> None:
        """Initialize biped episode state before observation manager probes policy terms."""
        self.biped_state = BipedEpisodeState(self)
        super().load_managers()

    @property
    def last_episode_displacement(self) -> torch.Tensor:
        return self.biped_state.last_episode_displacement

    @property
    def episode_start_imu_x(self) -> torch.Tensor:
        return self.biped_state.episode_start_imu_x

    @property
    def _last_physics(self) -> dict | None:
        return self.biped_state._last_physics

    @property
    def _last_biped_ctx(self):
        return self.biped_state._last_biped_ctx

    def _reset_idx(self, env_ids: Sequence[int]) -> None:
        """Reset manager subsystems and re-init biped episode buffers."""
        if not isinstance(env_ids, torch.Tensor):
            env_ids = torch.as_tensor(list(env_ids), device=self.device, dtype=torch.long)

        self.biped_state.record_episode_displacement(env_ids)
        # super()._reset_idx() が episode_length_buf をゼロ化するため、終了エピソード長を先に退避する
        episode_lengths = self.episode_length_buf[env_ids].float()
        super()._reset_idx(env_ids)
        self._log_watchlist(env_ids, episode_lengths)
        self.biped_state.init_env_buffers(env_ids)
        self.biped_state._last_update_step = -1
        self.biped_state.snapshot = None

    def _log_watchlist(self, env_ids: torch.Tensor, episode_lengths: torch.Tensor) -> None:
        """重要指標を WandB の専用セクション（0_Watchlist/）にも重複ログする。

        WandB はキーの ``/`` より前をセクション名として自動グルーピングし、
        セクションはアルファベット順に並ぶため、``0_`` 接頭辞で常に最上部に表示される。
        値は既存メトリクスの複製（スカラー）なのでログコストはほぼゼロ。

        注意: super()._reset_idx() は extras["log"] を新しい dict に差し替えるため、
        このメソッドは必ず super() の後に呼ぶこと。
        """
        if env_ids.numel() == 0:
            return
        log = self.extras.setdefault("log", {})

        # 前進距離（このタスクの主目的。右上がりが好ましい）
        log["0_Watchlist/episode_displacement_x"] = self.biped_state.last_episode_displacement[env_ids].mean()
        # エピソード長（長くなる = 転倒が減る。上限は episode_length_s / step_dt）
        log["0_Watchlist/episode_length_steps"] = episode_lengths.mean()

        # 終了理由の内訳（bad_pose は下がる・time_out は後半増えるのが好ましい）
        for key in ("Episode_Termination/bad_pose", "Episode_Termination/time_out"):
            if key in log:
                log["0_Watchlist/" + key.split("/")[-1]] = log[key]

        # エピソード報酬合計（報酬だけ伸びて displacement が停滞する場合は報酬ハックを疑う）
        reward_terms = [v for k, v in log.items() if k.startswith("Episode_Reward/")]
        if reward_terms:
            log["0_Watchlist/episode_reward_total"] = sum(reward_terms)
