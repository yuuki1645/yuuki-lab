/** lab_debug.py の Socket.IO 中継（:8794）と揃える型。 */

export const M5_JOINTS = 8;
/** 電源監視枠。論理関節と同じ 8。未割当は欠測 */
export const M5_INA_CHS = 8;
/** 既定プロファイルで INA を付ける軸数（PaHub 0x71 CH0/CH1） */
export const M5_INA_DEFAULT_ASSIGNED = 2;
export const M5_PANEL_COUNT = 2;

/** 関節ごとの電源グラフ色 */
export const M5_INA_PLOT_COLORS = [
  "#feca57",
  "#e67e22",
  "#00d2d3",
  "#5f27cd",
  "#10ac84",
  "#ee5253",
  "#54a0ff",
  "#c8d6e5",
];

export type M5Status = {
  ipad_clients: number;
  pc_locked: boolean;
  connected: boolean;
  port: string;
  name: string;
  hello: string;
  mode: string;
  bridge_port: number;
};

export type M5Control = {
  out: boolean[];
  cmd: number[];
  rand: boolean[];
  amp_limit: number;
  auto_scan: boolean;
  rand_min: number;
  rand_max: number;
  rand_hold_min: number;
  rand_hold_max: number;
  rand_jump: number;
};

export type M5Frame = {
  t: number;
  seq: number;
  period_us: number;
  loop_us: number;
  sense_us: number;
  jitter_us: number;
  overrun: boolean;
  cmd: Array<number | null>;
  raw: Array<number | null>;
  unwrap: Array<number | null>;
  corr: Array<number | null>;
  as_ok: boolean[];
  mag: number[];
  agc: number[];
  volt: Array<number | null>;
  amp: Array<number | null>;
  watt: Array<number | null>;
  ina_ok: boolean[];
  i2c_err: number;
  servo_ok: boolean;
  mode: string;
  out_mask: number;
  /** 右足 DF9-40（ATOM S3 Lite スレーブ）。未割当・欠測なら ok=false */
  foot?: M5FootSample | null;
};

export type M5ScanNode = {
  hub: string;
  ch: number;
  addr: string;
  kind: string;
  mag: number;
  agc: number;
};

export type M5Scan = {
  nodes: M5ScanNode[];
};

/** 右足スレーブ 1 隅（Hub の PressureCornerSample と同じ形） */
export type M5FootCorner = {
  force_kg: number;
  force_pct?: number;
  voltage_v?: number;
  rs_ohm?: number;
};

export type M5FootCorners = {
  top_left: M5FootCorner | null;
  top_right: M5FootCorner | null;
  bottom_right: M5FootCorner | null;
  bottom_left: M5FootCorner | null;
};

export type M5FootSample = {
  ok: boolean;
  seq: number;
  mask: number;
  force_kg: number;
  corners: M5FootCorners;
};

export type M5FootRoute = {
  hub: number;
  ch: number;
  addr: number;
};

export type M5Route = {
  enc_hub: number;
  enc_ch: number;
  enc_addr: number;
  act_hub: number;
  act_ch: number;
  act_addr: number;
  servo_ch: number;
  ina_hub: number;
  ina_ch: number;
  ina_addr: number;
};

export type M5Profile = {
  routes: M5Route[];
  ina_options: string[];
  foot?: M5FootRoute;
  foot_options?: string[];
};

export type M5Cal = {
  status: string;
  map_ch: number;
  map_count: number;
};

export type M5Hello = {
  status?: M5Status;
  control?: M5Control;
  frame?: M5Frame | null;
  scan?: M5Scan;
  profile?: M5Profile;
  events?: string[];
  cal?: M5Cal;
  record?: M5RecordStatus;
};

/** lab_debug 本記録のライブ状態（Socket.IO m5/record） */
export type M5RecordStatus = {
  recording: boolean;
  id: string | null;
  name: string;
  notes?: string;
  started_at?: string | null;
  sample_count: number;
  elapsed_sec: number;
  error?: string;
};

/** PC ディスク上の 1 本（一覧・詳細） */
export type M5RecordMeta = {
  format_id: string;
  id: string;
  name: string;
  notes: string;
  started_at: string;
  ended_at: string | null;
  started_unix: number;
  ended_unix: number | null;
  duration_sec: number | null;
  sample_count: number;
  hz: number;
  port: string;
  atom_name: string;
  mode: string;
  hello: string;
  recording: boolean;
  bytes?: number;
  /** robot-recorder の take。映像が無い記録は null */
  camera?: M5RecordCamera | null;
};

/** M5 本記録と実機カメラ take の結び */
export type M5RecordCamera = {
  experiment_id?: string;
  take_id?: string;
  video_t0_unix?: number | null;
  mp4_url?: string | null;
  hls_url?: string | null;
  ok?: boolean;
  error?: string;
};

export type M5RecordDetail = M5RecordMeta & {
  profile?: M5Profile;
  scan?: M5Scan;
  control?: M5Control;
};

/** グラフ用のリングバッファ 1 点 */
export function frameToHistory(frame: M5Frame): M5HistoryPoint {
  return {
    t: frame.t,
    cmd: frame.cmd,
    raw: frame.raw,
    unwrap: frame.unwrap,
    corr: frame.corr,
    volt: frame.volt,
    amp: frame.amp,
    watt: frame.watt,
    period_ms: frame.period_us / 1000,
    loop_ms: frame.loop_us / 1000,
    sense_ms: frame.sense_us / 1000,
  };
}

/** 再生中のスライダ／PWM 表示を、そのフレームの指令に合わせる */
export function controlFromFrame(frame: M5Frame, base?: M5Control | null): M5Control {
  const cmd = frame.cmd.map((v) => (typeof v === "number" && Number.isFinite(v) ? v : 135));
  const out = Array.from({ length: M5_JOINTS }, (_, i) => ((frame.out_mask >> i) & 1) === 1);
  return {
    out,
    cmd,
    rand: base?.rand ?? Array.from({ length: M5_JOINTS }, () => false),
    amp_limit: base?.amp_limit ?? 8,
    auto_scan: false,
    rand_min: base?.rand_min ?? 40,
    rand_max: base?.rand_max ?? 230,
    rand_hold_min: base?.rand_hold_min ?? 0.7,
    rand_hold_max: base?.rand_hold_max ?? 1.4,
    rand_jump: base?.rand_jump ?? 25,
  };
}

/** グラフ用のリングバッファ 1 点 */
export type M5HistoryPoint = {
  t: number;
  cmd: Array<number | null>;
  raw: Array<number | null>;
  unwrap: Array<number | null>;
  corr: Array<number | null>;
  volt: Array<number | null>;
  amp: Array<number | null>;
  watt: Array<number | null>;
  period_ms: number;
  loop_ms: number;
  sense_ms: number;
};

export type M5Cmd = Record<string, unknown> & { op: string };

export const MAG_LABEL: Record<number, string> = {
  0: "OK",
  1: "磁石なし",
  2: "弱い",
  3: "強い",
  4: "I2C",
  255: "—",
};

export const M5_COLORS = {
  cmd: "#ff9f43",
  raw: "#54a0ff",
  unwrap: "#1dd1a1",
  corr: "#ff4757",
  volt: "#feca57",
  amp: "#00d2d3",
  watt: "#ff6b81",
  period: "#f5f6fa",
  loop: "#ff9f43",
  sense: "#54a0ff",
};

/** トポロジのユニット種類。PC の lab_debug 木と同じ色分け */
export const KIND_META: Record<string, { label: string; color: string }> = {
  pahub: { label: "PaHub", color: "#a29bfe" },
  servo: { label: "サーボ", color: "#ff9f43" },
  as5600: { label: "AS5600", color: "#54a0ff" },
  ina226: { label: "INA226", color: "#feca57" },
  foot: { label: "足圧", color: "#ff6b9d" },
};

export function kindMeta(kind: string): { label: string; color: string } {
  return KIND_META[kind] ?? { label: kind, color: "#8b9bb0" };
}
