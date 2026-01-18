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

// 物理角の範囲（全サーボ共通）
export const PHYSICAL_MIN = 0;
export const PHYSICAL_MAX = 180;

// servo_daemonのURL
export const SERVO_DAEMON_URL = "http://192.168.100.24:5000";