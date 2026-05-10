"""HTTP サーバーと同一の Simulation を表示するパッシブ Viewer（ステップはサーバー側のみ）。"""

from __future__ import annotations

import logging
import time

import mujoco.viewer

from mujoco_sim.core import Simulation

LOG = logging.getLogger("mujoco_sim.viewer")

# 表示だけ更新（mj_step は Flask 内）。60 FPS 程度。
_SYNC_HZ = 60.0


def run_passive_viewer_follow_sim(sim: Simulation) -> None:
    """メインスレッドで呼ぶ。`sim` は Flask が共有している Simulation と同一インスタンス。"""
    LOG.info("Opening passive viewer (same model/data as HTTP API). Close window to exit.")
    with mujoco.viewer.launch_passive(sim.model, sim.data) as viewer:
        period = 1.0 / _SYNC_HZ
        while viewer.is_running():
            t0 = time.perf_counter()
            sim.sync_viewer(viewer)
            elapsed = time.perf_counter() - t0
            slack = period - elapsed
            if slack > 0:
                time.sleep(slack)
