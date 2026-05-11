# type: ignore

"""学習環境の各ステップでテレメトリをキューへ積む Gymnasium ラッパ。"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium.core import ActType, ObsType


class RlTelemetryWrapper(gym.Wrapper[ObsType, ActType, ObsType, ActType]):
    """
    ``step`` / ``reset`` のたびに観測・行動などを ``publish`` へ渡す。

    - ``obs`` 末尾の ``prev_ctrl`` は環境定義どおり **1 ステップ遅れ**（前回適用コマンド）。
    - ``action`` は当該ステップで ``env.step`` に渡されたベクトル（クリップ前は上位で決まる）。
    """

    def __init__(
        self,
        env: gym.Env[ObsType, ActType],
        publish_step: Callable[[dict[str, Any]], None],
        publish_reset: Callable[[dict[str, Any]], None],
        *,
        max_hz: float | None = 60.0,
        get_num_timesteps: Callable[[], int] | None = None,
    ) -> None:
        super().__init__(env)
        self._publish_step = publish_step
        self._publish_reset = publish_reset
        self._max_hz = None if max_hz is None or max_hz <= 0 else float(max_hz)
        self._get_num_timesteps = get_num_timesteps
        self._last_emit_t = 0.0
        self._episode_step = 0
        self._actuator_names: list[str] = []

    def set_num_timesteps_getter(self, fn: Callable[[], int] | None) -> None:
        self._get_num_timesteps = fn

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self._episode_step = 0
        names = []
        if isinstance(info, dict):
            raw = info.get("actuator_names")
            if isinstance(raw, list):
                names = [str(x) for x in raw]
        self._actuator_names = names
        o = np.asarray(obs, dtype=np.float64)
        self._publish_reset(
            {
                "wall_time": time.time(),
                "actuator_names": list(self._actuator_names),
                "obs_dim": int(o.size),
                "obs_acc": o[:3].tolist(),
                "obs_gyro": o[3:6].tolist(),
                "obs_prev_ctrl": o[6:].tolist(),
                "obs_flat": o.tolist(),
                "num_timesteps": self._nts(),
            }
        )
        return obs, info

    def step(self, action: ActType):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._episode_step += 1
        now = time.time()
        if self._max_hz is not None:
            min_dt = 1.0 / self._max_hz
            if now - self._last_emit_t < min_dt:
                return obs, reward, terminated, truncated, info
            self._last_emit_t = now

        o = np.asarray(obs, dtype=np.float64)
        a = np.asarray(action, dtype=np.float64).reshape(-1)
        self._publish_step(
            {
                "wall_time": now,
                "episode_step": int(self._episode_step),
                "num_timesteps": self._nts(),
                "actuator_names": list(self._actuator_names),
                "obs_acc": o[:3].tolist(),
                "obs_gyro": o[3:6].tolist(),
                "obs_prev_ctrl": o[6:].tolist(),
                "obs_flat": o.tolist(),
                "action": a.tolist(),
            }
        )
        return obs, reward, terminated, truncated, info

    def _nts(self) -> int | None:
        if self._get_num_timesteps is None:
            return None
        try:
            return int(self._get_num_timesteps())
        except Exception:
            return None
