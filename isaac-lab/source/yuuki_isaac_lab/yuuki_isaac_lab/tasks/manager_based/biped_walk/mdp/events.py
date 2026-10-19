"""起動時に一度だけ、板より下にはみ出す足首サーボの衝突を切る。

変換後の衝突プリムは `left_foot_servo_0_1` のように、見た目の箱と別名になる。
切らないと、アルミ板が床に着く前にサーボの箱が体重を受ける。
"""

from __future__ import annotations

import torch

from isaaclab.envs import ManagerBasedEnv
from pxr import UsdPhysics

# 見た目の箱の名前。物理の箱は末尾に _1 が付くか、displayName がこの名前。
_FOOT_SERVO_NAMES = ("left_foot_servo_0", "right_foot_servo_0")


def disable_foot_servo_collisions(env: ManagerBasedEnv, env_ids: torch.Tensor | None) -> None:
    """全環境の足首サーボ衝突を無効にする。env_ids は起動時の全環境。"""
    del env_ids
    stage = env.sim.stage
    found = 0
    for prim in stage.Traverse():
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        name = prim.GetName()
        display = str(prim.GetDisplayName() or "")
        matched = False
        for target in _FOOT_SERVO_NAMES:
            if name == target or name.startswith(target + "_") or display == target:
                matched = True
                break
        if not matched:
            continue
        collision = UsdPhysics.CollisionAPI(prim)
        enabled = collision.GetCollisionEnabledAttr()
        if enabled:
            enabled.Set(False)
        else:
            collision.CreateCollisionEnabledAttr(False)
        found += 1
    print(f"[biped_walk] 足首サーボの衝突を {found} 個切りました")
