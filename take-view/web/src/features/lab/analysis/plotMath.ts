/**
 * Pure helpers for the lab workbench: view (zoom / pan) math, tick
 * placement, time and number formatting, and lookups into window data.
 *
 * The time axis everywhere is "offset": seconds since the first sensor row
 * of the take. Nothing here touches the DOM, so it is unit-tested directly.
 */

import type { LabWindow } from "../types";

/** Visible time range in offset seconds. */
export type View = { from: number; to: number };

/** Smallest span the user can zoom to (about five 20 Hz samples). */
export const MIN_SPAN_SEC = 0.25;

/** Keep a view inside [0, duration] and at least MIN_SPAN_SEC wide. */
export function clampView(view: View, duration: number, minSpan = MIN_SPAN_SEC): View {
  const total = Math.max(duration, minSpan);
  const wanted = Number.isFinite(view.to - view.from) ? view.to - view.from : total;
  const span = Math.min(Math.max(wanted, minSpan), total);
  const start = Number.isFinite(view.from) ? view.from : 0;
  const from = Math.min(Math.max(start, 0), total - span);
  return { from, to: from + span };
}

/**
 * Zoom around a fixed time. factor < 1 zooms in, > 1 zooms out.
 * The time under the mouse stays under the mouse.
 */
export function zoomView(view: View, center: number, factor: number, duration: number): View {
  const span = view.to - view.from || 1;
  const ratio = Math.min(Math.max((center - view.from) / span, 0), 1);
  const next = span * factor;
  const from = center - next * ratio;
  return clampView({ from, to: from + next }, duration);
}

/** Shift a view by delta seconds without changing its span. */
export function panView(view: View, delta: number, duration: number): View {
  return clampView({ from: view.from + delta, to: view.to + delta }, duration);
}

/**
 * View that shows [from, to] with context on both sides, so a short
 * anomaly is never squeezed against the plot edge.
 */
export function focusView(from: number, to: number, duration: number, minSpan = 4): View {
  const span = Math.max(to - from, 0);
  const pad = Math.max(span * 0.5, (minSpan - span) / 2, 0.5);
  return clampView({ from: from - pad, to: to + pad }, duration);
}

/** Same span, moved so t is in the middle. Leaves the view alone if t is already well inside. */
export function revealTime(view: View, t: number, duration: number): View {
  const span = view.to - view.from;
  const margin = span * 0.05;
  if (t >= view.from + margin && t <= view.to - margin) return view;
  return clampView({ from: t - span / 2, to: t + span / 2 }, duration);
}

const TIME_STEPS = [
  0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200,
];

/** A "round" tick spacing that gives roughly approxTicks ticks over span. */
export function timeStep(span: number, approxTicks: number): number {
  const raw = span / Math.max(1, approxTicks);
  return TIME_STEPS.find((step) => step >= raw) ?? TIME_STEPS[TIME_STEPS.length - 1];
}

/** Tick positions (offset seconds) inside the view. */
export function timeTicks(view: View, approxTicks: number): { step: number; ticks: number[] } {
  const step = timeStep(view.to - view.from, approxTicks);
  const ticks: number[] = [];
  const first = Math.ceil(view.from / step - 1e-9);
  for (let k = first; k * step <= view.to + 1e-9 && ticks.length < 200; k += 1) {
    ticks.push(Number((k * step).toFixed(6)));
  }
  return { step, ticks };
}

/** Value ticks at 1 / 2 / 2.5 / 5 x 10^n spacing. */
export function niceTicks(min: number, max: number, approx: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || !(max > min)) return Number.isFinite(min) ? [min] : [];
  const raw = (max - min) / Math.max(1, approx);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
  const out: number[] = [];
  for (let k = Math.ceil(min / step - 1e-9); k * step <= max + step * 1e-9 && out.length < 50; k += 1) {
    out.push(Number((k * step).toPrecision(12)));
  }
  return out;
}

/** Decimal places for an offset label, from the tick spacing. */
function offsetDecimals(step: number): number {
  if (step < 0.1) return 2;
  if (step < 1) return 1;
  return 0;
}

/**
 * Offset as m:ss (or h:mm:ss), with decimals when ticks are closer than
 * a second. Rounds first so 59.96 s never prints as "0:60.0".
 */
export function formatOffset(sec: number, step = 1): string {
  if (!Number.isFinite(sec)) return "\u2014";
  const decimals = offsetDecimals(step);
  const factor = 10 ** decimals;
  const sign = sec < 0 ? "-" : "";
  const total = Math.round(Math.abs(sec) * factor) / factor;
  const hours = Math.floor(total / 3600);
  const mins = Math.floor((total - hours * 3600) / 60);
  const rest = total - hours * 3600 - mins * 60;
  const [whole, frac] = rest.toFixed(decimals).split(".");
  const secs = whole.padStart(2, "0") + (frac ? `.${frac}` : "");
  if (hours > 0) return `${sign}${hours}:${String(mins).padStart(2, "0")}:${secs}`;
  return `${sign}${mins}:${secs}`;
}

/** Wall clock (local time, ms) of an offset, e.g. 19:24:33.445. */
export function formatClock(t0: number, offset: number): string {
  const date = new Date((t0 + offset) * 1000);
  if (Number.isNaN(date.getTime())) return "\u2014";
  const pad = (value: number, width = 2) => String(value).padStart(width, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${pad(date.getMilliseconds(), 3)}`;
}

/**
 * Number for tables and legends. Large magnitudes drop decimals so the
 * column stays readable; null / NaN become a dash (a gap, never 0).
 */
export function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return "\u2014";
  const abs = Math.abs(value);
  const places = abs >= 100000 ? 0 : abs >= 10000 ? Math.min(digits, 1) : digits;
  return value.toFixed(places);
}

/** Share 0..1 as a percentage string. */
export function formatPct(ratio: number | null | undefined, digits = 0): string {
  if (ratio == null || !Number.isFinite(ratio)) return "\u2014";
  return `${(ratio * 100).toFixed(digits)}%`;
}

/** Index of the element of an ascending array closest to x (-1 when empty). */
export function nearestIndex(sorted: ArrayLike<number>, x: number): number {
  const count = sorted.length;
  if (count === 0) return -1;
  let lo = 0;
  let hi = count - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] < x) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(sorted[lo - 1] - x) <= Math.abs(sorted[lo] - x)) return lo - 1;
  return lo;
}

/** A plotted value at one instant: one number (raw) or a bucket range (envelope). */
export type PointValue = { value: number | null; min?: number | null; max?: number | null; t: number; index: number | null };

/**
 * Value of one channel nearest to t in window data. Returns null when the
 * window has no row near t (more than two sample spacings away).
 */
export function valueAt(data: LabWindow | null, key: string, t: number): PointValue | null {
  if (!data || data.t.length === 0) return null;
  const at = nearestIndex(data.t, t);
  if (at < 0) return null;
  const spacing = data.mode === "envelope" ? data.bucket_sec ?? 0 : (data.t[data.t.length - 1] - data.t[0]) / Math.max(1, data.t.length - 1);
  if (Math.abs(data.t[at] - t) > Math.max(spacing * 2, 0.15)) return null;
  const series = data.series[key];
  if (!series) return null;
  if (data.mode === "raw") {
    return { value: series.v?.[at] ?? null, t: data.t[at], index: data.index[at] ?? null };
  }
  return {
    value: series.mean?.[at] ?? null,
    min: series.min?.[at] ?? null,
    max: series.max?.[at] ?? null,
    t: data.t[at],
    index: data.index[at] ?? null,
  };
}

/** True when t falls inside one of the [start, end] spans. */
function inSpans(t: number, spans: number[][]): boolean {
  for (const [start, end] of spans) {
    if (t >= start && t <= end) return true;
  }
  return false;
}

/**
 * [min, max] of the given channels inside the view (envelope uses min/max).
 * With ``spans``, only rows inside them count, so values that are dimmed
 * as meaningless (e.g. tracking error with the output off) do not squash
 * the scale of the ones that matter. Falls back to everything when no
 * span overlaps the view.
 */
export function dataExtent(
  data: LabWindow | null,
  keys: string[],
  view: View,
  spans?: number[][]
): [number, number] | null {
  if (!data) return null;
  const useSpans = spans?.some(([start, end]) => end >= view.from && start <= view.to) ?? false;
  let lo = Infinity;
  let hi = -Infinity;
  for (const key of keys) {
    const series = data.series[key];
    if (!series) continue;
    const lows = data.mode === "raw" ? series.v : series.min;
    const highs = data.mode === "raw" ? series.v : series.max;
    if (!lows || !highs) continue;
    for (let i = 0; i < data.t.length; i += 1) {
      const t = data.t[i];
      if (t < view.from || t > view.to) continue;
      if (useSpans && spans && !inSpans(t, spans)) continue;
      const a = lows[i];
      const b = highs[i];
      if (a != null && a < lo) lo = a;
      if (b != null && b > hi) hi = b;
    }
  }
  return Number.isFinite(lo) && Number.isFinite(hi) ? [lo, hi] : null;
}

/** Pad a value range so lines never touch the plot border. */
export function paddedDomain(extent: [number, number] | null): [number, number] {
  if (!extent) return [0, 1];
  const [lo, hi] = extent;
  if (hi - lo < 1e-9) {
    const pad = Math.abs(hi) * 0.05 || 0.5;
    return [lo - pad, hi + pad];
  }
  const pad = (hi - lo) * 0.08;
  return [lo - pad, hi + pad];
}

/** How many points to ask the server for, given the plot width in pixels. */
export function pointsForWidth(width: number): number {
  return Math.min(6000, Math.max(400, Math.round(width * 2)));
}
