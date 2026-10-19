"""床との接触を、左右の足の四隅 kg にする。

実機の DF9-40 と同じく、各隅は 2 kg で頭打ち、0.02 kg 未満は 0。
方策はこの kg だけを見て、シミュの接触点そのものは見ない。
定数は `robot_description/sole_pressure.py` と揃える。
"""

from __future__ import annotations

import torch

import isaaclab.utils.math as math_utils
from isaaclab.assets import Articulation
from isaaclab.envs import ManagerBasedRLEnv
from isaaclab.managers import SceneEntityCfg

from .sole_corners import corner_newtons

# sole_pressure.py と同じ。センサの満量と応答点。
GRAVITY_MPS2 = 9.81
DF9_MAX_KG = 2.0
DEADZONE_KG = 0.02
# 足板 0.300 m × 0.170 m の半寸。
PLATE_HALF_X_M = 0.150
PLATE_HALF_Y_M = 0.085


def foot_corner_kg(
    env: ManagerBasedRLEnv,
    sensor_cfg: SceneEntityCfg,
    sole_cfg: SceneEntityCfg,
) -> torch.Tensor:
    """左右4隅の kg。形は (環境数, 8)。

    列は左のつま先左・つま先右・かかと左・かかと右、そのあと右足の同じ順。
    接触が無い環境は 0。圧力中心は足裏リンクの座標で表す。
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    robot: Articulation = env.scene[sole_cfg.name]
    if sensor.data.force_matrix_w is None or sensor.data.contact_pos_w is None:
        raise RuntimeError("足の接触センサに、床で絞った力と接触位置がありません")

    foot_ids = sensor_cfg.body_ids
    sole_ids = sole_cfg.body_ids
    # (環境, 足, フィルタ, 3)。フィルタは床の剛体。
    force_w = sensor.data.force_matrix_w.torch[:, foot_ids, :, :]
    point_w = sensor.data.contact_pos_w.torch[:, foot_ids, :, :]
    sole_pos = robot.data.body_link_pos_w.torch[:, sole_ids, :]
    sole_quat = robot.data.body_link_quat_w.torch[:, sole_ids, :]

    total, x_cop, y_cop = _sole_load(force_w, point_w, sole_pos, sole_quat)
    left = corner_newtons(total[:, 0], x_cop[:, 0], y_cop[:, 0], PLATE_HALF_X_M, PLATE_HALF_Y_M)
    right = corner_newtons(total[:, 1], x_cop[:, 1], y_cop[:, 1], PLATE_HALF_X_M, PLATE_HALF_Y_M)
    return torch.cat((_to_kg(left), _to_kg(right)), dim=-1)


def stance_load_kg(
    env: ManagerBasedRLEnv,
    sensor_cfg: SceneEntityCfg,
    sole_cfg: SceneEntityCfg,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """報酬用。左右の合計 kg と、足裏座標の圧力中心 x [m] を返す。"""
    corners = foot_corner_kg(env, sensor_cfg, sole_cfg)
    left = corners[:, 0:4]
    right = corners[:, 4:8]
    left_sum = left.sum(dim=-1)
    right_sum = right.sum(dim=-1)
    # 隅の位置で、kg から圧力中心を戻す。無荷重の足は 0。
    xs = corners.new_tensor([PLATE_HALF_X_M, PLATE_HALF_X_M, -PLATE_HALF_X_M, -PLATE_HALF_X_M])
    left_x = (left * xs).sum(dim=-1) / left_sum.clamp(min=1.0e-6)
    right_x = (right * xs).sum(dim=-1) / right_sum.clamp(min=1.0e-6)
    return left_sum, right_sum, left_x, right_x


def _sole_load(
    force_w: torch.Tensor,
    point_w: torch.Tensor,
    sole_pos: torch.Tensor,
    sole_quat: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """ワールドの接触を足裏座標へ移し、上向き成分の合計と圧力中心を返す。

    force_w / point_w の形は (環境, 足, フィルタ, 3)。
    戻り値はそれぞれ (環境, 足)。
    """
    count_env, count_foot, count_filter, _ = force_w.shape
    flat = count_env * count_foot
    quat = sole_quat.reshape(flat, 4).unsqueeze(1).expand(flat, count_filter, 4).reshape(-1, 4)
    origin = sole_pos.reshape(flat, 3).unsqueeze(1).expand(flat, count_filter, 3).reshape(-1, 3)
    force_local = math_utils.quat_apply_inverse(quat, force_w.reshape(-1, 3))
    point_local = math_utils.quat_apply_inverse(quat, point_w.reshape(-1, 3) - origin)
    # 足裏の +z が上。床が板を押す成分だけを圧縮とする。
    normal = force_local[:, 2].clamp(min=0.0).reshape(count_env, count_foot, count_filter)
    xy = point_local[:, 0:2].reshape(count_env, count_foot, count_filter, 2)
    total = normal.sum(dim=-1)
    weight = normal.unsqueeze(-1)
    cop = (xy * weight).sum(dim=2) / total.clamp(min=1.0e-6).unsqueeze(-1)
    return total, cop[..., 0], cop[..., 1]


def _to_kg(force_n: torch.Tensor) -> torch.Tensor:
    """ニュートンを kg 表示にし、応答点未満は 0、満量は 2 kg で止める。"""
    kg = force_n.clamp(min=0.0) / GRAVITY_MPS2
    kg = torch.where(kg < DEADZONE_KG, torch.zeros_like(kg), kg)
    return kg.clamp(max=DF9_MAX_KG)
