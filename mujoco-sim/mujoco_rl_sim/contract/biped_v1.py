"""biped_ppo_v1: exp_019 / exp_020 と同一の 42 次元観測・テレメトリ契約。"""

from __future__ import annotations

from mujoco_rl_sim.contract.spec import (
  ObservationSlice,
  ObservationSpec,
  RewardLogTerm,
  RewardLogSpec,
  TelemetryContract,
)

BIPED_PPO_V1_OBS_DIM = 42

_BIPED_OBS_SLICES: tuple[ObservationSlice, ...] = (
  ObservationSlice("obs_dx", 0, 1, "scalar", "IMU +X 移動量（正規化）"),
  ObservationSlice("obs_imu_gyro", 1, 4, "vector", "IMU 角速度 rad/s（正規化）"),
  ObservationSlice("obs_imu_zaxis", 4, 7, "vector", "IMU 上向き単位ベクトル"),
  ObservationSlice("obs_imu_z_norm", 7, 8, "scalar", "IMU 高さ（正規化）"),
  ObservationSlice("obs_left_foot_contact", 8, 9, "scalar", "左足接地 ±1"),
  ObservationSlice("obs_right_foot_contact", 9, 10, "scalar", "右足接地 ±1"),
  ObservationSlice("obs_left_foot_dx", 10, 11, "scalar", "左足 +X 移動量（正規化）"),
  ObservationSlice("obs_right_foot_dx", 11, 12, "scalar", "右足 +X 移動量（正規化）"),
  ObservationSlice("obs_joint_q_norm", 12, 22, "vector", "関節角 q（正規化）×10"),
  ObservationSlice("obs_joint_qvel_norm", 22, 32, "vector", "関節角速度（正規化）×10"),
  ObservationSlice("obs_prev_action_norm", 32, 42, "vector", "直前 action [-1,1]×10"),
)

_BIPED_REWARD_LOG = RewardLogSpec(
  terms=(
    RewardLogTerm("reward_total", "報酬 total"),
    RewardLogTerm("reward_forward", "前進合計"),
    RewardLogTerm("reward_forward_imu", "IMU 前進"),
    RewardLogTerm("reward_forward_foot", "足元前進"),
    RewardLogTerm("reward_shaping", "shaping 合計"),
    RewardLogTerm("reward_effort_penalty", "effort ペナルティ"),
    RewardLogTerm("reward_fall_penalty", "転倒・姿勢ペナルティ"),
    RewardLogTerm("reward_flight_duration_penalty", "遊脚継続ペナルティ"),
    RewardLogTerm("reward_progress", "進捗ボーナス"),
    RewardLogTerm("torso_height", "torso height (m)"),
  )
)

BIPED_PPO_V1 = TelemetryContract(
  schema_id="biped_ppo_v1",
  observation=ObservationSpec(
    obs_dim=BIPED_PPO_V1_OBS_DIM,
    slices=_BIPED_OBS_SLICES,
  ),
  reward_log=_BIPED_REWARD_LOG,
  include_legacy_gyro_alias=True,
)

BIPED_PPO_V1.validate()
