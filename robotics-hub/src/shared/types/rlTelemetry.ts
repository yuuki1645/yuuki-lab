/** mujoco_rl_sim の ``RlTelemetryServer`` / ``RlTelemetryWrapper`` が送るペイロード */

export interface RlTelemetryHelloPayload {
  ok?: boolean;
  server_ts?: number;
}

export interface RlTelemetryResetPayload {
  wall_time: number;
  actuator_names: string[];
  obs_dim: number;
  obs_acc: number[];
  obs_gyro: number[];
  obs_prev_ctrl: number[];
  obs_flat: number[];
  num_timesteps: number | null;
}

export interface RlTelemetryStepPayload {
  wall_time: number;
  episode_step: number;
  num_timesteps: number | null;
  actuator_names: string[];
  obs_acc: number[];
  obs_gyro: number[];
  obs_prev_ctrl: number[];
  obs_flat: number[];
  action: number[];
}
