import type { ImuCsvRow, ServoCsvRow } from "./csvParse";

/**
 * perf_timestamp が昇順で、各行に有限な perf_timestamp があることを前提。
 * （呼び出し側で filter + sort 済みの配列を渡す）
 */
export function nearestImuIndexByPerf(rows: ImuCsvRow[], perfT: number): number {
  if (rows.length === 0 || !Number.isFinite(perfT)) return -1;
  let lo = 0;
  let hi = rows.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (rows[mid]!.perf_timestamp! < perfT) lo = mid + 1;
    else hi = mid;
  }
  const i = lo;
  if (i <= 0) return 0;
  if (i >= rows.length) return rows.length - 1;
  const d0 = Math.abs(rows[i]!.perf_timestamp! - perfT);
  const d1 = Math.abs(rows[i - 1]!.perf_timestamp! - perfT);
  return d0 < d1 ? i : i - 1;
}

/**
 * perf_timestamp 昇順・各行に有限な perf があることを前提。
 */
export function servoRowsAroundPerf(
  rows: ServoCsvRow[],
  perfT: number,
  windowSec: number,
  maxRows: number
): ServoCsvRow[] {
  if (rows.length === 0 || !Number.isFinite(perfT)) return [];
  const loT = perfT - windowSec;
  const hiT = perfT + windowSec;
  let lo = 0;
  let hi = rows.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (rows[mid]!.perf_timestamp! < loT) lo = mid + 1;
    else hi = mid;
  }
  let i = lo;
  const picked: ServoCsvRow[] = [];
  while (i < rows.length) {
    const row = rows[i]!;
    const p = row.perf_timestamp!;
    if (p > hiT) break;
    if (p >= loT) picked.push(row);
    i++;
  }
  picked.sort(
    (a, b) => Math.abs(a.perf_timestamp! - perfT) - Math.abs(b.perf_timestamp! - perfT)
  );
  return picked.slice(0, maxRows);
}

export function minPerfTimestamp(imu: ImuCsvRow[], servo: ServoCsvRow[]): number | null {
  let m = Infinity;
  for (const r of imu) {
    const p = r.perf_timestamp;
    if (p !== undefined && Number.isFinite(p)) m = Math.min(m, p);
  }
  for (const r of servo) {
    const p = r.perf_timestamp;
    if (p !== undefined && Number.isFinite(p)) m = Math.min(m, p);
  }
  return m === Infinity ? null : m;
}

export function maxPerfTimestamp(imu: ImuCsvRow[], servo: ServoCsvRow[]): number | null {
  let m = -Infinity;
  for (const r of imu) {
    const p = r.perf_timestamp;
    if (p !== undefined && Number.isFinite(p)) m = Math.max(m, p);
  }
  for (const r of servo) {
    const p = r.perf_timestamp;
    if (p !== undefined && Number.isFinite(p)) m = Math.max(m, p);
  }
  return m === -Infinity ? null : m;
}
