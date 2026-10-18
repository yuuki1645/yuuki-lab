/** 右脚 5 軸。ATOM 論理関節 0〜4 は servo_daemon の R_HIP1…R_HEEL_ROLL と同じ順。 */

/** 実験中のライブ PWM 上限。ファームは 40〜230 のまま、PC / Hub だけ狭める */
export const SERVO_MIN_DEG = 100;
export const SERVO_MAX_DEG = 170;
export const SERVO_NEUTRAL_DEG = 135;

export const LEG_BAR = {
  cmd: "#f7c948",
  corr: "#3ee07f",
  err: "#ff4757",
  volt: "#ff6b6b",
  amp: "#4dabf7",
};

/** 右脚 5 軸グラフで共通トグルする系列 */
export type LegPlotKey = "cmd" | "corr" | "volt" | "amp";

export type LegPlotVisibility = Record<LegPlotKey, boolean>;

export const LEG_PLOT_ITEMS: { key: LegPlotKey; label: string; color: string }[] = [
  { key: "cmd", label: "指令", color: LEG_BAR.cmd },
  { key: "corr", label: "補正", color: LEG_BAR.corr },
  { key: "volt", label: "電圧", color: LEG_BAR.volt },
  { key: "amp", label: "電流", color: LEG_BAR.amp },
];

export const LEG_PLOT_DEFAULT: LegPlotVisibility = {
  cmd: true,
  corr: true,
  volt: true,
  amp: true,
};

export type RightLegJointId =
  | "hipRoll"
  | "hipPitch"
  | "kneePitch"
  | "anklePitch"
  | "ankleRoll";

export type LegSide = "left" | "right";

export type RightLegJoint = {
  /** 左右で重ならない id。選択ハイライト用 */
  id: string;
  /** 右脚は実機ファームの論理関節 0〜4。左脚は 5〜9（Isaac の橋だけが使う） */
  ch: number;
  label: string;
  short: string;
  side: LegSide;
};

/** 上から股ロール、股ピッチ、ひざ、かかとピッチ、かかとロール。左右で同じ順。 */
export const LEG_ROWS: { id: RightLegJointId; label: string; short: string }[] = [
  { id: "hipRoll", label: "股関節ロール", short: "HIP ROLL" },
  { id: "hipPitch", label: "股関節ピッチ", short: "HIP PITCH" },
  { id: "kneePitch", label: "ひざピッチ", short: "KNEE" },
  { id: "anklePitch", label: "かかとピッチ", short: "ANKLE" },
  { id: "ankleRoll", label: "かかとロール", short: "FOOT ROLL" },
];

/** 右脚 ch 0〜4、左脚 ch 5〜9。 */
export function legChannel(side: LegSide, row: number): number {
  return side === "right" ? row : 5 + row;
}

export function legJoint(side: LegSide, row: number): RightLegJoint {
  const def = LEG_ROWS[row];
  if (!def) {
    throw new Error(`脚の行番号が範囲外です: ${row}`);
  }
  const sideLabel = side === "left" ? "左" : "右";
  return {
    id: `${side}-${def.id}`,
    ch: legChannel(side, row),
    label: `${sideLabel} ${def.label}`,
    short: def.short,
    side,
  };
}

/** 実機 PWM ボタン用。右脚だけ、従来の ch 0〜4。 */
export const RIGHT_LEG_JOINTS: RightLegJoint[] = LEG_ROWS.map((_, row) => legJoint("right", row));
