"""biped_walk_v1: 51 次元観測・交互片脚歩行向けテレメトリ契約。"""

from __future__ import annotations

from contract.spec import (
  ObservationSlice,
  ObservationSpec,
  RewardLogTerm,
  RewardLogSpec,
  TelemetryContract,
)

BIPED_WALK_V1_OBS_DIM = 51

_BIPED_WALK_OBS_SLICES: tuple[ObservationSlice, ...] = (
  ObservationSlice("obs_dx", 0, 1, "scalar", "IMU +X 移動量（正規化）"),
  ObservationSlice("obs_imu_gyro", 1, 4, "vector", "IMU 角速度 rad/s（正規化）"),
  ObservationSlice("obs_imu_zaxis", 4, 7, "vector", "IMU 上向き単位ベクトル"),
  ObservationSlice("obs_imu_z_norm", 7, 8, "scalar", "IMU 高さ（正規化）"),
  ObservationSlice("obs_left_foot_contact", 8, 9, "scalar", "左足接地 ±1"),
  ObservationSlice("obs_right_foot_contact", 9, 10, "scalar", "右足接地 ±1"),
  ObservationSlice("obs_left_foot_dx", 10, 11, "scalar", "左足 +X 移動量（正規化）"),
  ObservationSlice("obs_right_foot_dx", 11, 12, "scalar", "右足 +X 移動量（正規化）"),
  ObservationSlice("obs_left_foot_z_norm", 12, 13, "scalar", "左足 site Z（正規化）"),
  ObservationSlice("obs_right_foot_z_norm", 13, 14, "scalar", "右足 site Z（正規化）"),
  ObservationSlice("obs_single_support", 14, 15, "scalar", "片足支持 +1 / それ以外 -1"),
  ObservationSlice("obs_joint_q_norm", 15, 27, "vector", "関節角 q（正規化）×12"),
  ObservationSlice("obs_joint_qvel_norm", 27, 39, "vector", "関節角速度（正規化）×12"),
  ObservationSlice("obs_prev_action_norm", 39, 51, "vector", "直前 action [-1,1]×12"),
)

_BIPED_WALK_REWARD_LOG = RewardLogSpec(
  terms=(
    RewardLogTerm("reward_total", "報酬 total"),
    RewardLogTerm("reward_forward", "前進合計"),
    RewardLogTerm("reward_forward_imu", "IMU 前進"),
    RewardLogTerm("reward_forward_foot", "支持脚前進"),
    RewardLogTerm("reward_shaping", "shaping 合計"),
    RewardLogTerm("reward_double_support_penalty", "両足支持ペナルティ"),
    RewardLogTerm("reward_alternating_landing", "交互着地ボーナス"),
    RewardLogTerm("reward_fall_penalty", "転倒・姿勢ペナルティ"),
    RewardLogTerm("reward_progress", "進捗ボーナス"),
    RewardLogTerm("torso_height", "torso height (m)"),
  )
)

BIPED_WALK_V1 = TelemetryContract(
  schema_id="biped_walk_v1",
  observation=ObservationSpec(
    obs_dim=BIPED_WALK_V1_OBS_DIM,
    slices=_BIPED_WALK_OBS_SLICES,
  ),
  reward_log=_BIPED_WALK_REWARD_LOG,
  include_legacy_gyro_alias=True,
)

BIPED_WALK_V1.validate()
