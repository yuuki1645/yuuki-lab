# type: ignore

from __future__ import annotations

from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

from mujoco_realtime_sim.paths import resolved_model_xml


class KneeTrackEnv(gym.Env):
    """
    Minimal MuJoCo RL task:
    - Control only left_knee_pitch target angle (position actuator control).
    - Reward is high when the joint angle tracks a fixed target.

    既定 MJCF は ``mujoco_realtime_sim`` 同梱の ``xmls/main.xml``（環境変数
    ``MUJOCO_REALTIME_SIM_XML`` / ``MUJOCO_SIM_XML`` で上書き可）。
    """

    metadata = {"render_modes": ["human"], "render_fps": 60}

    def __init__(self, xml_path: str | Path | None = None, max_steps: int = 500):
        super().__init__()
        path = Path(xml_path) if xml_path is not None else resolved_model_xml()
        self.model = mujoco.MjModel.from_xml_path(str(path))
        self.data = mujoco.MjData(self.model)
        self.max_steps = max_steps
        self.step_count = 0

        self.knee_joint_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, "left_knee_pitch"
        )
        self.knee_act_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, "left_knee_pitch_motor"
        )
        self.root_joint_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, "root"
        )
        self._has_free_root = (
            self.root_joint_id >= 0
            and int(self.model.jnt_type[self.root_joint_id])
            == mujoco.mjtJoint.mjJNT_FREE
        )

        self.action_space = spaces.Box(
            low=np.array([-0.7], dtype=np.float32),
            high=np.array([0.2], dtype=np.float32),
            dtype=np.float32,
        )
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32
        )

        self.target_angle = -0.25

    def _get_obs(self) -> np.ndarray:
        qpos_adr = self.model.jnt_qposadr[self.knee_joint_id]
        qvel_adr = self.model.jnt_dofadr[self.knee_joint_id]
        knee_angle = self.data.qpos[qpos_adr]
        knee_vel = self.data.qvel[qvel_adr]

        if self._has_free_root:
            root_qpos_adr = self.model.jnt_qposadr[self.root_joint_id]
            torso_height = float(self.data.qpos[root_qpos_adr + 2])
            torso_pitch_proxy = float(self.data.qpos[root_qpos_adr + 5])
        else:
            # 実時間用 MJCF は root をコメントアウトしていることがある
            torso_height = 0.9
            torso_pitch_proxy = 0.0

        return np.array(
            [knee_angle, knee_vel, torso_height, torso_pitch_proxy], dtype=np.float32
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.step_count = 0

        qpos_adr = self.model.jnt_qposadr[self.knee_joint_id]
        self.data.qpos[qpos_adr] = self.np_random.uniform(-0.2, 0.0)
        mujoco.mj_forward(self.model, self.data)
        return self._get_obs(), {}

    def step(self, action):
        self.step_count += 1
        action = np.clip(action, self.action_space.low, self.action_space.high)

        self.data.ctrl[:] = 0.0
        self.data.ctrl[self.knee_act_id] = float(action[0])
        mujoco.mj_step(self.model, self.data)

        obs = self._get_obs()
        knee_angle = float(obs[0])
        knee_vel = float(obs[1])
        torso_height = float(obs[2])

        err = knee_angle - self.target_angle
        reward = 1.0 - 2.0 * (err * err) - 0.02 * abs(knee_vel)

        terminated = False
        if self._has_free_root and torso_height < 0.45:
            terminated = True
            reward -= 3.0

        truncated = self.step_count >= self.max_steps
        return obs, reward, terminated, truncated, {}

    def render(self):
        return None

    def close(self):
        pass
