import type { ImuCsvRow, ServoCsvRow } from "./csvParse";

/** wall_unix が昇順であることを前提に、最も近い IMU 行のインデックス */
export function nearestImuIndex(rows: ImuCsvRow[], wallUnix: number): number {
  if (rows.length === 0) return -1;
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

/** 時刻 t に最も近いサーボ行のうち、前後 windowSec 以内のものを最大 maxRows 件 */
export function servoRowsAround(
  rows: ServoCsvRow[],
  wallUnix: number,
  windowSec: number,
  maxRows: number
): ServoCsvRow[] {
  if (rows.length === 0 || !Number.isFinite(wallUnix)) return [];
  const loT = wallUnix - windowSec;
  const hiT = wallUnix + windowSec;
  let lo = 0;
  let hi = rows.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (rows[mid]!.wall_unix < loT) lo = mid + 1;
    else hi = mid;
  }
  let i = lo;
  const picked: ServoCsvRow[] = [];
  while (i < rows.length) {
    const row = rows[i]!;
    if (row.wall_unix > hiT) break;
    if (row.wall_unix >= loT) picked.push(row);
    i++;
  }
  picked.sort((a, b) => Math.abs(a.wall_unix - wallUnix) - Math.abs(b.wall_unix - wallUnix));
  return picked.slice(0, maxRows);
}

export function minWallUnix(imu: ImuCsvRow[], servo: ServoCsvRow[]): number | null {
  const a = imu.length ? imu[0]!.wall_unix : null;
  const b = servo.length ? servo[0]!.wall_unix : null;
  if (a !== null && b !== null) return Math.min(a, b);
  if (a !== null) return a;
  if (b !== null) return b;
  return null;
}

export function maxWallUnix(imu: ImuCsvRow[], servo: ServoCsvRow[]): number | null {
  const a = imu.length ? imu[imu.length - 1]!.wall_unix : null;
  const b = servo.length ? servo[servo.length - 1]!.wall_unix : null;
  if (a !== null && b !== null) return Math.max(a, b);
  if (a !== null) return a;
  if (b !== null) return b;
  return null;
}
