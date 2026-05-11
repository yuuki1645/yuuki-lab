/** robot-daemon の MPU6050 ストリーム（``imu/sample`` 等） */

export interface ImuDaemonStatusPayload {
  streaming?: boolean;
  rate_hz?: number;
  /** サーバが CSV ログを書けるか（``IMU_LOG_DISABLE`` 等） */
  csv_enabled?: boolean;
  /** 現在 CSV セッションが開いているか */
  csv_recording?: boolean;
  sensor?: {
    enabled?: boolean;
    mock_mode?: boolean;
    error?: string;
    error_code?: string;
    bus_id?: number;
    address?: number;
  };
}

export interface ImuDaemonSamplePayload {
  timestamp?: number;
  mock?: boolean;
  accel?: { x?: number; y?: number; z?: number };
  gyro?: { x?: number; y?: number; z?: number };
  angle?: { pitch?: number; roll?: number; yaw?: number };
}
