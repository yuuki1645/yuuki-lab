/** 右脚 5 軸。ATOM 論理関節 0〜4 は servo_daemon の R_HIP1…R_HEEL_ROLL と同じ順。 */

export const SERVO_MIN_DEG = 40;
export const SERVO_MAX_DEG = 230;
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

export type RightLegJoint = {
  id: RightLegJointId;
  /** ATOM / lab_debug の論理関節番号 */
  ch: number;
  label: string;
  short: string;
};

export const RIGHT_LEG_JOINTS: RightLegJoint[] = [
  { id: "hipRoll", ch: 0, label: "股関節ロール", short: "HIP ROLL" },
  { id: "hipPitch", ch: 1, label: "股関節ピッチ", short: "HIP PITCH" },
  { id: "kneePitch", ch: 2, label: "ひざピッチ", short: "KNEE" },
  { id: "anklePitch", ch: 3, label: "かかとピッチ", short: "ANKLE" },
  { id: "ankleRoll", ch: 4, label: "かかとロール", short: "FOOT ROLL" },
];
