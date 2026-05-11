/** mujoco_rl_sim の ``RlTelemetryServer`` / ``RlTelemetryWrapper`` が送るペイロード（Socket.IO イベント名は従来どおり ``rl_telemetry/*``） */

export interface TrainingTelemetryHelloPayload {
  ok?: boolean;
  server_ts?: number;
}

export interface TrainingTelemetryResetPayload {
  wall_time: number;
  actuator_names: string[];
  obs_dim: number;
  obs_acc: number[];
  obs_gyro: number[];
  obs_prev_ctrl: number[];
  obs_prev_action_logical_deg?: number[];
  obs_prev_action_unit?: "logical_deg" | "rad" | "deg";
  obs_flat: number[];
  num_timesteps: number | null;
}

export interface TrainingTelemetryStepPayload {
  wall_time: number;
  episode_step: number;
  num_timesteps: number | null;
  actuator_names: string[];
  obs_acc: number[];
  obs_gyro: number[];
  obs_prev_ctrl: number[];
  obs_prev_action_logical_deg?: number[];
  obs_prev_action_unit?: "logical_deg" | "rad" | "deg";
  obs_flat: number[];
  action: number[];
  action_norm?: number[];
  action_norm_unit?: "normalized";
  action_logical_deg?: number[];
  action_unit?: "logical_deg" | "rad" | "deg";
  reward?: number;
  reward_total?: number;
  reward_action_penalty?: number;
  reward_fall_penalty?: number;
  torso_height?: number | null;
  step_wall_sleep_sec?: number | null;
  is_fallen?: boolean;
  terminated?: boolean;
  truncated?: boolean;
  obs_next_acc?: number[];
  obs_next_gyro?: number[];
  obs_next_prev_ctrl?: number[];
  obs_next_prev_action_logical_deg?: number[];
  obs_next_prev_action_unit?: "logical_deg" | "rad" | "deg";
  obs_next_flat?: number[];
}
