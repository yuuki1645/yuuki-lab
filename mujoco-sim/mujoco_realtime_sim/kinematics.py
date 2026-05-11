# 互換維持のため `mujoco_realtime_sim.kinematics` は残し、
# 実体は共通モジュール `mujoco_sim_common.kinematics` に移す。
from __future__ import annotations

from mujoco_sim_common.kinematics import *  # noqa: F403

