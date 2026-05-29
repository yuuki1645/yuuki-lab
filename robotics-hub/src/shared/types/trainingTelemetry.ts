/** mujoco-sim の ``HubTelemetrySocketIoServer`` + ``biped_ppo`` ペイロード（``rl_telemetry/*``） */

export const BIPED_PPO_TELEMETRY_SCHEMA = "biped_ppo_v1";

export interface TrainingTelemetryHelloPayload {
  ok?: boolean;
  server_ts?: number;
}

/** 旧 train_002 / 6 次元 IMU 先頭観測（後方互換） */
export interface TrainingTelemetryLegacyImuFields {
  obs_acc?: number[];
  obs_acc_unit?: "g" | "m/s2";
  obs_gyro?: number[];
  obs_prev_ctrl?: number[];
  obs_prev_action_logical_deg?: number[];
  obs_prev_action_unit?: "logical_deg" | "rad" | "deg" | "normalized";
}

/** exp_019 ``biped_ppo_v1`` 観測スライス */
export interface TrainingTelemetryBipedObsFields {
  schema?: string;
  exp_name?: string;
  obs_dx?: number;
  /** rad/s（MuJoCo ``imu_gyro`` 生値） */
  obs_imu_gyro?: number[];
  obs_imu_zaxis?: number[];
  obs_imu_z_norm?: number;
  obs_left_foot_contact?: number;
  obs_right_foot_contact?: number;
  obs_left_foot_dx?: number;
  obs_right_foot_dx?: number;
  obs_joint_q_norm?: number[];
  obs_joint_qvel_norm?: number[];
  obs_prev_action_norm?: number[];
  joint_q_logical_deg?: number[];
}

export interface TrainingTelemetryResetPayload
  extends TrainingTelemetryLegacyImuFields,
    TrainingTelemetryBipedObsFields {
  wall_time: number;
  actuator_names: string[];
  obs_dim: number;
  obs_flat: number[];
  num_timesteps: number | null;
}

export interface TrainingTelemetryStepPayload
  extends TrainingTelemetryLegacyImuFields,
    TrainingTelemetryBipedObsFields {
  wall_time: number;
  episode_step: number;
  num_timesteps: number | null;
  actuator_names: string[];
  obs_flat: number[];
  action: number[];
  action_norm?: number[];
  action_norm_unit?: "normalized";
  action_logical_deg?: number[];
  action_unit?: "logical_deg" | "rad" | "deg";
  reward?: number;
  reward_total?: number;
  /** exp_019: トルク・電力コスト系 */
  reward_effort_penalty?: number;
  /** 旧名互換 */
  reward_action_penalty?: number;
  reward_fall_penalty?: number;
  torso_height?: number | null;
  step_wall_sleep_sec?: number | null;
  is_fallen?: boolean;
  terminated?: boolean;
  truncated?: boolean;
  obs_next_acc?: number[];
  obs_next_acc_unit?: "g" | "m/s2";
  obs_next_gyro?: number[];
  obs_next_imu_gyro?: number[];
  obs_next_imu_zaxis?: number[];
  obs_next_imu_z_norm?: number;
  obs_next_prev_ctrl?: number[];
  obs_next_prev_action_logical_deg?: number[];
  obs_next_prev_action_norm?: number[];
  obs_next_flat?: number[];
}

export function isBipedPpoTelemetry(
  payload: { schema?: string; exp_name?: string } | null | undefined
): boolean {
  if (!payload) return false;
  if (payload.schema === BIPED_PPO_TELEMETRY_SCHEMA) return true;
  if (typeof payload.exp_name === "string") {
    return (
      payload.exp_name.includes("exp_019") || payload.exp_name.includes("exp_020")
    );
  }
  return false;
}
