// ガイド画像のマッピング
export const GUIDE_MAP: Record<string, string> = {
  KNEE: "/guides/knee.JPG",
  HEEL: "/guides/heel.JPG",
  HEEL_ROLL: "/guides/heel.JPG",
  HIP1: "/guides/hip1.JPG",
  HIP2: "/guides/hip2.JPG",
};

// サーボ名 -> チャンネル番号のマッピング（servo_daemon/app.py と一致させる）
export const SERVO_NAME_TO_CH: Record<string, number> = {
  R_HIP1: 0,
  R_HIP2: 1,
  R_KNEE: 2,
  R_HEEL: 3,
  R_HEEL_ROLL: 4,
  L_HIP1: 8,
  L_HIP2: 9,
  L_KNEE: 10,
  L_HEEL: 11,
  L_HEEL_ROLL: 12,
};

// チャンネル番号 -> サーボ名のマッピング
export const CH_TO_SERVO_NAME: Record<number, string> = {
  0: "R_HIP1",
  1: "R_HIP2",
  2: "R_KNEE",
  3: "R_HEEL",
  4: "R_HEEL_ROLL",
  8: "L_HIP1",
  9: "L_HIP2",
  10: "L_KNEE",
  11: "L_HEEL",
  12: "L_HEEL_ROLL",
};

/** サーボ種別ごとの角度スライダー目盛り（必ず表示する切れの良い値） */
export const SERVO_TICK_VALUES: Record<string, number[]> = {
  HIP1: [90, 0, -30],
  HIP2: [0, 90, 120],
  KNEE: [0, 90, 120],
  HEEL: [-30, 0, 90],
  HEEL_ROLL: [-20, 0, 20],
};

// 全サーボチャンネル番号の配列
export const SERVO_CHANNELS: number[] = [0, 1, 2, 3, 4, 8, 9, 10, 11, 12];

/** robot-daemon のベース URL（サーボは REST、IMU は同じオリジンで Socket.IO） */
export const SERVO_DAEMON_URL =
  "http://" +
  (typeof window !== "undefined" ? window.location.hostname : "127.0.0.1") +
  ":5000";

/**
 * IMU 用 Socket.IO の接続先。
 * `VITE_IMU_SOCKET_URL` を指定すると mujoco_realtime_sim（:8787 等）へ向けられる。
 * 未指定時は `SERVO_DAEMON_URL`（robot-daemon :5000）。
 */
export function getImuSocketUrl(): string {
  const fromEnv = import.meta.env.VITE_IMU_SOCKET_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return SERVO_DAEMON_URL;
}

/**
 * mujoco-sim（Flask）のベース URL。
 * `VITE_MUJOCO_SIM_URL` があればそれを優先（ビルド時に埋め込み）。
 */
export function getMujocoSimUrl(): string {
  const fromEnv = import.meta.env.VITE_MUJOCO_SIM_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return (
    "http://" +
    (typeof window !== "undefined" ? window.location.hostname : "127.0.0.1") +
    ":8787"
  );
}

/** 物理角スライダー範囲（レッグチューナーなど） */
export const PHYSICAL_MIN = 0;
export const PHYSICAL_MAX = 180;

// デフォルトの角度（全サーボ共通）
export const DEFAULT_ANGLE = 90;

// 補間の更新間隔（ミリ秒）
export const INTERPOLATION_INTERVAL = 50;

// モーションの最大時間（ミリ秒）
export const MAX_MOTION_DURATION = 20000; // 20秒

// モーションのデフォルト時間（ミリ秒）
export const DEFAULT_MOTION_DURATION = 20000; // 20秒

// キーフレーム間の最小間隔（ミリ秒）- 重複を防ぐため
export const MIN_KEYFRAME_INTERVAL = 100; // 0.1秒

/** トラックタップ時にキーフレーム中心をタップ位置に合わせるためのオフセット（px）。キーフレームは left で配置するため、見た目の中心はこの値だけ右にある */
export const TIMELINE_KEYFRAME_CENTER_OFFSET_PX = 20;

// 論理角の範囲（全サーボ共通、必要に応じてservo_daemonから取得）
export const LOGICAL_ANGLE_MIN = -90;
export const LOGICAL_ANGLE_MAX = 90;
