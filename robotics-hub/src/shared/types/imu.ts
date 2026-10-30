/** ヘッダーの IMU ウィンドウが受け取る Socket.IO `imu/*`。既定の送り元は MuJoCo。 */

export interface ImuStatusPayload {
  streaming?: boolean;
  rate_hz?: number;
  sensor?: {
    enabled?: boolean;
    error?: string;
    bus_id?: number;
    address?: number;
  };
}

export interface ImuSamplePayload {
  timestamp?: number;
  accel?: { x?: number; y?: number; z?: number };
  gyro?: { x?: number; y?: number; z?: number };
  angle?: { pitch?: number; roll?: number; yaw?: number };
  mock?: boolean;
}
