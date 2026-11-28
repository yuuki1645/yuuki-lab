/**
 * 実験画面で関節角を読むときの単位。
 *
 * 記録と方策の中は、直立を 0 としたラジアンのまま。
 * 画面に出すときだけ、その関節の真下を足して度にする。
 * RDS51150 の真下は 135°、SM105BL の真下は 0°。
 * 頭打ちのような差には真下を足さない。
 */

import type { LabTakeContext, LabWindow, LabWindowSeries } from "../types";
import { formatNumber } from "./plotMath";

/** 絶対角（真下を足す）か、差（足さない）か。 */
export type AngleDisplay = "screen" | "delta";

const RAD_TO_DEG = 180 / Math.PI;
const DEG_TO_RAD = Math.PI / 180;

/**
 * 契約が直立を書いていないときの並び。
 * 右 0–4、左 5–9。ひざとかかとピッチだけ SM105BL で 0°。
 */
const DEFAULT_UPRIGHT_DEG = [135, 135, 0, 0, 135, 135, 135, 0, 0, 135];

/** このチャンネルが、画面で度に直すラジアンならその種類。すでに度の欄は null。 */
const RADIAN_FIELDS: Record<string, AngleDisplay> = {
  obs: "screen",
  action_rad: "screen",
  cmd_rad: "screen",
  corr_rad: "screen",
  clip: "delta",
};

export function angleDisplayOf(channel: string): AngleDisplay | null {
  const field = channel.split(".")[1] ?? "";
  return RADIAN_FIELDS[field] ?? null;
}

/** 論理軸の真下。契約の upright_deg、無ければサーボ名、それも無ければ既定の並び。 */
export function uprightDegOf(joint: number, context: LabTakeContext | null | undefined): number {
  const listed = context?.upright_deg?.[joint];
  if (typeof listed === "number" && Number.isFinite(listed)) return listed;
  const servo = context?.servos?.[joint] ?? "";
  if (servo === "SM105BL") return 0;
  if (servo === "RDS51150") return 135;
  return DEFAULT_UPRIGHT_DEG[joint] ?? 135;
}

/** 直立 0 のラジアンを、描画用の度へ。差のときは uprightDeg を無視する。 */
export function radiansToDisplayDeg(rad: number, display: AngleDisplay, uprightDeg: number): number {
  const degrees = rad * RAD_TO_DEG;
  return display === "screen" ? uprightDeg + degrees : degrees;
}

/** 描画用の度から、括弧に添える元のラジアンへ戻す。 */
export function displayDegToRadians(deg: number, display: AngleDisplay, uprightDeg: number): number {
  const fromUpright = display === "screen" ? deg - uprightDeg : deg;
  return fromUpright * DEG_TO_RAD;
}

/** 「30.0度 (0.524 rad)」。度が無ければダッシュ。ラジアンが無ければ度だけ。 */
export function formatAnglePair(deg: number | null | undefined, rad: number | null | undefined): string {
  if (deg == null || !Number.isFinite(deg)) return "\u2014";
  const head = `${formatNumber(deg, 1)}\u5ea6`;
  if (rad == null || !Number.isFinite(rad)) return head;
  return `${head} (${formatNumber(rad, 3)} rad)`;
}

/** バケットの最小と最大。度を主にして、ラジアンは括弧にまとめる。 */
export function formatAngleSpan(
  minDeg: number,
  maxDeg: number,
  minRad: number,
  maxRad: number
): string {
  return `${formatNumber(minDeg, 1)}\u2013${formatNumber(maxDeg, 1)}\u5ea6 (${formatNumber(minRad, 3)}\u2013${formatNumber(maxRad, 3)} rad)`;
}

function mapValues(
  values: Array<number | null> | undefined,
  convert: (rad: number) => number
): Array<number | null> | undefined {
  if (!values) return values;
  return values.map((value) => (value == null || !Number.isFinite(value) ? value : convert(value)));
}

function mapSeries(series: LabWindowSeries, convert: (rad: number) => number): LabWindowSeries {
  return {
    v: mapValues(series.v, convert),
    min: mapValues(series.min, convert),
    max: mapValues(series.max, convert),
    mean: mapValues(series.mean, convert),
  };
}

/**
 * 指定したチャンネルだけを度へ写した窓。
 * 元の窓は変えない。重力や角速度など、渡していない欄はそのまま。
 */
export function presentWindow(
  data: LabWindow,
  display: AngleDisplay,
  uprightDeg: number,
  keys: readonly string[]
): LabWindow {
  const convert = (rad: number) => radiansToDisplayDeg(rad, display, uprightDeg);
  const series = { ...data.series };
  for (const key of keys) {
    const item = series[key];
    if (item) series[key] = mapSeries(item, convert);
  }
  return { ...data, series };
}
