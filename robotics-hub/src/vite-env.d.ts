/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MUJOCO_SIM_URL?: string;
  /** IMU の Socket.IO 先。未指定時は `getMujocoSimUrl()`（既定 :8787） */
  readonly VITE_IMU_SOCKET_URL?: string;
  /** PPO 学習テレメトリ（`train_002_full_actuators`）。未指定時は同一ホスト :8791 */
  readonly VITE_RL_TELEMETRY_SOCKET_URL?: string;
}
