/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MUJOCO_SIM_URL?: string;
  /** ``mujoco_test_009.py`` のビュワー補助 API（既定は同一ホスト :8788） */
  readonly VITE_MUJOCO_VIEWER_AUX_URL?: string;
  /** IMU の Socket.IO 先。未指定時は `getMujocoSimUrl()`（既定 :8787） */
  readonly VITE_IMU_SOCKET_URL?: string;
  /** 学習テレメトリ用 Socket.IO（exp_019 `train`）。未設定時は旧名 `VITE_RL_TELEMETRY_SOCKET_URL` のあと同一ホスト :8791 */
  readonly VITE_TELEMETRY_SOCKET_URL?: string;
  /** @deprecated `VITE_TELEMETRY_SOCKET_URL` を使用してください */
  readonly VITE_RL_TELEMETRY_SOCKET_URL?: string;
  /** テレメトリページの実機 IMU（robot-daemon）Socket.IO（未設定時は hostname:5000） */
  readonly VITE_TELEMETRY_IMU_SOCKET_URL?: string;
}
