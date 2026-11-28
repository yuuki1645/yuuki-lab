/** Lab experiment API. The browser never receives a raw jsonl file. */

import type {
  LabAnalysis,
  LabDaysResponse,
  LabRangeStats,
  LabRows,
  LabSample,
  LabTakesResponse,
  LabWindow,
} from "./types";

const BASE = "/api/lab";

function takeBase(day: string, takeId: string): string {
  return `${BASE}/takes/${encodeURIComponent(day)}/${encodeURIComponent(takeId)}`;
}

/** Query string with only the defined values. Numbers keep 4 decimals. */
function query(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null) continue;
    q.set(key, typeof value === "number" ? String(Math.round(value * 10000) / 10000) : value);
  }
  return q.toString();
}

/** JSON GET. A non-JSON error body is thrown as its text. */
async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal });
  if (!res.ok) {
    throw new Error((await res.text()) || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export const labApi = {
  getDays(): Promise<LabDaysResponse> {
    return getJson(`${BASE}/days`);
  },

  getTakes(day: string): Promise<LabTakesResponse> {
    return getJson(`${BASE}/takes?day=${encodeURIComponent(day)}`);
  },

  /** Health map, findings and stats. First open of a take parses it (seconds). */
  getAnalysis(
    day: string,
    takeId: string,
    buckets = 800,
    signal?: AbortSignal,
    side?: string | null,
  ): Promise<LabAnalysis> {
    return getJson(`${takeBase(day, takeId)}/analysis?${query({ buckets, side })}`, signal);
  },

  /** Plot data for [from, to]: raw rows, or min/max buckets past maxPoints. */
  getWindow(
    day: string,
    takeId: string,
    channels: string[],
    from: number,
    to: number,
    maxPoints: number,
    signal?: AbortSignal,
    side?: string | null,
  ): Promise<LabWindow> {
    const q = query({ channels: channels.join(","), from, to, max_points: Math.round(maxPoints), side });
    return getJson(`${takeBase(day, takeId)}/window?${q}`, signal);
  },

  getStats(
    day: string,
    takeId: string,
    channels: string[],
    from: number,
    to: number,
    signal?: AbortSignal,
    side?: string | null,
  ): Promise<LabRangeStats> {
    const q = query({ channels: channels.join(","), from, to, side });
    return getJson(`${takeBase(day, takeId)}/stats?${q}`, signal);
  },

  getRows(
    day: string,
    takeId: string,
    channels: string[],
    start: number,
    count: number,
    signal?: AbortSignal,
    side?: string | null,
  ): Promise<LabRows> {
    const q = query({
      channels: channels.join(","),
      start: Math.max(0, Math.round(start)),
      count,
      side,
    });
    return getJson(`${takeBase(day, takeId)}/rows?${q}`, signal);
  },

  /** Nearest row to t, or the row at index. */
  getSample(
    day: string,
    takeId: string,
    at: { index?: number; t?: number },
    signal?: AbortSignal,
    side?: string | null,
  ): Promise<LabSample> {
    const q = query({ index: at.index, t: at.t, side });
    return getJson(`${takeBase(day, takeId)}/sample?${q}`, signal);
  },

  /** Save a CSV of [from, to]. The file is fetched and handed to the browser. */
  async downloadCsv(
    day: string,
    takeId: string,
    channels: string[],
    from: number | null,
    to: number | null,
    side?: string | null,
  ) {
    const q = query({ channels: channels.join(","), from, to, side });
    const res = await fetch(`${takeBase(day, takeId)}/export.csv?${q}`);
    if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = /filename="([^"]+)"/.exec(disposition);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = match?.[1] ?? `${takeId}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 10000);
  },
};
