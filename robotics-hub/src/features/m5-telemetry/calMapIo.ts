/**
 * 校正マップ JSON（as5600-servo-map-v1）。
 * atom-rt/tools/lib/cal_map_io.py と同じ形式。
 */
import type { M5CalPoint } from "./types";

export const CAL_MAP_FORMAT = "as5600-servo-map-v1";
/** ファーム CalMap / kMapLen と同じ上限 */
export const CAL_MAP_MAX_POINTS = 191;

export type CalMapFile = {
  channel: number;
  points: M5CalPoint[];
};

type CalMapJson = {
  format?: unknown;
  channel?: unknown;
  points?: unknown;
};

/** Python save_map と同じ本文（末尾改行付き） */
export function serializeCalMap(channel: number, points: M5CalPoint[]): string {
  const data = {
    format: CAL_MAP_FORMAT,
    channel: Math.trunc(channel),
    count: points.length,
    points: points.map((p) => ({ as5600: Number(p.as5600), servo: Number(p.servo) })),
  };
  return `${JSON.stringify(data, null, 2)}\n`;
}

function asPoint(raw: unknown): M5CalPoint | null {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const o = raw as { as5600?: unknown; servo?: unknown };
    const x = Number(o.as5600);
    const y = Number(o.servo);
    if (Number.isFinite(x) && Number.isFinite(y)) return { as5600: x, servo: y };
    return null;
  }
  if (Array.isArray(raw) && raw.length >= 2) {
    const x = Number(raw[0]);
    const y = Number(raw[1]);
    if (Number.isFinite(x) && Number.isFinite(y)) return { as5600: x, servo: y };
  }
  return null;
}

/** load_map 相当。形式が違うと throw */
export function parseCalMap(text: string): CalMapFile {
  const data = JSON.parse(text) as CalMapJson;
  if (!data || typeof data !== "object" || data.format !== CAL_MAP_FORMAT) {
    throw new Error("未対応のマップファイルです");
  }
  const channel = Number(data.channel ?? 0);
  if (!Number.isFinite(channel)) {
    throw new Error("channel が不正です");
  }
  const pts: M5CalPoint[] = [];
  const rawPts = Array.isArray(data.points) ? data.points : [];
  for (const p of rawPts) {
    const pt = asPoint(p);
    if (pt) pts.push(pt);
  }
  if (pts.length < 2) {
    throw new Error("点が足りません");
  }
  if (pts.length > CAL_MAP_MAX_POINTS) {
    throw new Error(`点が多すぎます（最大 ${CAL_MAP_MAX_POINTS}）`);
  }
  return { channel: Math.trunc(channel), points: pts };
}

/** ブラウザで cal_map_chN.json を保存する */
export function downloadCalMap(channel: number, points: M5CalPoint[]): void {
  const blob = new Blob([serializeCalMap(channel, points)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `cal_map_ch${Math.trunc(channel)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
