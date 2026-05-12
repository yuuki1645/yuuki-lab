# type: ignore

"""アクチュエータ無し MJCF（受動関節）または指令固定のベースライン環境。"""

from __future__ import annotations

from pathlib import Path
import time

import gymnasium as gym
import mujoco
import mujoco_sim_assets
import numpy as np
from gymnasium import spaces
from mujoco_sim_common.kinematics import KINEMATICS, JointKinematicsBase

_ASSETS_ROOT = Path(mujoco_sim_assets.__file__).resolve().parent
DEFAULT_ENV_MODEL_XML = _ASSETS_ROOT / "xmls" / "003_leg_freejoint" / "main.xml"

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


def _joint_rad_limits(model: mujoco.MjModel, jid: int) -> tuple[float, float]:
    jlo, jhi = float(model.jnt_range[jid, 0]), float(model.jnt_range[jid, 1])
    if np.isfinite(jlo) and np.isfinite(jhi) and jhi > jlo + 1e-6:
        return jlo, jhi
    return _FALLBACK_HINGE


class Env003StaticActuators(gym.Env):
    """
    既定 MJCF は ``003_leg_freejoint``（**アクチュエータ無し**・ヒンジはダンピングのみ）。

    - **受動モード**（``model.nu == 0``）: ``reset`` で ``KINEMATICS`` に基づきヒンジ ``qpos``
      のみ設定し、``mj_step`` のみ（トルク指令なし）。観測は IMU **6 次元**。
      行動は Stable-Baselines3 互換の **ダミー 1 次元**（無視）。
    - **指令固定モード**（``xml_path`` で ``002`` 等 ``nu >= 1`` を指定した場合）:
      ``reset`` で決めた ``ctrl`` をエピソード中固定し、002 と同様に末尾に論理角 prev を連結した ``6+nu`` 次元。
    """

    metadata = {"render_modes": ["human"], "render_fps": 60}

    def __init__(
        self,
        xml_path: str | Path | None = None,
        max_steps: int = 500,
        reset_joint_noise: float = 0.05,
        step_wall_sleep_sec: float = 0.0,
    ) -> None:
        super().__init__()
        path = Path(xml_path) if xml_path is not None else DEFAULT_ENV_MODEL_XML
        self.model = mujoco.MjModel.from_xml_path(str(path))
        self.data = mujoco.MjData(self.model)
        self.max_steps = max_steps
        self.reset_joint_noise = float(reset_joint_noise)
        self._step_wall_sleep_sec = max(0.0, float(step_wall_sleep_sec))
        self.step_count = 0

        nu = int(self.model.nu)
        self._passive = nu == 0

        self._joint_ids: list[int] = []
        self._ctrl_low = np.array([], dtype=np.float32)
        self._ctrl_high = np.array([], dtype=np.float32)
        self._logical_low = np.array([], dtype=np.float32)
        self._logical_high = np.array([], dtype=np.float32)
        self._actuator_names: list[str] = []
        self._actuator_kin: list[JointKinematicsBase] = []
        self._passive_kins: list[JointKinematicsBase] = []

        if self._passive:
            seen_joints: set[str] = set()
            for kin in KINEMATICS.values():
                jid = mujoco.mj_name2id(
                    self.model, mujoco.mjtObj.mjOBJ_JOINT, kin.joint
                )
                if jid < 0:
                    continue
                if kin.joint in seen_joints:
                    continue
                seen_joints.add(kin.joint)
                self._passive_kins.append(kin)
                self._joint_ids.append(jid)
            if not self._passive_kins:
                raise ValueError(
                    "受動 MJCF ですが KINEMATICS と対応するヒンジ関節が1つも見つかりません"
                )
            obs_tail = 0
            act_dim = 1
        else:
            if nu < 1:
                raise ValueError("MJCF にアクチュエータが1つもありません")

            ctrl_lows: list[float] = []
            ctrl_highs: list[float] = []
            logical_lows: list[float] = []
            logical_highs: list[float] = []

            for aid in range(nu):
                self._joint_ids.append(_hinge_joint_for_position_actuator(self.model, aid))
                lo, hi = _ctrl_limits_for_actuator(self.model, aid)
                ctrl_lows.append(lo)
                ctrl_highs.append(hi)
                name = mujoco.mj_id2name(
                    self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, aid
                ) or f"actuator_{aid}"
                self._actuator_names.append(name)

                kin = KINEMATICS.get(name)
                if kin is None:
                    raise KeyError(
                        f"論理角 kinematics が未登録のアクチュエータです: {name!r}"
                    )
                self._actuator_kin.append(kin)
                logical_lows.append(float(kin.logical_range.lo))
                logical_highs.append(float(kin.logical_range.hi))

            self._ctrl_low = np.array(ctrl_lows, dtype=np.float32)
            self._ctrl_high = np.array(ctrl_highs, dtype=np.float32)
            self._logical_low = np.array(logical_lows, dtype=np.float32)
            self._logical_high = np.array(logical_highs, dtype=np.float32)
            obs_tail = nu
            act_dim = nu

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

        self._prev_action_logical_deg = np.zeros(obs_tail, dtype=np.float32)
        self._fixed_ctrl_rad = np.zeros(nu, dtype=np.float32)

        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(act_dim,),
            dtype=np.float32,
        )

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(6 + obs_tail,),
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

    def _acc_sensor_ms2_to_g(self, acc_ms2: np.ndarray) -> np.ndarray:
        """MJCF 加速度計（m/s²）を、モデル重力の大きさで割って g 単位にする。"""
        g_mag = float(np.linalg.norm(self.model.opt.gravity))
        if not np.isfinite(g_mag) or g_mag < 1e-6:
            g_mag = 9.80665
        return acc_ms2 / np.float32(g_mag)

    def _get_obs(self) -> np.ndarray:
        acc_ms2 = self._sensor_vec(self._imu_acc_name, 3)
        acc = self._acc_sensor_ms2_to_g(acc_ms2)
        gyr = self._sensor_vec(self._imu_gyro_name, 3)
        if self._passive:
            return np.concatenate([acc, gyr])
        return np.concatenate([acc, gyr, self._prev_action_logical_deg])

    def _torso_height(self) -> float:
        if self._has_free_root:
            adr = int(self.model.jnt_qposadr[self.root_joint_id])
            return float(self.data.qpos[adr + 2])
        return 0.9

    def set_step_wall_sleep_sec(self, value: float) -> None:
        self._step_wall_sleep_sec = max(0.0, float(value))

    def get_step_wall_sleep_sec(self) -> float:
        return float(self._step_wall_sleep_sec)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.step_count = 0
        nu = int(self.model.nu)

        if self._passive:
            initial_logical = np.zeros(len(self._passive_kins), dtype=np.float32)
            for i, kin in enumerate(self._passive_kins):
                jid = mujoco.mj_name2id(
                    self.model, mujoco.mjtObj.mjOBJ_JOINT, kin.joint
                )
                qadr = int(self.model.jnt_qposadr[jid])
                span = float(kin.logical_range.hi - kin.logical_range.lo)
                noise = self.np_random.uniform(
                    -self.reset_joint_noise * span,
                    self.reset_joint_noise * span,
                )
                logical_deg = float(kin.default_logical + noise)
                initial_logical[i] = float(logical_deg)
                mujoco_deg = float(kin.logical_to_mujoco_deg(logical_deg))
                rad = float(np.deg2rad(mujoco_deg))
                lo, hi = _joint_rad_limits(self.model, jid)
                self.data.qpos[qadr] = float(np.clip(rad, lo, hi))
            self._prev_action_logical_deg = np.array([], dtype=np.float32)
            info = {
                "actuator_names": [],
                "passive": True,
                "kinematics_joint_names": [k.joint for k in self._passive_kins],
            }
        else:
            initial_logical = np.zeros(nu, dtype=np.float32)
            ctrl_rad = np.empty(nu, dtype=np.float32)

            for aid, kin in enumerate(self._actuator_kin):
                jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, kin.joint)
                if jid < 0:
                    raise ValueError(
                        f"kinematics が参照する joint {kin.joint!r} が MJCF にありません"
                    )
                qadr = int(self.model.jnt_qposadr[jid])

                span = float(kin.logical_range.hi - kin.logical_range.lo)
                noise = self.np_random.uniform(
                    -self.reset_joint_noise * span,
                    self.reset_joint_noise * span,
                )
                logical_deg = float(kin.default_logical + noise)
                initial_logical[aid] = float(logical_deg)
                mujoco_deg = float(kin.logical_to_mujoco_deg(logical_deg))
                rad = float(np.deg2rad(mujoco_deg))
                self.data.qpos[qadr] = rad
                ctrl_rad[aid] = rad

            ctrl_rad = np.clip(ctrl_rad, self._ctrl_low, self._ctrl_high)
            self.data.ctrl[:] = ctrl_rad
            self._fixed_ctrl_rad = np.asarray(ctrl_rad, dtype=np.float32).copy()
            self._prev_action_logical_deg = initial_logical.copy()
            info = {
                "actuator_names": list(self._actuator_names),
                "passive": False,
            }

        mujoco.mj_forward(self.model, self.data)
        return self._get_obs(), info

    def step(self, action):
        self.step_count += 1
        a_norm = np.asarray(action, dtype=np.float32).reshape(-1)
        expected = int(np.prod(self.action_space.shape))
        if a_norm.shape[0] != expected:
            raise ValueError(
                f"action の長さは {expected} である必要があります（受け取り {a_norm.shape[0]}）"
            )

        a_norm = np.clip(a_norm, self.action_space.low, self.action_space.high)

        if self._passive:
            nu_tail = 0
            delta_logical = np.array([], dtype=np.float32)
            a_logical = np.array([], dtype=np.float32)
            ctrl_rad = np.array([], dtype=np.float32)
        else:
            nu_tail = int(self.model.nu)
            delta_logical = np.zeros(nu_tail, dtype=np.float32)
            a_logical = np.asarray(self._prev_action_logical_deg, dtype=np.float32).copy()
            ctrl_rad = np.asarray(self._fixed_ctrl_rad, dtype=np.float32)
            self.data.ctrl[:] = ctrl_rad

        mujoco.mj_step(self.model, self.data)
        if self._step_wall_sleep_sec > 0.0:
            time.sleep(self._step_wall_sleep_sec)

        obs = self._get_obs()

        torso_height = self._torso_height()
        if self._passive:
            reward_action_penalty = 0.0
        else:
            reward_action_penalty = float(-1e-4 * np.sum(np.square(ctrl_rad)))
        reward_fall_penalty = 0.0

        terminated = False
        if self._has_free_root and torso_height < 0.45:
            terminated = True
            reward_fall_penalty = -1.0

        reward = reward_action_penalty + reward_fall_penalty

        truncated = self.step_count >= self.max_steps
        return obs, reward, terminated, truncated, {
            "action_ignored": True,
            "passive": self._passive,
            "action_norm": a_norm.tolist(),
            "action_delta_logical_deg": delta_logical.tolist(),
            "action_delta_logical_unit": "logical_deg",
            "action_logical_deg": a_logical.tolist(),
            "action_logical_unit": "logical_deg",
            "reward_total": float(reward),
            "reward_action_penalty": float(reward_action_penalty),
            "reward_fall_penalty": float(reward_fall_penalty),
            "torso_height": float(torso_height),
            "is_fallen": bool(terminated and reward_fall_penalty < 0.0),
            "step_wall_sleep_sec": float(self._step_wall_sleep_sec),
        }

    def render(self):
        return None

    def close(self) -> None:
        pass
