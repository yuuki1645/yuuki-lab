"""両脚バイペッド向け観測（51 次元・交互片脚歩行）。"""

from dataclasses import dataclass
from typing import NamedTuple

import mujoco

import config
from sim.episode_state import EpisodeState
from lib.actuators import (
  JOINT_NAMES,
  LEFT_FOOT_GEOM,
  LEFT_FOOT_SITE,
  RIGHT_FOOT_GEOM,
  RIGHT_FOOT_SITE,
)
from contract.validate import assert_obs_vector

from contract import TELEMETRY_CONTRACT
from lib.obs_norm import clip_scale, height_to_norm, range_to_norm
from lib.pose import pose_metrics

LEFT_HEEL_SITE = "heel_bottom_site"
LEFT_TOE_SITE = "toe_bottom_site"
RIGHT_HEEL_SITE = "right_heel_bottom_site"
RIGHT_TOE_SITE = "right_toe_bottom_site"


class PolicyObs(NamedTuple):
  dx: float
  imu_gyro_x: float
  imu_gyro_y: float
  imu_gyro_z: float
  imu_zaxis_x: float
  imu_zaxis_y: float
  imu_zaxis_z: float
  imu_z: float
  left_foot_contact: float
  right_foot_contact: float
  left_foot_dx: float
  right_foot_dx: float
  left_foot_z: float
  right_foot_z: float
  single_support: float
  joint_q: tuple[float, ...]
  joint_qvel: tuple[float, ...]
  prev_action: tuple[float, ...]

  def to_vector(self) -> tuple[float, ...]:
    vec = (
      self.dx,
      self.imu_gyro_x,
      self.imu_gyro_y,
      self.imu_gyro_z,
      self.imu_zaxis_x,
      self.imu_zaxis_y,
      self.imu_zaxis_z,
      self.imu_z,
      self.left_foot_contact,
      self.right_foot_contact,
      self.left_foot_dx,
      self.right_foot_dx,
      self.left_foot_z,
      self.right_foot_z,
      self.single_support,
      *self.joint_q,
      *self.joint_qvel,
      *self.prev_action,
    )
    assert_obs_vector(vec, TELEMETRY_CONTRACT)
    return vec


@dataclass(frozen=True)
class StepPhysics:
  imu_x: float
  rel_imu_x: float
  dx: float
  left_foot_x: float
  right_foot_x: float
  left_foot_dx: float
  right_foot_dx: float
  foot_dx: float
  imu_z: float
  left_foot_z: float
  right_foot_z: float
  left_toe_z: float
  left_heel_z: float
  right_toe_z: float
  right_heel_z: float
  left_foot_on_floor: bool
  right_foot_on_floor: bool
  any_foot_on_floor: bool
  single_support: bool
  single_support_side: int
  imu_gyro_x: float
  imu_gyro_y: float
  imu_gyro_z: float
  imu_zaxis_x: float
  imu_zaxis_y: float
  imu_zaxis_z: float
  upright: float
  lean_fwd_body: float
  heading_align: float
  tilt_horiz: float
  joint_q: tuple[float, ...]
  joint_qvel: tuple[float, ...]
  left_knee_angle: float
  right_knee_angle: float
  left_knee_vel: float
  right_knee_vel: float


class Observation:
  def __init__(self, model: mujoco.MjModel):
    self._floor_id = model.geom("floor").id
    self._left_foot_id = model.geom(LEFT_FOOT_GEOM).id
    self._right_foot_id = model.geom(RIGHT_FOOT_GEOM).id
    self._joint_q_ranges = [
      model.jnt_range[model.joint(name).id].copy() for name in JOINT_NAMES
    ]

  @staticmethod
  def _site_x(data: mujoco.MjData, site_name: str) -> float:
    return float(data.site(site_name).xpos[0])

  @staticmethod
  def _site_z(data: mujoco.MjData, site_name: str) -> float:
    return float(data.site(site_name).xpos[2])

  def _geom_on_floor(self, data: mujoco.MjData, geom_id: int) -> bool:
    for i in range(data.ncon):
      c = data.contact[i]
      if (c.geom1 == geom_id and c.geom2 == self._floor_id) or (
        c.geom2 == geom_id and c.geom1 == self._floor_id
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
    left_foot_dx: float = 0.0,
    right_foot_dx: float = 0.0,
  ) -> tuple[PolicyObs, StepPhysics]:
    _ = model
    imu_x = float(data.site("imu_site").xpos[0])
    imu_z = float(data.site("imu_site").xpos[2])
    rel_imu_x = imu_x - episode.origin_imu_x

    left_on = self._geom_on_floor(data, self._left_foot_id)
    right_on = self._geom_on_floor(data, self._right_foot_id)
    any_foot = left_on or right_on
    single_support = (left_on and not right_on) or (right_on and not left_on)
    if left_on and not right_on:
      support_side = 1
    elif right_on and not left_on:
      support_side = -1
    else:
      support_side = 0

    left_foot_z = self._site_z(data, LEFT_FOOT_SITE)
    right_foot_z = self._site_z(data, RIGHT_FOOT_SITE)
    left_toe_z = self._site_z(data, LEFT_TOE_SITE)
    left_heel_z = self._site_z(data, LEFT_HEEL_SITE)
    right_toe_z = self._site_z(data, RIGHT_TOE_SITE)
    right_heel_z = self._site_z(data, RIGHT_HEEL_SITE)

    imu_gyro = data.sensor("imu_gyro").data
    imu_zaxis = data.sensor("imu_zaxis").data
    upright = float(imu_zaxis[2])
    lean_fwd_body, heading_align, tilt_horiz = pose_metrics(imu_zaxis, data)

    joint_q: list[float] = []
    joint_qvel: list[float] = []
    joint_q_norm: list[float] = []
    joint_qvel_norm: list[float] = []
    for jname, q_range in zip(JOINT_NAMES, self._joint_q_ranges, strict=True):
      q = float(data.joint(jname).qpos[0])
      qv = float(data.joint(jname).qvel[0])
      joint_q.append(q)
      joint_qvel.append(qv)
      lo, hi = float(q_range[0]), float(q_range[1])
      joint_q_norm.append(range_to_norm(q, lo, hi))
      joint_qvel_norm.append(clip_scale(qv, config.MAX_JOINT_VEL_RAD_S))

    left_knee = float(data.joint("left_knee_pitch").qpos[0])
    right_knee = float(data.joint("right_knee_pitch").qpos[0])
    left_knee_vel = float(data.joint("left_knee_pitch").qvel[0])
    right_knee_vel = float(data.joint("right_knee_pitch").qvel[0])

    foot_dx = 0.0
    if single_support:
      if left_on:
        foot_dx = left_foot_dx
      else:
        foot_dx = right_foot_dx

    z_min = config.MIN_IMU_Z_NORM
    z_max = config.MAX_IMU_Z
    fz_min = config.MIN_FOOT_Z_NORM
    fz_max = config.MAX_FOOT_Z_NORM

    obs = PolicyObs(
      clip_scale(dx, config.MAX_DX_PER_STEP),
      clip_scale(float(imu_gyro[0]), config.MAX_GYRO_RAD_S),
      clip_scale(float(imu_gyro[1]), config.MAX_GYRO_RAD_S),
      clip_scale(float(imu_gyro[2]), config.MAX_GYRO_RAD_S),
      float(imu_zaxis[0]),
      float(imu_zaxis[1]),
      float(imu_zaxis[2]),
      height_to_norm(imu_z, z_min, z_max),
      1.0 if left_on else -1.0,
      1.0 if right_on else -1.0,
      clip_scale(left_foot_dx, config.MAX_FOOT_DX_PER_STEP),
      clip_scale(right_foot_dx, config.MAX_FOOT_DX_PER_STEP),
      height_to_norm(left_foot_z, fz_min, fz_max),
      height_to_norm(right_foot_z, fz_min, fz_max),
      1.0 if single_support else -1.0,
      tuple(joint_q_norm),
      tuple(joint_qvel_norm),
      tuple(episode.prev_action),
    )

    step_physics = StepPhysics(
      imu_x=imu_x,
      rel_imu_x=rel_imu_x,
      dx=dx,
      left_foot_x=self._site_x(data, LEFT_FOOT_SITE),
      right_foot_x=self._site_x(data, RIGHT_FOOT_SITE),
      left_foot_dx=left_foot_dx,
      right_foot_dx=right_foot_dx,
      foot_dx=foot_dx,
      imu_z=imu_z,
      left_foot_z=left_foot_z,
      right_foot_z=right_foot_z,
      left_toe_z=left_toe_z,
      left_heel_z=left_heel_z,
      right_toe_z=right_toe_z,
      right_heel_z=right_heel_z,
      left_foot_on_floor=left_on,
      right_foot_on_floor=right_on,
      any_foot_on_floor=any_foot,
      single_support=single_support,
      single_support_side=support_side,
      imu_gyro_x=float(imu_gyro[0]),
      imu_gyro_y=float(imu_gyro[1]),
      imu_gyro_z=float(imu_gyro[2]),
      imu_zaxis_x=float(imu_zaxis[0]),
      imu_zaxis_y=float(imu_zaxis[1]),
      imu_zaxis_z=float(imu_zaxis[2]),
      upright=upright,
      lean_fwd_body=lean_fwd_body,
      heading_align=heading_align,
      tilt_horiz=tilt_horiz,
      joint_q=tuple(joint_q),
      joint_qvel=tuple(joint_qvel),
      left_knee_angle=left_knee,
      right_knee_angle=right_knee,
      left_knee_vel=left_knee_vel,
      right_knee_vel=right_knee_vel,
    )
    return obs, step_physics
