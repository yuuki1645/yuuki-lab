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

    - ``obs`` 末尾の ``prev_*`` は環境定義どおり **1 ステップ遅れ**（前回適用コマンド）。
    - ``action`` は当該ステップで ``env.step`` に渡された正規化ベクトル（``[-1, 1]``）。
    - step イベントでは ``obs_*`` を「エージェント入力（step 前観測）」として送る。
      物理更新後の観測は ``obs_next_*`` で併送する。
    - ``Env002FullActuators`` では ``obs`` 末尾は直前コマンドの論理角（deg）、``action`` は ``[-1,1]`` の正規化ベクトル、
      ``info['action_logical_deg']`` が解決後の論理角。先頭 3 要素の加速度は **g** であるため、
      payload に ``*_logical_deg``・``*_unit``・``obs_acc_unit`` 等を明示して送る。
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
        self._last_obs: np.ndarray | None = None

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
        self._last_obs = o.copy()
        self._publish_reset(
            {
                "wall_time": time.time(),
                "actuator_names": list(self._actuator_names),
                "obs_dim": int(o.size),
                "obs_acc": o[:3].tolist(),
                "obs_acc_unit": "g",
                "obs_gyro": o[3:6].tolist(),
                "obs_prev_ctrl": o[6:].tolist(),
                "obs_prev_action_logical_deg": o[6:].tolist(),
                "obs_prev_action_unit": "logical_deg",
                "obs_flat": o.tolist(),
                "num_timesteps": self._nts(),
            }
        )
        return obs, info

    def step(self, action: ActType):
        obs_before = self._last_obs.copy() if self._last_obs is not None else None
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._episode_step += 1
        now = time.time()
        if self._max_hz is not None:
            min_dt = 1.0 / self._max_hz
            if now - self._last_emit_t < min_dt:
                return obs, reward, terminated, truncated, info
            self._last_emit_t = now

        o_next = np.asarray(obs, dtype=np.float64)
        if obs_before is None:
            # 通常は reset 後に step が呼ばれるため発生しないが、保険として次観測を採用する。
            obs_before = o_next
        self._last_obs = o_next.copy()
        a_norm = np.asarray(action, dtype=np.float64).reshape(-1)
        info_dict = info if isinstance(info, dict) else {}
        a_logical = np.asarray(
            info_dict.get("action_logical_deg", a_norm.tolist()),
            dtype=np.float64,
        ).reshape(-1)
        reward_total = float(info_dict.get("reward_total", reward))
        reward_action_penalty = float(
            info_dict.get("reward_action_penalty", reward_total)
        )
        reward_fall_penalty = float(info_dict.get("reward_fall_penalty", 0.0))
        torso_height = info_dict.get("torso_height")
        torso_height_num = (
            float(torso_height)
            if isinstance(torso_height, (float, int))
            else None
        )
        step_wall_sleep = info_dict.get("step_wall_sleep_sec")
        step_wall_sleep_num = (
            float(step_wall_sleep)
            if isinstance(step_wall_sleep, (float, int))
            else None
        )
        is_fallen = bool(info_dict.get("is_fallen", bool(terminated)))
        self._publish_step(
            {
                "wall_time": now,
                "episode_step": int(self._episode_step),
                "num_timesteps": self._nts(),
                "actuator_names": list(self._actuator_names),
                # エージェントが意思決定に使った入力観測（step 前）
                "obs_acc": obs_before[:3].tolist(),
                "obs_acc_unit": "g",
                "obs_gyro": obs_before[3:6].tolist(),
                "obs_prev_ctrl": obs_before[6:].tolist(),
                "obs_prev_action_logical_deg": obs_before[6:].tolist(),
                "obs_prev_action_unit": "logical_deg",
                "obs_flat": obs_before.tolist(),
                "action": a_norm.tolist(),
                "action_norm": a_norm.tolist(),
                "action_norm_unit": "normalized",
                "action_logical_deg": a_logical.tolist(),
                "action_unit": "logical_deg",
                "reward": reward_total,
                "reward_total": reward_total,
                "reward_action_penalty": reward_action_penalty,
                "reward_fall_penalty": reward_fall_penalty,
                "torso_height": torso_height_num,
                "step_wall_sleep_sec": step_wall_sleep_num,
                "is_fallen": is_fallen,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                # 物理更新後の次観測（s_{t+1}）
                "obs_next_acc": o_next[:3].tolist(),
                "obs_next_acc_unit": "g",
                "obs_next_gyro": o_next[3:6].tolist(),
                "obs_next_prev_ctrl": o_next[6:].tolist(),
                "obs_next_prev_action_logical_deg": o_next[6:].tolist(),
                "obs_next_prev_action_unit": "logical_deg",
                "obs_next_flat": o_next.tolist(),
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
