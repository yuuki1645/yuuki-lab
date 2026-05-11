# type: ignore

"""MJCF に定義された全アクチュエータに ``ctrl``（目標値）を与える環境。"""

from __future__ import annotations

from pathlib import Path

import gymnasium as gym
import mujoco
import mujoco_sim_assets
import numpy as np
from gymnasium import spaces

_ASSETS_ROOT = Path(mujoco_sim_assets.__file__).resolve().parent
# この環境が既定で読み込む MJCF（必要ならここを書き換え。例: 002_leg_freejoint/main.xml）
DEFAULT_ENV_MODEL_XML = _ASSETS_ROOT / "xmls" / "002_leg_freejoint" / "main.xml"

_FALLBACK_HINGE = (-np.pi, np.pi)


def _ctrl_limits_for_actuator(model: mujoco.MjModel, aid: int) -> tuple[float, float]:
    """``actuator_ctrlrange`` → 関節 ``jnt_range`` → ヒンジ用フォールバックの順で決める。"""
    lo, hi = float(model.actuator_ctrlrange[aid, 0]), float(model.actuator_ctrlrange[aid, 1])
    if np.isfinite(lo) and np.isfinite(hi) and hi > lo + 1e-6:
        return lo, hi

    if int(model.actuator_trntype[aid]) != int(mujoco.mjtTrn.mjTRN_JOINT):
        return _FALLBACK_HINGE

    jid = int(model.actuator_trnid[aid, 0])
    jlo, jhi = float(model.jnt_range[jid, 0]), float(model.jnt_range[jid, 1])
    if np.isfinite(jlo) and np.isfinite(jhi) and jhi > jlo + 1e-6:
        return jlo, jhi

    return _FALLBACK_HINGE


def _hinge_joint_for_position_actuator(model: mujoco.MjModel, aid: int) -> int:
    if int(model.actuator_trntype[aid]) != int(mujoco.mjtTrn.mjTRN_JOINT):
        raise ValueError(
            f"アクチュエータ {aid} は joint 伝達ではありません（未対応の型です）"
        )
    jid = int(model.actuator_trnid[aid, 0])
    if int(model.jnt_type[jid]) != int(mujoco.mjtJoint.mjJNT_HINGE):
        raise ValueError(
            f"アクチュエータ {aid} の伝達先がヒンジ関節ではありません（未対応）"
        )
    return jid


class Env002FullActuators(gym.Env):
    """
    MJCF 上の **すべての** アクチュエータに対して ``data.ctrl`` を設定する環境。

    - 想定: 各アクチュエータが **position** 型で、ヒンジ関節を駆動している（``ctrl`` = 目標角 [rad]）。
    - 観測: ``imu_acc``（3, 局所 m/s²）, ``imu_gyro``（3, 局所 rad/s）, **直前ステップで適用した** ``ctrl``（``nu``）を連結した ``(6 + nu,)`` ベクトル。MJCF に同名センサーが必要。
    - 報酬: 小さな行動ペナルティのみ（タスク非依存）。必要に応じてラッパや別報酬で置き換えてください。

    既定 MJCF は本モジュール先頭の ``DEFAULT_ENV_MODEL_XML``。別ファイルを使うときは
    ``Env002FullActuators(xml_path=...)`` を指定。
    """

    metadata = {"render_modes": ["human"], "render_fps": 60}

    def __init__(
        self,
        xml_path: str | Path | None = None,
        max_steps: int = 500,
        reset_joint_noise: float = 0.05,
    ) -> None:
        super().__init__()
        path = Path(xml_path) if xml_path is not None else DEFAULT_ENV_MODEL_XML
        self.model = mujoco.MjModel.from_xml_path(str(path))
        self.data = mujoco.MjData(self.model)
        self.max_steps = max_steps
        self.reset_joint_noise = float(reset_joint_noise)
        self.step_count = 0

        nu = int(self.model.nu)
        if nu < 1:
            raise ValueError("MJCF にアクチュエータが1つもありません")

        self._joint_ids: list[int] = []
        lows: list[float] = []
        highs: list[float] = []
        self._actuator_names: list[str] = []

        for aid in range(nu):
            self._joint_ids.append(_hinge_joint_for_position_actuator(self.model, aid))
            lo, hi = _ctrl_limits_for_actuator(self.model, aid)
            lows.append(lo)
            highs.append(hi)
            name = mujoco.mj_id2name(
                self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, aid
            ) or f"actuator_{aid}"
            self._actuator_names.append(name)

        self._act_low = np.array(lows, dtype=np.float32)
        self._act_high = np.array(highs, dtype=np.float32)

        self._imu_acc_name = "imu_acc"
        self._imu_gyro_name = "imu_gyro"
        for sname, expected_dim in (
            (self._imu_acc_name, 3),
            (self._imu_gyro_name, 3),
        ):
            sid = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_SENSOR, sname
            )
            if sid < 0:
                raise ValueError(
                    f"MJCF に IMU センサー {sname!r} がありません。"
                    " ``<accelerometer name=\"imu_acc\" site=\"...\"/>`` および "
                    " ``<gyro name=\"imu_gyro\" site=\"...\"/>`` を含めてください。"
                )
            if int(self.model.sensor_dim[sid]) != expected_dim:
                raise ValueError(
                    f"センサー {sname!r} の次元は {expected_dim} である必要があります"
                    f"（実際 {int(self.model.sensor_dim[sid])}）"
                )

        self._prev_cmd = np.zeros(nu, dtype=np.float32)

        self.action_space = spaces.Box(
            low=self._act_low.copy(),
            high=self._act_high.copy(),
            shape=(nu,),
            dtype=np.float32,
        )
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(6 + nu,),
            dtype=np.float32,
        )

        self.root_joint_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, "root"
        )
        self._has_free_root = (
            self.root_joint_id >= 0
            and int(self.model.jnt_type[self.root_joint_id])
            == mujoco.mjtJoint.mjJNT_FREE
        )

    def _sensor_vec(self, name: str, dim: int) -> np.ndarray:
        sid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, name)
        adr = int(self.model.sensor_adr[sid])
        return np.asarray(
            self.data.sensordata[adr : adr + dim], dtype=np.float32
        ).copy()

    def _get_obs(self) -> np.ndarray:
        acc = self._sensor_vec(self._imu_acc_name, 3)
        gyr = self._sensor_vec(self._imu_gyro_name, 3)
        return np.concatenate([acc, gyr, self._prev_cmd])

    def _torso_height(self) -> float:
        if self._has_free_root:
            adr = int(self.model.jnt_qposadr[self.root_joint_id])
            return float(self.data.qpos[adr + 2])
        return 0.9

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.step_count = 0
        self._prev_cmd = np.zeros(int(self.model.nu), dtype=np.float32)

        for jid in self._joint_ids:
            qadr = int(self.model.jnt_qposadr[jid])
            lo, hi = float(self.model.jnt_range[jid, 0]), float(self.model.jnt_range[jid, 1])
            if hi > lo + 1e-6:
                mid = 0.5 * (lo + hi)
                span = hi - lo
                noise = self.np_random.uniform(
                    -self.reset_joint_noise * span,
                    self.reset_joint_noise * span,
                )
                self.data.qpos[qadr] = float(np.clip(mid + noise, lo, hi))
            else:
                self.data.qpos[qadr] += float(
                    self.np_random.uniform(-self.reset_joint_noise, self.reset_joint_noise)
                )

        mujoco.mj_forward(self.model, self.data)
        return self._get_obs(), {"actuator_names": list(self._actuator_names)}

    def step(self, action):
        self.step_count += 1
        a = np.asarray(action, dtype=np.float32).reshape(-1)
        if a.shape[0] != self.model.nu:
            raise ValueError(
                f"action の長さは {self.model.nu} である必要があります（受け取り {a.shape[0]}）"
            )
        a = np.clip(a, self.action_space.low, self.action_space.high)

        self.data.ctrl[:] = a
        mujoco.mj_step(self.model, self.data)

        obs = self._get_obs()
        self._prev_cmd = np.asarray(a, dtype=np.float32).copy()

        reward = float(-1e-4 * np.sum(np.square(a)))

        terminated = False
        if self._has_free_root and self._torso_height() < 0.45:
            terminated = True
            reward -= 1.0

        truncated = self.step_count >= self.max_steps
        return obs, reward, terminated, truncated, {}

    def render(self):
        return None

    def close(self) -> None:
        pass
