"""exp_002 の観測ベクトル組み立て。

MuJoCo の site / sensor / joint から
  - ObsExp002 … ポリシー入力（正規化・クリップ済み、19 次元）
  - StepPhysics … 報酬・ログ用の生物理量
を同一タイミングで生成する。
"""

from dataclasses import dataclass
from typing import NamedTuple

import mujoco

import config
from debug import print_step_overlay
from episode_state import EpisodeState
from lib.obs_norm import clip_scale, height_to_norm, range_to_norm


class ObsExp002(NamedTuple):
  """正規化済み観測（おおよそ [-1, 1]）。フィールド順 = ポリシー入力順。

  累積前進 rel_imu_x は固定スポーンでは世界 X に近いためポリシー入力から除外。
  前進は dx のみ。デバッグ用の rel_imu_x は StepPhysics に残す。
  """

  dx: float  # 直前制御ステップからの IMU X 変位 [m]
  foot_on_floor: float  # 接地 1.0 / 非接地 -1.0
  imu_gyro_x: float
  imu_gyro_y: float
  imu_gyro_z: float
  imu_zaxis_x: float  # IMU 上向き単位ベクトル（直立時 z≈1）
  imu_zaxis_y: float
  imu_zaxis_z: float
  imu_z: float
  foot_z: float
  foot_xaxis_z: float
  knee: float
  ankle: float
  knee_vel: float
  ankle_vel: float
  com_x: float  # COM X − 趾 X（前後の体重偏り）
  com_z: float
  prev_knee_action: float  # 直前ステップのポリシー出力 [-1, 1]
  prev_ankle_action: float

  def to_vector(self) -> tuple[float, ...]:
    return tuple(self)


@dataclass(frozen=True)
class StepPhysics:
  """1 制御ステップ時点の物理量（ポリシー観測の正規化前）。

  報酬計算・デバッグ表示・step_info で共有する。
  """

  imu_x: float
  rel_imu_x: float
  dx: float
  foot_x: float
  foot_dx: float
  imu_z: float
  foot_z: float
  foot_on_floor: bool
  imu_gyro_x: float
  imu_gyro_y: float
  imu_gyro_z: float
  imu_zaxis_x: float
  imu_zaxis_y: float
  imu_zaxis_z: float
  foot_xaxis_z: float
  knee_angle: float
  ankle_angle: float
  knee_vel: float
  ankle_vel: float
  com_x: float
  com_z: float
  upright: float  # imu_zaxis_z。前進報酬の直立条件に使用（reward.py）


class Observation:
  """MuJoCo 状態から ObsExp002 を組み立てる。"""

  def __init__(self, model: mujoco.MjModel):
    self._basket_thigh_body_id = model.body("basket_thigh").id
    self._floor_id = model.geom("floor").id
    self._foot_id = model.geom("foot_plate").id
    self._knee_q_range = model.jnt_range[model.joint("knee").id].copy()
    self._ankle_q_range = model.jnt_range[model.joint("ankle").id].copy()
    self._debug_step_counter = 0

  @staticmethod
  def _imu_x(data: mujoco.MjData) -> float:
    return float(data.site("imu_site").xpos[0])

  @staticmethod
  def _foot_x(data: mujoco.MjData) -> float:
    return float(data.site("foot_site").xpos[0])

  @staticmethod
  def _imu_z(data: mujoco.MjData) -> float:
    return float(data.site("imu_site").xpos[2])

  def _foot_on_floor(self, data: mujoco.MjData) -> bool:
    """foot_plate geom と floor の接触の有無。"""
    for i in range(data.ncon):
      c = data.contact[i]
      if (c.geom1 == self._foot_id and c.geom2 == self._floor_id) or (
        c.geom2 == self._foot_id and c.geom1 == self._floor_id
      ):
        return True
    return False

  def build(
    self,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    episode: EpisodeState,
    *,
    dx: float,
    foot_dx: float = 0.0,
  ) -> tuple[ObsExp002, StepPhysics]:
    """制御ステップ末の MjData から観測ペアを構築する。dx / foot_dx は EpisodeState が計算済み。"""
    imu_x = self._imu_x(data)
    foot_x = self._foot_x(data)
    imu_z = self._imu_z(data)
    rel_imu_x = imu_x - episode.origin_imu_x

    foot_on_floor = self._foot_on_floor(data)

    # --- 生物理量の読み取り ---------------------------------------------------
    imu_gyro = data.sensor("imu_gyro").data
    imu_gyro_x = float(imu_gyro[0])
    imu_gyro_y = float(imu_gyro[1])
    imu_gyro_z = float(imu_gyro[2])

    imu_zaxis = data.sensor("imu_zaxis").data
    imu_zaxis_x = float(imu_zaxis[0])
    imu_zaxis_y = float(imu_zaxis[1])
    imu_zaxis_z = float(imu_zaxis[2])
    upright = imu_zaxis_z

    foot_z = float(data.site("foot_site").xpos[2])
    foot_xaxis_z = float(data.sensor("foot_xaxis").data[2])

    knee_angle = float(data.joint("knee").qpos[0])
    ankle_angle = float(data.joint("ankle").qpos[0])
    knee_vel = float(data.joint("knee").qvel[0])
    ankle_vel = float(data.joint("ankle").qvel[0])

    toe_pos = data.sensor("toe_pos").data
    com = data.subtree_com[self._basket_thigh_body_id]
    com_x = float(com[0] - toe_pos[0])
    com_z = float(com[2])

    z_min = config.MIN_IMU_Z_NORM
    z_max = config.MAX_IMU_Z

    # --- ポリシー観測（正規化）とログ用生値の組み立て -------------------------
    obs = ObsExp002(
      clip_scale(dx, config.MAX_DX_PER_STEP),
      1.0 if foot_on_floor else -1.0,
      clip_scale(imu_gyro_x, config.MAX_GYRO_RAD_S),
      clip_scale(imu_gyro_y, config.MAX_GYRO_RAD_S),
      clip_scale(imu_gyro_z, config.MAX_GYRO_RAD_S),
      imu_zaxis_x,
      imu_zaxis_y,
      imu_zaxis_z,
      height_to_norm(imu_z, z_min, z_max),
      height_to_norm(foot_z, z_min, z_max),
      foot_xaxis_z,
      range_to_norm(knee_angle, self._knee_q_range[0], self._knee_q_range[1]),
      range_to_norm(ankle_angle, self._ankle_q_range[0], self._ankle_q_range[1]),
      clip_scale(knee_vel, config.MAX_JOINT_VEL_RAD_S),
      clip_scale(ankle_vel, config.MAX_JOINT_VEL_RAD_S),
      clip_scale(com_x, config.MAX_COM_X_OFFSET),
      height_to_norm(com_z, z_min, z_max),
      float(episode.prev_action[0]),
      float(episode.prev_action[1]),
    )

    step_physics = StepPhysics(
      imu_x=imu_x,
      rel_imu_x=rel_imu_x,
      dx=dx,
      foot_x=foot_x,
      foot_dx=foot_dx,
      imu_z=imu_z,
      foot_z=foot_z,
      foot_on_floor=foot_on_floor,
      imu_gyro_x=imu_gyro_x,
      imu_gyro_y=imu_gyro_y,
      imu_gyro_z=imu_gyro_z,
      imu_zaxis_x=imu_zaxis_x,
      imu_zaxis_y=imu_zaxis_y,
      imu_zaxis_z=imu_zaxis_z,
      foot_xaxis_z=foot_xaxis_z,
      knee_angle=knee_angle,
      ankle_angle=ankle_angle,
      knee_vel=knee_vel,
      ankle_vel=ankle_vel,
      com_x=com_x,
      com_z=com_z,
      upright=upright,
    )
    return obs, step_physics

  def maybe_print_debug(
    self,
    *,
    episode_step: int,
    reward: float,
    step_physics: StepPhysics,
    episode: EpisodeState,
  ) -> None:
    """100 制御ステップごとにターミナルへ物理量オーバーレイを表示（env から呼ぶ）。"""
    if self._debug_step_counter != 100:
      self._debug_step_counter += 1
      return

    self._debug_step_counter = 0
    print_step_overlay(
      episode_step=float(episode_step),
      reward=reward,
      foot_on_floor=step_physics.foot_on_floor,
      imu_gyro_x=step_physics.imu_gyro_x,
      imu_gyro_y=step_physics.imu_gyro_y,
      imu_gyro_z=step_physics.imu_gyro_z,
      imu_zaxis_x=step_physics.imu_zaxis_x,
      imu_zaxis_y=step_physics.imu_zaxis_y,
      imu_zaxis_z=step_physics.imu_zaxis_z,
      imu_x=step_physics.imu_x,
      rel_imu_x=step_physics.rel_imu_x,
      dx=step_physics.dx,
      imu_z=step_physics.imu_z,
      foot_z=step_physics.foot_z,
      foot_xaxis_z=step_physics.foot_xaxis_z,
      knee_angle=step_physics.knee_angle,
      ankle_angle=step_physics.ankle_angle,
      knee_vel=step_physics.knee_vel,
      ankle_vel=step_physics.ankle_vel,
      com_x=step_physics.com_x,
      com_z=step_physics.com_z,
      prev_knee_action=episode.prev_action[0],
      prev_ankle_action=episode.prev_action[1],
    )
    self._debug_step_counter += 1
