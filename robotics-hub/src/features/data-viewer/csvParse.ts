/** 1 行を RFC 4180 風に分割（フィールド内のダブルクォート対応） */
export function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i]!;
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      out.push(cur);
      cur = "";
    } else {
      cur += c;
    }
  }
  out.push(cur);
  return out;
}

export function parseCsvRows(text: string): string[][] {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  return lines.map(splitCsvLine);
}

function cellNum(c: string | undefined): number | undefined {
  if (c === undefined || c === "") return undefined;
  const v = Number(c);
  return Number.isFinite(v) ? v : undefined;
}

function cellBool(c: string | undefined): boolean | undefined {
  if (c === undefined || c === "") return undefined;
  const t = c.trim().toLowerCase();
  if (t === "true" || t === "1") return true;
  if (t === "false" || t === "0") return false;
  return undefined;
}

export interface ImuCsvRow {
  wall_unix: number;
  perf_timestamp: number | undefined;
  mock: boolean | undefined;
  accel_x: number | undefined;
  accel_y: number | undefined;
  accel_z: number | undefined;
  gyro_x: number | undefined;
  gyro_y: number | undefined;
  gyro_z: number | undefined;
  angle_pitch: number | undefined;
  angle_roll: number | undefined;
  angle_yaw: number | undefined;
}

export interface ServoCsvRow {
  wall_unix: number;
  perf_timestamp: number | undefined;
  endpoint: string | undefined;
  mode: string | undefined;
  ch: number | undefined;
  angle_in: number | undefined;
  logical_deg: number | undefined;
  physical_deg: number | undefined;
  extra_json: string | undefined;
}

function headerIndex(header: string[], name: string): number {
  const i = header.indexOf(name);
  if (i < 0) throw new Error(`CSV ヘッダに必須列 "${name}" がありません`);
  return i;
}

export function parseImuCsv(text: string): ImuCsvRow[] {
  const rows = parseCsvRows(text);
  if (rows.length < 2) return [];
  const h = rows[0]!;
  const wi = headerIndex(h, "wall_unix");
  const out: ImuCsvRow[] = [];
  for (let r = 1; r < rows.length; r++) {
    const c = rows[r]!;
    const wall = cellNum(c[wi]);
    if (wall === undefined) continue;
    const gi = (name: string) => {
      const j = h.indexOf(name);
      return j < 0 ? undefined : c[j];
    };
    out.push({
      wall_unix: wall,
      perf_timestamp: cellNum(gi("perf_timestamp")),
      mock: cellBool(gi("mock")),
      accel_x: cellNum(gi("accel_x")),
      accel_y: cellNum(gi("accel_y")),
      accel_z: cellNum(gi("accel_z")),
      gyro_x: cellNum(gi("gyro_x")),
      gyro_y: cellNum(gi("gyro_y")),
      gyro_z: cellNum(gi("gyro_z")),
      angle_pitch: cellNum(gi("angle_pitch")),
      angle_roll: cellNum(gi("angle_roll")),
      angle_yaw: cellNum(gi("angle_yaw")),
    });
  }
  out.sort((a, b) => a.wall_unix - b.wall_unix);
  return out;
}

export function parseServoCsv(text: string): ServoCsvRow[] {
  const rows = parseCsvRows(text);
  if (rows.length < 2) return [];
  const h = rows[0]!;
  const wi = headerIndex(h, "wall_unix");
  const out: ServoCsvRow[] = [];
  for (let r = 1; r < rows.length; r++) {
    const c = rows[r]!;
    const wall = cellNum(c[wi]);
    if (wall === undefined) continue;
    const gi = (name: string) => {
      const j = h.indexOf(name);
      return j < 0 ? undefined : c[j];
    };
    out.push({
      wall_unix: wall,
      perf_timestamp: cellNum(gi("perf_timestamp")),
      endpoint: gi("endpoint"),
      mode: gi("mode"),
      ch: cellNum(gi("ch")),
      angle_in: cellNum(gi("angle_in")),
      logical_deg: cellNum(gi("logical_deg")),
      physical_deg: cellNum(gi("physical_deg")),
      extra_json: gi("extra_json"),
    });
  }
  out.sort((a, b) => a.wall_unix - b.wall_unix);
  return out;
}
