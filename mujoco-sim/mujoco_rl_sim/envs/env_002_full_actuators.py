# type: ignore

"""MJCF に定義された全アクチュエータに ``ctrl``（目標値）を与える環境。"""

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

    - 想定: 各アクチュエータが **position** 型で、ヒンジ関節を駆動している。
    - 行動: **正規化 action**（``nu`` 次元, 各軸 ``[-1, 1]``）。環境内で各関節の
      論理角レンジへ線形写像し、`mujoco_sim_common.kinematics.KINEMATICS` で MuJoCo
      関節角へ変換して `data.ctrl` に **目標角 [rad]** を設定する。
    - 観測: ``imu_acc``（3, 局所 **g** … MJCF 加速度計の m/s² を ``|model.opt.gravity|`` で除算）,
      ``imu_gyro``（3, 局所 rad/s）, **直前ステップで適用した** 論理角(度)（``nu``）を連結した ``(6 + nu,)`` ベクトル。MJCF に同名センサーが必要。
    - ``step_wall_sleep_sec``: 各 ``step`` の物理更新のあとに ``time.sleep`` する秒数（テレメトリ確認用。学習は壁時計で遅くなる）。
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
        if nu < 1:
            raise ValueError("MJCF にアクチュエータが1つもありません")

        self._joint_ids: list[int] = []
        ctrl_lows: list[float] = []
        ctrl_highs: list[float] = []
        logical_lows: list[float] = []
        logical_highs: list[float] = []
        self._actuator_names: list[str] = []
        self._actuator_kin: list[JointKinematicsBase] = []

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

        self._prev_action_logical_deg = np.zeros(nu, dtype=np.float32)

        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
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
        initial_logical = np.zeros(nu, dtype=np.float32)
        ctrl_rad = np.empty(nu, dtype=np.float32)

        # 論理角のデフォルト姿勢（kinematics）を基準に qpos と ctrl を揃える。
        # mj_resetData 直後は ctrl=0 のままだと、位置アクチュエータが関節を 0rad 目標に
        # 引き寄せようとして加速度計が異常に大きくなる。
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
        self._prev_action_logical_deg = initial_logical.copy()

        mujoco.mj_forward(self.model, self.data)
        return self._get_obs(), {"actuator_names": list(self._actuator_names)}

    def step(self, action):
        self.step_count += 1
        a_norm = np.asarray(action, dtype=np.float32).reshape(-1)
        if a_norm.shape[0] != self.model.nu:
            raise ValueError(
                f"action の長さは {self.model.nu} である必要があります（受け取り {a_norm.shape[0]}）"
            )
        a_norm = np.clip(a_norm, self.action_space.low, self.action_space.high)
        # [-1, 1] -> [logical_low, logical_high]
        a_logical = self._logical_low + 0.5 * (a_norm + 1.0) * (
            self._logical_high - self._logical_low
        )

        ctrl_rad = np.empty_like(a_logical, dtype=np.float32)
        for aid, kin in enumerate(self._actuator_kin):
            mujoco_deg = kin.logical_to_mujoco_deg(float(a_logical[aid]))
            ctrl_rad[aid] = float(np.deg2rad(mujoco_deg))
        ctrl_rad = np.clip(ctrl_rad, self._ctrl_low, self._ctrl_high)

        self.data.ctrl[:] = ctrl_rad
        mujoco.mj_step(self.model, self.data)
        if self._step_wall_sleep_sec > 0.0:
            time.sleep(self._step_wall_sleep_sec)

        obs = self._get_obs()
        self._prev_action_logical_deg = np.asarray(a_logical, dtype=np.float32).copy()

        torso_height = self._torso_height()
        # 物理的な大きさ（rad）に対する行動ペナルティ（常時）
        reward_action_penalty = float(-1e-4 * np.sum(np.square(ctrl_rad)))
        reward_fall_penalty = 0.0

        terminated = False
        if self._has_free_root and torso_height < 0.45:
            terminated = True
            reward_fall_penalty = -1.0

        reward = reward_action_penalty + reward_fall_penalty

        truncated = self.step_count >= self.max_steps
        return obs, reward, terminated, truncated, {
            "action_norm": a_norm.tolist(),
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
