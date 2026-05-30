"""両脚バイペッド向け観測（42 次元。foot_contact は契約維持のため未使用）。"""

from dataclasses import dataclass
from typing import NamedTuple

import mujoco
import numpy as np

from . import config
from .episode_state import EpisodeState
from .lib.actuators import JOINT_NAMES, LEFT_FOOT_SITE, RIGHT_FOOT_SITE
from mujoco_rl_sim.contract.validate import assert_obs_vector

from .experiment_contract import TELEMETRY_CONTRACT
from .lib.obs_norm import clip_scale, height_to_norm, range_to_norm

# biped_ppo_v1 契約上の foot_contact スロット。exp_022 では contact 走査を行わない。
_UNUSED_FOOT_CONTACT = -1.0


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
  in_stance: bool
  imu_gyro_x: float
  imu_gyro_y: float
  imu_gyro_z: float
  imu_zaxis_x: float
  imu_zaxis_y: float
  imu_zaxis_z: float
  upright: float
  joint_q: tuple[float, ...]
  joint_qvel: tuple[float, ...]
  left_knee_angle: float
  right_knee_angle: float


class Observation:
  def __init__(self, model: mujoco.MjModel):
    _ = model
    self._joint_q_ranges = [
      model.jnt_range[model.joint(name).id].copy() for name in JOINT_NAMES
    ]

  @staticmethod
  def _site_x(data: mujoco.MjData, site_name: str) -> float:
    return float(data.site(site_name).xpos[0])

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
    in_stance = imu_z < config.STANCE_IMU_Z_THRESHOLD

    imu_gyro = data.sensor("imu_gyro").data
    imu_zaxis = data.sensor("imu_zaxis").data
    upright = float(imu_zaxis[2])

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

    foot_dx = float(np.clip(left_foot_dx, 0.0, np.inf)) + float(
      np.clip(right_foot_dx, 0.0, np.inf)
    )

    z_min = config.MIN_IMU_Z_NORM
    z_max = config.MAX_IMU_Z

    obs = PolicyObs(
      clip_scale(dx, config.MAX_DX_PER_STEP),
      clip_scale(float(imu_gyro[0]), config.MAX_GYRO_RAD_S),
      clip_scale(float(imu_gyro[1]), config.MAX_GYRO_RAD_S),
      clip_scale(float(imu_gyro[2]), config.MAX_GYRO_RAD_S),
      float(imu_zaxis[0]),
      float(imu_zaxis[1]),
      float(imu_zaxis[2]),
      height_to_norm(imu_z, z_min, z_max),
      _UNUSED_FOOT_CONTACT,
      _UNUSED_FOOT_CONTACT,
      clip_scale(left_foot_dx, config.MAX_FOOT_DX_PER_STEP),
      clip_scale(right_foot_dx, config.MAX_FOOT_DX_PER_STEP),
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
      in_stance=in_stance,
      imu_gyro_x=float(imu_gyro[0]),
      imu_gyro_y=float(imu_gyro[1]),
      imu_gyro_z=float(imu_gyro[2]),
      imu_zaxis_x=float(imu_zaxis[0]),
      imu_zaxis_y=float(imu_zaxis[1]),
      imu_zaxis_z=float(imu_zaxis[2]),
      upright=upright,
      joint_q=tuple(joint_q),
      joint_qvel=tuple(joint_qvel),
      left_knee_angle=left_knee,
      right_knee_angle=right_knee,
    )
    return obs, step_physics
