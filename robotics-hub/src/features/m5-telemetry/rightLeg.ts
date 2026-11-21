/** 右脚 5 軸。順は股ロール、股ピッチ、ひざ、かかとピッチ、かかとロール。 */

/** 実験中のライブ PWM 上限。ファームは 40〜230 のまま、PC / Hub だけ狭める */
export const SERVO_MIN_DEG = 100;
export const SERVO_MAX_DEG = 170;
export const SERVO_NEUTRAL_DEG = 135;
/** SM105BL の真下。RDS の 135° とは別の基準。 */
export const SM105_NEUTRAL_DEG = 0;

export const LEG_BAR = {
  cmd: "#f7c948",
  raw: "#54a0ff",
  corr: "#3ee07f",
  err: "#ff4757",
  volt: "#ff6b6b",
  amp: "#4dabf7",
};

/** 関節カード左のバー。生角は AS5600 の 0〜360° */
export type LegBarKey = "cmd" | "raw" | "err" | "corr";

export type LegBarVisibility = Record<LegBarKey, boolean>;

export const LEG_BAR_ITEMS: { key: LegBarKey; label: string; color: string }[] = [
  { key: "cmd", label: "指令", color: LEG_BAR.cmd },
  { key: "raw", label: "生角", color: LEG_BAR.raw },
  { key: "err", label: "ズレ", color: LEG_BAR.err },
  { key: "corr", label: "補正", color: LEG_BAR.corr },
];

export const LEG_BAR_DEFAULT: LegBarVisibility = {
  cmd: true,
  raw: true,
  err: true,
  corr: true,
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

/**
 * ひざピッチとかかとピッチは SM105BL（RS485）。
 * 右ひざ 1、右かかとピッチ 2、左ひざ 3、左かかとピッチ 4。
 * 論理関節は右が 0〜4、左が 5〜9。ひざは 2、かかとピッチは 3。
 */
export function isSm105Channel(ch: number): boolean {
  return sm105ServoId(ch) != null;
}

export function sm105ServoId(ch: number): number | null {
  switch (ch) {
    case 2:
      return 1;
    case 3:
      return 2;
    case 7:
      return 3;
    case 8:
      return 4;
    default:
      return null;
  }
}

/**
 * バーと右グラフの角度窓。届いた数値は範囲外でもそのまま表示する。
 * ひざは後ろへ折れる向きが正。かかとはつま先を上げる向きが正。真下は 0°。
 */
export function sm105AngleWindow(ch: number): { min: number; max: number } | null {
  if (ch === 2 || ch === 7) {
    return { min: -30, max: 150 };
  }
  if (ch === 3 || ch === 8) {
    return { min: -60, max: 60 };
  }
  return null;
}
