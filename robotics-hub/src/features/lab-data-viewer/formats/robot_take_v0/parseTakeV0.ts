/**
 * robot_take_v0 の jsonl（IMU / サーボ指令）をパースし、壁時計で突き合わせる。
 * 映像時刻は `video_t0_unix + video.currentTime`。
 */

export type ImuJsonlRow = {
  wall_unix: number;
  pitch?: number;
  roll?: number;
  yaw?: number;
};

export type CommandJsonlRow = {
  wall_unix: number;
  endpoint?: string;
  raw: Record<string, unknown>;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

/** daemon は angle.pitch、フラットな pitch のどちらも許容する。 */
function nestedAngle(obj: Record<string, unknown>, key: "pitch" | "roll" | "yaw"): number | undefined {
  const top = finiteNumber(obj[key]);
  if (top !== undefined) return top;
  const angle = asRecord(obj.angle);
  return angle ? finiteNumber(angle[key]) : undefined;
}

function parseJsonlObjects(text: string): Record<string, unknown>[] {
  const out: Record<string, unknown>[] = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const obj = asRecord(JSON.parse(trimmed) as unknown);
      if (obj) out.push(obj);
    } catch {
      // 途中書き込みや壊れた行はスキップ
    }
  }
  return out;
}

function byWallUnix<T extends { wall_unix: number }>(a: T, b: T): number {
  return a.wall_unix - b.wall_unix;
}

export function parseImuJsonl(text: string): ImuJsonlRow[] {
  const rows: ImuJsonlRow[] = [];
  for (const obj of parseJsonlObjects(text)) {
    const wall =
      finiteNumber(obj.wall_unix) ??
      finiteNumber(obj.recorder_recv_unix);
    if (wall === undefined) continue;
    rows.push({
      wall_unix: wall,
      pitch: nestedAngle(obj, "pitch"),
      roll: nestedAngle(obj, "roll"),
      yaw: nestedAngle(obj, "yaw"),
    });
  }
  rows.sort(byWallUnix);
  return rows;
}

export function parseCommandJsonl(text: string): CommandJsonlRow[] {
  const rows: CommandJsonlRow[] = [];
  for (const obj of parseJsonlObjects(text)) {
    const wall =
      finiteNumber(obj.wall_unix) ??
      finiteNumber(obj.recorder_recv_unix) ??
      finiteNumber(obj.forwarded_at_unix);
    if (wall === undefined) continue;
    const endpoint = obj.endpoint;
    rows.push({
      wall_unix: wall,
      endpoint: typeof endpoint === "string" ? endpoint : undefined,
      raw: obj,
    });
  }
  rows.sort(byWallUnix);
  return rows;
}

/**
 * wall_unix 昇順の IMU から、指定時刻に最も近い行の index。
 * 空、または時刻が非有限なら -1。
 */
export function nearestImuIndex(rows: ImuJsonlRow[], wallUnix: number): number {
  if (rows.length === 0 || !Number.isFinite(wallUnix)) return -1;
  let lo = 0;
  let hi = rows.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (rows[mid]!.wall_unix < wallUnix) lo = mid + 1;
    else hi = mid;
  }
  const i = lo;
  if (i <= 0) return 0;
  if (i >= rows.length) return rows.length - 1;
  const d0 = Math.abs(rows[i]!.wall_unix - wallUnix);
  const d1 = Math.abs(rows[i - 1]!.wall_unix - wallUnix);
  return d0 < d1 ? i : i - 1;
}

/**
 * ±windowSec 内の指令を、指定時刻に近い順で最大 maxRows 件。
 */
export function commandsAround(
  rows: CommandJsonlRow[],
  wallUnix: number,
  windowSec: number,
  maxRows: number
): CommandJsonlRow[] {
  if (rows.length === 0 || !Number.isFinite(wallUnix) || windowSec < 0) return [];
  const loT = wallUnix - windowSec;
  const hiT = wallUnix + windowSec;
  let lo = 0;
  let hi = rows.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (rows[mid]!.wall_unix < loT) lo = mid + 1;
    else hi = mid;
  }
  const picked: CommandJsonlRow[] = [];
  for (let i = lo; i < rows.length; i++) {
    const row = rows[i]!;
    if (row.wall_unix > hiT) break;
    if (row.wall_unix >= loT) picked.push(row);
  }
  picked.sort(
    (a, b) => Math.abs(a.wall_unix - wallUnix) - Math.abs(b.wall_unix - wallUnix)
  );
  return picked.slice(0, maxRows);
}
