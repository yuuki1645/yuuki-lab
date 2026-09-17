/**
 * 机上ラボの定数。
 *
 * 実機（右脚）は PC / Hub 側で 100〜170° に狭めているが、机上は 1 サーボ単体
 * なのでファームの可動域 40〜230°（校正スイープと同じ）をそのまま使う。
 */
export const BENCH_MIN_DEG = 40;
export const BENCH_MAX_DEG = 230;
export const BENCH_NEUTRAL_DEG = 135;

/** 指令バーの早送り先。端と中立を 1 タップで出す */
export const BENCH_PRESETS = [BENCH_MIN_DEG, 90, BENCH_NEUTRAL_DEG, 180, BENCH_MAX_DEG];

export const BENCH_BAR = {
  cmd: "#f7c948",
  raw: "#54a0ff",
  unwrap: "#1dd1a1",
  corr: "#3ee07f",
  err: "#ff4757",
  volt: "#ff6b6b",
  amp: "#4dabf7",
  watt: "#ff6b81",
};

export type BenchPlotKey = "cmd" | "raw" | "unwrap" | "corr" | "volt" | "amp" | "watt";

export const BENCH_PLOT_ITEMS: { key: BenchPlotKey; label: string; color: string }[] = [
  { key: "cmd", label: "指令", color: BENCH_BAR.cmd },
  { key: "raw", label: "生角", color: BENCH_BAR.raw },
  { key: "unwrap", label: "unwrap", color: BENCH_BAR.unwrap },
  { key: "corr", label: "補正", color: BENCH_BAR.corr },
  { key: "volt", label: "電圧", color: BENCH_BAR.volt },
  { key: "amp", label: "電流", color: BENCH_BAR.amp },
  { key: "watt", label: "電力", color: BENCH_BAR.watt },
];

export type BenchPlotVisibility = Record<BenchPlotKey, boolean>;

/** 既定は校正で見たい 4 本。電源は必要になったら足す */
export const BENCH_PLOT_DEFAULT: BenchPlotVisibility = {
  cmd: true,
  raw: true,
  unwrap: false,
  corr: true,
  volt: false,
  amp: true,
  watt: false,
};
