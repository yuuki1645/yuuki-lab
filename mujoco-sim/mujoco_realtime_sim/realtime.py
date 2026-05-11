# type: ignore

"""実時間ペースで `mj_step` を回し続けるバックグラウンドスレッダ。

`Simulation._lock` で REST API（`/api/set` 等）と直列化される。
"""

from __future__ import annotations

import logging
import threading
import time

from mujoco_realtime_sim.core import Simulation

LOG = logging.getLogger("mujoco_realtime_sim.realtime")

# Windows の time.sleep は ~10〜15ms 粒度。短すぎると CPU を空回りするため、
# ループは 5ms 単位で起き、その間にたまった分をまとめて mj_step する。
_SLEEP_SLICE_S = 0.005

# 100ms 以上遅れたら追いつかず、現在時刻を新しい基準にする（暴走防止）。
_MAX_CATCHUP_S = 0.1


class RealtimeStepper:
    """`Simulation` を実時間ペースで進めるデーモンスレッド。

    - `start()` で背景スレッドを開始（多重起動は no-op）。
    - `pause()` / `resume()` で一時停止／再開。停止中は時間が貯まらない。
    - `stop()` でスレッド停止（プロセス終了時も daemon=True なので自然停止）。
    """

    def __init__(self, sim: Simulation) -> None:
        self._sim = sim
        self._dt = float(sim.model.opt.timestep)
        if self._dt <= 0:
            raise ValueError(
                f"model.opt.timestep must be > 0 (got {self._dt})"
            )
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="mujoco-sim-realtime",
            daemon=True,
        )
        self._thread.start()
        LOG.info(
            "Realtime stepper started (timestep=%.4fs, %.0f Hz)",
            self._dt,
            1.0 / self._dt,
        )

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1.0)
        self._thread = None

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        last = time.perf_counter()
        while not self._stop.is_set():
            time.sleep(_SLEEP_SLICE_S)
            if self._paused.is_set():
                last = time.perf_counter()
                continue
            now = time.perf_counter()
            elapsed = now - last
            if elapsed > _MAX_CATCHUP_S:
                last = now
                continue
            n = int(elapsed / self._dt)
            if n < 1:
                continue
            try:
                self._sim.step(n)
            except Exception:
                LOG.exception("realtime step failed; pausing stepper")
                self._paused.set()
                continue
            last += n * self._dt
