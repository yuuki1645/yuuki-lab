// ガイド画像のマッピング
export const GUIDE_MAP = {
  "KNEE": "/guides/knee.JPG",
  "HEEL": "/guides/heel.JPG",
  "HIP1": "/guides/hip1.JPG",
  "HIP2": "/guides/hip2.JPG",
};

// サーボ名 -> チャンネル番号のマッピング（servo_daemon/app.py と一致させる）
export const SERVO_NAME_TO_CH = {
  "R_HIP1": 0,
  "R_HIP2": 1,
  "R_KNEE": 2,
  "R_HEEL": 3,
  "L_HIP1": 8,
  "L_HIP2": 9,
  "L_KNEE": 10,
  "L_HEEL": 11,
};

// チャンネル番号 -> サーボ名のマッピング
export const CH_TO_SERVO_NAME = {
  0: "R_HIP1",
  1: "R_HIP2",
  2: "R_KNEE",
  3: "R_HEEL",
  8: "L_HIP1",
  9: "L_HIP2",
  10: "L_KNEE",
  11: "L_HEEL",
};

// 全サーボチャンネル番号の配列
export const SERVO_CHANNELS = [0, 1, 2, 3, 8, 9, 10, 11];

// servo_daemonのURL
export const SERVO_DAEMON_URL = "http://192.168.100.24:5000";
// export const SERVO_DAEMON_URL = "http://127.0.0.1:5000";

// デフォルトの角度（全サーボ共通）
export const DEFAULT_ANGLE = 90;

// 補間の更新間隔（ミリ秒）
export const INTERPOLATION_INTERVAL = 50;

// モーションの最大時間（ミリ秒）
export const MAX_MOTION_DURATION = 20000; // 20秒

// モーションのデフォルト時間（ミリ秒）
export const DEFAULT_MOTION_DURATION = 20000; // 5秒

// キーフレーム間の最小間隔（ミリ秒）- 重複を防ぐため
export const MIN_KEYFRAME_INTERVAL = 100; // 0.1秒

// 論理角の範囲（全サーボ共通、必要に応じてservo_daemonから取得）
export const LOGICAL_ANGLE_MIN = -90;
export const LOGICAL_ANGLE_MAX = 90;