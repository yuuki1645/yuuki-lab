// ガイド画像のマッピング
export const GUIDE_MAP: Record<string, string> = {
  KNEE: "/guides/knee.JPG",
  HEEL: "/guides/heel.JPG",
  HEEL_ROLL: "/guides/heel.JPG",
  HIP1: "/guides/hip1.JPG",
  HIP2: "/guides/hip2.JPG",
};

/**
 * モーションエディタと MuJoCo 連携が使うサーボ名。
 * 実機（M5）の論理軸 0〜9 とは番号が違う。左脚は 8 から始まる。
 */
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

/** モーションエディタが走査するチャンネル。実機の論理軸 0〜9 ではない。 */
export const SERVO_CHANNELS: number[] = [0, 1, 2, 3, 4, 8, 9, 10, 11, 12];

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

/**
 * ``mujoco_test_009.py`` が立てるビュワー補助 API（Flask）のベース URL。
 * ``VITE_MUJOCO_VIEWER_AUX_URL`` があれば優先（ビルド時に埋め込み）。
 */
export function getMujocoViewerAuxUrl(): string {
  const fromEnv = import.meta.env.VITE_MUJOCO_VIEWER_AUX_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return (
    "http://" +
    (typeof window !== "undefined" ? window.location.hostname : "127.0.0.1") +
    ":8788"
  );
}

/**
 * ヘッダーの IMU ウィンドウが使う Socket.IO。
 * `VITE_IMU_SOCKET_URL` があればそれを優先する。
 * 未指定時は MuJoCo シムと同じホスト（既定 :8787）。
 */
export function getImuSocketUrl(): string {
  const fromEnv = import.meta.env.VITE_IMU_SOCKET_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return getMujocoSimUrl();
}

/**
 * 学習プロセスのテレメトリ用 Socket.IO（exp_019 ``train`` の ``--telemetry-port``、既定 8791）。
 * 旧名 ``VITE_RL_TELEMETRY_SOCKET_URL`` も未設定時のみフォールバックとして読む。
 */
export function getTrainingTelemetrySocketUrl(): string {
  const primary = import.meta.env.VITE_TELEMETRY_SOCKET_URL;
  if (typeof primary === "string" && primary.length > 0) {
    return primary.replace(/\/$/, "");
  }
  const legacy = import.meta.env.VITE_RL_TELEMETRY_SOCKET_URL;
  if (typeof legacy === "string" && legacy.length > 0) {
    return legacy.replace(/\/$/, "");
  }
  return (
    "http://" +
    (typeof window !== "undefined" ? window.location.hostname : "127.0.0.1") +
    ":8791"
  );
}

/**
 * Isaac Lab RSL-RL の TensorBoard ログ API（``server/isaac_rl_log_server.py``、既定 :8792）。
 * ``VITE_ISAAC_RL_LOG_API_URL`` があれば優先。
 */
export function getIsaacRlLogApiUrl(): string {
  const fromEnv = import.meta.env.VITE_ISAAC_RL_LOG_API_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return (
    "http://" +
    (typeof window !== "undefined" ? window.location.hostname : "127.0.0.1") +
    ":8792"
  );
}

/**
 * ATOM / lab_debug.py の iPad 中継 Socket.IO（既定 :8794）。
 * iPad は Windows PC の LAN IP で Hub を開く。
 * ``VITE_M5_TELEMETRY_SOCKET_URL`` があれば優先。
 */
export function getM5TelemetrySocketUrl(): string {
  const fromEnv = import.meta.env.VITE_M5_TELEMETRY_SOCKET_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return (
    "http://" +
    (typeof window !== "undefined" ? window.location.hostname : "127.0.0.1") +
    ":8794"
  );
}

/**
 * Isaac 再生の橋（``robot_description/isaac_hub_bridge.py``、既定 :8795）。
 * 実機の :8794 が無いとき、実機テレメトリ画面がこちらへ接続する。
 * ``VITE_ISAAC_HUB_SOCKET_URL`` があれば優先。
 */
export function getIsaacHubSocketUrl(): string {
  const fromEnv = import.meta.env.VITE_ISAAC_HUB_SOCKET_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return (
    "http://" +
    (typeof window !== "undefined" ? window.location.hostname : "127.0.0.1") +
    ":8795"
  );
}

/**
 * 実機カメラ／Recorder MJPEG（``robot-recorder``、既定 :8766）のベース URL。
 * ``VITE_CAPTURE_REALTIME_URL`` があれば優先（ビルド時に埋め込み）。
 */
export function getCaptureRealtimeBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_CAPTURE_REALTIME_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return (
    "http://" +
    (typeof window !== "undefined" ? window.location.hostname : "127.0.0.1") +
    ":8766"
  );
}

/** MJPEG ストリーム本体（``/stream.mjpg``）。 */
export function getCaptureRealtimeStreamUrl(): string {
  return getCaptureRealtimeBaseUrl() + "/stream.mjpg";
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

/** モーションエディタの論理角スライダー範囲（度）。実機の 135° 中立とは別。 */
export const LOGICAL_ANGLE_MIN = -90;
export const LOGICAL_ANGLE_MAX = 90;
