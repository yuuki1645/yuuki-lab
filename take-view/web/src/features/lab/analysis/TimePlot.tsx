/**
 * Canvas time-series plot used for every panel of the workbench.
 *
 * Two stacked canvases: the base layer (bands, grid, data) only redraws
 * when data, view or size change; the overlay (hover crosshair, cursor,
 * drag box) redraws on every mouse move. That keeps hovering smooth even
 * with thousands of points on ten plots.
 *
 * Interaction (shared by all plots through the workbench state):
 *   drag            select a range and zoom to it
 *   click           pick that instant (cursor)
 *   shift/middle drag  pan
 *   ctrl + wheel    zoom around the mouse; shift + wheel pans
 *   double click    whole take
 */

import { memo, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { L } from "../labels";
import type { LabWindow } from "../types";
import { LABEL_FONT, MONO_FONT, SEV_COLOR, SEV_FILL, readTheme, setupCanvas, useElementWidth } from "./canvas";
import { NODATA_FILL, type PlotLine, type PlotRef, type StateRow } from "./panels";
import {
  dataExtent,
  formatNumber,
  formatOffset,
  niceTicks,
  paddedDomain,
  panView,
  timeTicks,
  valueAt,
  zoomView,
  type View,
} from "./plotMath";

export type PlotBand = { from: number; to: number; severity: number };
export type PlotMarker = { t: number; kind: "error" | "warn" | "cmd" };

type Props = {
  title: string;
  unit: string;
  lines: PlotLine[];
  states?: StateRow[];
  refs?: PlotRef[];
  yFixed?: [number, number];
  digits: number;
  height: number;
  data: LabWindow | null;
  view: View;
  duration: number;
  hoverT: number | null;
  cursorT: number | null;
  bands: PlotBand[];
  markers: PlotMarker[];
  /** Offsets where the value is meaningful (e.g. output on). Outside is dimmed. */
  activeSpans?: number[][];
  hidden: ReadonlySet<string>;
  showAxis: boolean;
  loading: boolean;
  onHover: (t: number | null) => void;
  onPick: (t: number) => void;
  onView: (view: View) => void;
  onReset: () => void;
  onToggleLine: (key: string) => void;
};

/** Plot area insets in CSS pixels. Left leaves room for value ticks / row labels. */
const PAD_LEFT = 64;
const PAD_RIGHT = 12;
const PAD_TOP = 8;
const AXIS_H = 18;
/** Drag shorter than this is a click. */
const CLICK_PX = 4;

type Geometry = { left: number; right: number; top: number; bottom: number; width: number; height: number };

type DragState = { pointerId: number; startX: number; mode: "select" | "pan"; startView: View; moved: boolean };

function geometry(width: number, height: number, showAxis: boolean): Geometry {
  return {
    left: PAD_LEFT,
    right: Math.max(PAD_LEFT + 10, width - PAD_RIGHT),
    top: PAD_TOP,
    bottom: Math.max(PAD_TOP + 10, height - (showAxis ? AXIS_H : 6)),
    width,
    height,
  };
}

/** Decimal places for value tick labels from their spacing. */
function tickDigits(ticks: number[]): number {
  if (ticks.length < 2) return 2;
  const step = Math.abs(ticks[1] - ticks[0]);
  if (step >= 1) return 0;
  return Math.min(4, Math.ceil(-Math.log10(step)));
}

export const TimePlot = memo(function TimePlot(props: Props) {
  const {
    title,
    unit,
    lines,
    states,
    refs,
    yFixed,
    digits,
    height,
    data,
    view,
    duration,
    hoverT,
    cursorT,
    bands,
    markers,
    activeSpans,
    hidden,
    showAxis,
    loading,
    onHover,
    onPick,
    onView,
    onReset,
    onToggleLine,
  } = props;

  const frameRef = useRef<HTMLDivElement>(null);
  const baseRef = useRef<HTMLCanvasElement>(null);
  const overRef = useRef<HTMLCanvasElement>(null);
  const width = useElementWidth(frameRef);
  const geo = useMemo(() => geometry(width, height, showAxis), [width, height, showAxis]);
  const dragRef = useRef<DragState | null>(null);
  const [dragBox, setDragBox] = useState<[number, number] | null>(null);

  const visible = useMemo(() => lines.filter((line) => !hidden.has(line.key)), [lines, hidden]);
  const isStates = Boolean(states && states.length);

  // Value range: fixed, or from the visible data inside the view.
  const domain = useMemo<[number, number]>(() => {
    if (isStates) return [0, 1];
    if (yFixed) return yFixed;
    return paddedDomain(dataExtent(data, visible.map((line) => line.key), view, activeSpans));
  }, [isStates, yFixed, data, visible, view, activeSpans]);

  // Latest props for the native wheel listener (it is attached once).
  const latest = useRef({ view, duration, geo, onView });
  latest.current = { view, duration, geo, onView };

  const tAt = (x: number, g: Geometry = geo, v: View = view): number =>
    v.from + ((x - g.left) / Math.max(1, g.right - g.left)) * (v.to - v.from);

  // ----- base layer ----------------------------------------------------
  useEffect(() => {
    const canvas = baseRef.current;
    if (!canvas || width <= 0) return;
    const ctx = setupCanvas(canvas, width, height);
    if (!ctx) return;
    const theme = readTheme();
    const g = geo;
    const span = view.to - view.from || 1;
    const plotW = g.right - g.left;
    const plotH = g.bottom - g.top;
    const x = (t: number) => g.left + ((t - view.from) / span) * plotW;
    const [lo, hi] = domain;
    const y = (v: number) => g.bottom - ((v - lo) / (hi - lo || 1)) * plotH;

    // Plot background.
    ctx.fillStyle = "rgba(255, 255, 255, 0.015)";
    ctx.fillRect(g.left, g.top, plotW, plotH);

    // Anomaly bands behind everything. Never thinner than 2 px so a single
    // bad row stays visible when zoomed out; a solid tick on top marks them.
    for (const band of bands) {
      if (band.to < view.from || band.from > view.to) continue;
      const x0 = Math.max(g.left, x(band.from));
      const x1 = Math.min(g.right, Math.max(x(band.to), x0 + 2));
      ctx.fillStyle = SEV_FILL[band.severity] ?? SEV_FILL[1];
      ctx.fillRect(x0, g.top, x1 - x0, plotH);
      if (band.severity >= 2) {
        ctx.fillStyle = SEV_COLOR[band.severity];
        ctx.fillRect(x0, g.top, x1 - x0, 2);
      }
    }

    // Time grid (and labels on the bottom plot only).
    const { step, ticks } = timeTicks(view, Math.max(2, Math.floor(plotW / 90)));
    ctx.strokeStyle = theme.grid;
    ctx.globalAlpha = 0.55;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const tick of ticks) {
      const px = Math.round(x(tick)) + 0.5;
      ctx.moveTo(px, g.top);
      ctx.lineTo(px, g.bottom);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
    if (showAxis) {
      ctx.fillStyle = theme.muted;
      ctx.font = MONO_FONT;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      for (const tick of ticks) ctx.fillText(formatOffset(tick, step), x(tick), g.bottom + 4);
    }

    ctx.save();
    ctx.beginPath();
    ctx.rect(g.left, g.top, plotW, plotH);
    ctx.clip();

    if (isStates && states) {
      drawStates(ctx, data, states, g, x, theme.grid);
    } else {
      // Value grid.
      const yTicks = niceTicks(lo, hi, Math.max(2, Math.floor(plotH / 34)));
      ctx.strokeStyle = theme.grid;
      ctx.globalAlpha = 0.45;
      ctx.beginPath();
      for (const tick of yTicks) {
        const py = Math.round(y(tick)) + 0.5;
        ctx.moveTo(g.left, py);
        ctx.lineTo(g.right, py);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;

      // Threshold lines. Labels that would overlap a label already drawn
      // are skipped; the line itself is always drawn.
      const labelled: number[] = [];
      const shownRefs = (refs ?? []).filter((ref) => ref.y >= lo && ref.y <= hi).sort((a, b) => b.y - a.y);
      for (const ref of shownRefs) {
        const py = Math.round(y(ref.y)) + 0.5;
        ctx.strokeStyle = ref.color;
        ctx.globalAlpha = 0.7;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(g.left, py);
        ctx.lineTo(g.right, py);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        if (labelled.every((other) => Math.abs(other - py) >= 12)) {
          ctx.fillStyle = ref.color;
          ctx.font = LABEL_FONT;
          ctx.textAlign = "right";
          ctx.textBaseline = "bottom";
          ctx.fillText(ref.label, g.right - 4, py - 2);
          labelled.push(py);
        }
      }

      if (data) {
        for (const line of visible) drawLine(ctx, data, line, x, y, view, plotW);
      }

      // Rows where the value means nothing (output off) are dimmed, not hidden.
      if (activeSpans) {
        ctx.fillStyle = "rgba(8, 12, 18, 0.62)";
        let cursor = view.from;
        const spans = [...activeSpans].sort((a, b) => a[0] - b[0]);
        for (const [start, end] of spans) {
          if (end < view.from) continue;
          if (start > view.to) break;
          if (start > cursor) ctx.fillRect(x(cursor), g.top, x(start) - x(cursor), plotH);
          cursor = Math.max(cursor, end);
        }
        if (cursor < view.to) ctx.fillRect(x(cursor), g.top, x(view.to) - x(cursor), plotH);
      }
    }

    // Event / command markers.
    for (const marker of markers) {
      if (marker.t < view.from || marker.t > view.to) continue;
      const px = Math.round(x(marker.t)) + 0.5;
      if (marker.kind === "cmd") {
        ctx.strokeStyle = theme.accent;
        ctx.globalAlpha = 0.9;
        ctx.beginPath();
        ctx.moveTo(px, g.bottom - 7);
        ctx.lineTo(px, g.bottom);
        ctx.stroke();
      } else {
        ctx.strokeStyle = marker.kind === "error" ? SEV_COLOR[3] : SEV_COLOR[2];
        ctx.globalAlpha = marker.kind === "error" ? 0.85 : 0.3;
        ctx.beginPath();
        ctx.moveTo(px, g.top);
        ctx.lineTo(px, g.bottom);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
    ctx.restore();

    // Value tick labels (or state row labels) in the left gutter.
    ctx.fillStyle = theme.muted;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    if (isStates && states) {
      ctx.font = LABEL_FONT;
      const rowH = plotH / states.length;
      states.forEach((row, index) => {
        ctx.fillText(row.label, g.left - 6, g.top + rowH * (index + 0.5), g.left - 8);
      });
    } else {
      ctx.font = MONO_FONT;
      const yTicks = niceTicks(lo, hi, Math.max(2, Math.floor(plotH / 34)));
      const places = tickDigits(yTicks);
      for (const tick of yTicks) ctx.fillText(tick.toFixed(places), g.left - 6, y(tick));
    }

    ctx.strokeStyle = theme.grid;
    ctx.strokeRect(g.left + 0.5, g.top + 0.5, plotW - 1, plotH - 1);
  }, [
    width,
    height,
    geo,
    view,
    domain,
    data,
    visible,
    isStates,
    states,
    refs,
    bands,
    markers,
    activeSpans,
    showAxis,
  ]);

  // ----- overlay layer -------------------------------------------------
  useEffect(() => {
    const canvas = overRef.current;
    if (!canvas || width <= 0) return;
    const ctx = setupCanvas(canvas, width, height);
    if (!ctx) return;
    const theme = readTheme();
    const g = geo;
    const span = view.to - view.from || 1;
    const plotW = g.right - g.left;
    const x = (t: number) => g.left + ((t - view.from) / span) * plotW;
    const [lo, hi] = domain;
    const y = (v: number) => g.bottom - ((v - lo) / (hi - lo || 1)) * (g.bottom - g.top);

    if (dragBox) {
      const [a, b] = dragBox;
      ctx.fillStyle = "rgba(77, 166, 255, 0.16)";
      ctx.fillRect(Math.min(a, b), g.top, Math.abs(b - a), g.bottom - g.top);
      ctx.strokeStyle = theme.accent;
      ctx.strokeRect(Math.min(a, b) + 0.5, g.top + 0.5, Math.abs(b - a), g.bottom - g.top - 1);
    }

    const drawVertical = (t: number, color: string, dash: number[]) => {
      if (t < view.from || t > view.to) return;
      const px = Math.round(x(t)) + 0.5;
      ctx.strokeStyle = color;
      ctx.setLineDash(dash);
      ctx.beginPath();
      ctx.moveTo(px, g.top);
      ctx.lineTo(px, g.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
      // Value dots where the line crosses each visible series.
      if (!isStates && data) {
        for (const line of visible) {
          const point = valueAt(data, line.key, t);
          if (!point || point.value == null) continue;
          ctx.fillStyle = line.color;
          ctx.beginPath();
          ctx.arc(x(point.t), y(point.value), 3, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    };

    if (cursorT != null) drawVertical(cursorT, "rgba(255, 255, 255, 0.9)", []);
    if (hoverT != null) {
      drawVertical(hoverT, theme.muted, [3, 3]);
      if (hoverT >= view.from && hoverT <= view.to) {
        const { step } = timeTicks(view, Math.max(2, Math.floor(plotW / 90)));
        const text = formatOffset(hoverT, Math.min(step / 10, 0.01));
        ctx.font = MONO_FONT;
        const textW = ctx.measureText(text).width + 8;
        const px = Math.min(Math.max(x(hoverT) - textW / 2, g.left), g.right - textW);
        ctx.fillStyle = "rgba(15, 20, 25, 0.9)";
        ctx.fillRect(px, g.top, textW, 15);
        ctx.fillStyle = theme.text;
        ctx.textAlign = "left";
        ctx.textBaseline = "top";
        ctx.fillText(text, px + 4, g.top + 2);
      }
    }
  }, [width, height, geo, view, domain, hoverT, cursorT, dragBox, data, visible, isStates]);

  // Ctrl + wheel zooms, shift + wheel pans. Needs a non-passive listener to
  // stop the page from scrolling or the browser from zooming.
  useEffect(() => {
    const canvas = overRef.current;
    if (!canvas) return;
    const onWheel = (event: WheelEvent) => {
      const { view: v, duration: total, geo: g, onView: apply } = latest.current;
      const rect = canvas.getBoundingClientRect();
      const px = event.clientX - rect.left;
      if (px < g.left || px > g.right) return;
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault();
        const centre = v.from + ((px - g.left) / Math.max(1, g.right - g.left)) * (v.to - v.from);
        apply(zoomView(v, centre, event.deltaY > 0 ? 1.25 : 0.8, total));
      } else if (event.shiftKey) {
        event.preventDefault();
        const delta = (event.deltaY || event.deltaX) / Math.max(1, g.right - g.left);
        apply(panView(v, delta * (v.to - v.from), total));
      }
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, []);

  const localX = (event: ReactPointerEvent<HTMLCanvasElement>) =>
    event.clientX - event.currentTarget.getBoundingClientRect().left;

  const handleDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0 && event.button !== 1) return;
    const px = localX(event);
    if (px < geo.left || px > geo.right) return;
    event.preventDefault();
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      /* Pointer already gone (e.g. released before capture); drag still works inside the canvas. */
    }
    dragRef.current = {
      pointerId: event.pointerId,
      startX: px,
      mode: event.button === 1 || event.shiftKey ? "pan" : "select",
      startView: view,
      moved: false,
    };
  };

  const handleMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const px = Math.min(Math.max(localX(event), geo.left), geo.right);
    const drag = dragRef.current;
    if (drag) {
      if (Math.abs(px - drag.startX) > CLICK_PX) drag.moved = true;
      if (drag.mode === "pan") {
        const delta = ((drag.startX - px) / Math.max(1, geo.right - geo.left)) * (drag.startView.to - drag.startView.from);
        onView(panView(drag.startView, delta, duration));
      } else if (drag.moved) {
        setDragBox([drag.startX, px]);
      }
    }
    onHover(tAt(px));
  };

  const handleUp = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    dragRef.current = null;
    setDragBox(null);
    if (!drag) return;
    const px = Math.min(Math.max(localX(event), geo.left), geo.right);
    if (drag.mode === "select") {
      if (drag.moved) {
        const a = tAt(Math.min(drag.startX, px));
        const b = tAt(Math.max(drag.startX, px));
        onView({ from: a, to: b });
      } else {
        onPick(tAt(px));
      }
    }
  };

  // Legend values follow the hover line, else the pinned cursor.
  const legendT = hoverT ?? cursorT;
  const legend = (isStates ? [] : lines).map((line) => {
    const point = legendT != null && data ? valueAt(data, line.key, legendT) : null;
    let text = "";
    if (point) {
      if (point.min != null && point.max != null && data?.mode === "envelope" && point.min !== point.max) {
        text = `${formatNumber(point.min, digits)}\u2013${formatNumber(point.max, digits)}`;
      } else {
        text = point.value == null ? L.missing : formatNumber(point.value, digits);
      }
    }
    return { line, text, off: hidden.has(line.key) };
  });

  return (
    <section className="lab-plot">
      <header className="lab-plot-head">
        <h4 className="lab-plot-title">
          {title}
          {unit ? <span className="lab-plot-unit">{unit}</span> : null}
          {loading ? <span className="lab-plot-loading" aria-hidden /> : null}
        </h4>
        <ul className="lab-legend">
          {legend.map(({ line, text, off }) => (
            <li key={line.key}>
              <button
                type="button"
                className={off ? "lab-legend-item is-off" : "lab-legend-item"}
                onClick={() => onToggleLine(line.key)}
              >
                <span
                  className="lab-legend-swatch"
                  style={{
                    background: line.dash
                      ? `repeating-linear-gradient(90deg, ${line.color} 0 4px, transparent 4px 7px)`
                      : line.color,
                  }}
                />
                <span className="lab-legend-label">{line.label}</span>
                {text ? <span className="lab-legend-value">{text}</span> : null}
              </button>
            </li>
          ))}
        </ul>
      </header>
      <div className="lab-plot-frame" ref={frameRef} style={{ height }}>
        <canvas ref={baseRef} className="lab-plot-canvas" />
        <canvas
          ref={overRef}
          className="lab-plot-canvas lab-plot-overlay"
          onPointerDown={handleDown}
          onPointerMove={handleMove}
          onPointerUp={handleUp}
          onPointerCancel={handleUp}
          onPointerLeave={() => {
            if (!dragRef.current) onHover(null);
          }}
          onDoubleClick={onReset}
        />
      </div>
    </section>
  );
});

/** One series: raw rows as a line / step / bars, or a min-max envelope. */
function drawLine(
  ctx: CanvasRenderingContext2D,
  data: LabWindow,
  line: PlotLine,
  x: (t: number) => number,
  y: (v: number) => number,
  view: View,
  plotW: number
) {
  const series = data.series[line.key];
  if (!series) return;
  const times = data.t;
  const style = line.style ?? "line";
  ctx.strokeStyle = line.color;
  ctx.fillStyle = line.color;
  ctx.lineWidth = 1.5;
  ctx.setLineDash(line.dash ?? []);
  const baseline = y(0);

  if (data.mode === "envelope") {
    const mins = series.min ?? [];
    const maxs = series.max ?? [];
    const means = series.mean ?? [];
    const bucketPx = Math.max(1, ((data.bucket_sec ?? 0) / (view.to - view.from || 1)) * plotW);
    if (style === "bar") {
      for (let i = 0; i < times.length; i += 1) {
        const top = maxs[i];
        if (top == null || top === 0) continue;
        const px = x(times[i]);
        ctx.fillRect(px - bucketPx / 2, Math.min(y(top), baseline), Math.max(1, bucketPx), Math.abs(baseline - y(top)) || 1);
      }
      ctx.setLineDash([]);
      return;
    }
    // Filled min..max band, broken at gaps, so a one-row spike still shows.
    ctx.globalAlpha = 0.32;
    let i = 0;
    while (i < times.length) {
      while (i < times.length && (mins[i] == null || maxs[i] == null)) i += 1;
      const start = i;
      while (i < times.length && mins[i] != null && maxs[i] != null) i += 1;
      if (i - start < 1) continue;
      ctx.beginPath();
      for (let k = start; k < i; k += 1) {
        const px = x(times[k]);
        const top = y(maxs[k] as number) - 0.5;
        if (k === start) ctx.moveTo(px, top);
        else ctx.lineTo(px, top);
      }
      for (let k = i - 1; k >= start; k -= 1) ctx.lineTo(x(times[k]), y(mins[k] as number) + 0.5);
      ctx.closePath();
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    strokeSeries(ctx, times, means, x, y, style === "step");
    ctx.setLineDash([]);
    return;
  }

  const values = series.v ?? [];
  const pxPerSample = times.length > 1 ? plotW / Math.max(1, times.length - 1) : plotW;
  if (style === "bar") {
    const barW = Math.min(6, Math.max(1, pxPerSample * 0.8));
    for (let i = 0; i < times.length; i += 1) {
      const value = values[i];
      if (value == null || value === 0) continue;
      ctx.fillRect(x(times[i]) - barW / 2, Math.min(y(value), baseline), barW, Math.abs(baseline - y(value)) || 1);
    }
    ctx.setLineDash([]);
    return;
  }
  strokeSeries(ctx, times, values, x, y, style === "step");
  ctx.setLineDash([]);
  // Zoomed in far enough that rows are distinct: mark each recorded sample.
  if (pxPerSample >= 6) {
    for (let i = 0; i < times.length; i += 1) {
      const value = values[i];
      if (value == null) continue;
      ctx.beginPath();
      ctx.arc(x(times[i]), y(value), 2, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

/** Polyline that lifts the pen at every null, so gaps stay gaps. */
function strokeSeries(
  ctx: CanvasRenderingContext2D,
  times: number[],
  values: Array<number | null>,
  x: (t: number) => number,
  y: (v: number) => number,
  step: boolean
) {
  ctx.beginPath();
  let pen = false;
  let lastY = 0;
  for (let i = 0; i < times.length; i += 1) {
    const value = values[i];
    if (value == null) {
      pen = false;
      continue;
    }
    const px = x(times[i]);
    const py = y(value);
    if (!pen) ctx.moveTo(px, py);
    else if (step) {
      ctx.lineTo(px, lastY);
      ctx.lineTo(px, py);
    } else ctx.lineTo(px, py);
    pen = true;
    lastY = py;
  }
  ctx.stroke();
}

/** Categorical strips: one row per state, coloured block per row / bucket. */
function drawStates(
  ctx: CanvasRenderingContext2D,
  data: LabWindow | null,
  states: StateRow[],
  g: Geometry,
  x: (t: number) => number,
  grid: string
) {
  const rowH = (g.bottom - g.top) / states.length;
  states.forEach((row, rowIndex) => {
    const top = g.top + rowH * rowIndex + 1;
    const h = Math.max(2, rowH - 2);
    const series = data?.series[row.key];
    const gate = row.gate ? data?.series[row.gate] : undefined;
    if (data && series) {
      const times = data.t;
      const half = data.mode === "envelope" ? (data.bucket_sec ?? 0) / 2 : 0;
      for (let i = 0; i < times.length; i += 1) {
        const value =
          data.mode === "raw" ? series.v?.[i] : row.worst === "min" ? series.min?.[i] : series.max?.[i];
        if (value == null) continue;
        // Worst verdict in this row / bucket. Exactly 1 means "no data":
        // the leg was not reporting, so the flag says nothing about health.
        const verdict = gate ? (data.mode === "raw" ? gate.v?.[i] : gate.max?.[i]) : null;
        const color = verdict === 1 ? NODATA_FILL : row.color(value);
        if (!color) continue;
        // A raw row lasts until the next row; a bucket covers its own span.
        const start = data.mode === "raw" ? times[i] : times[i] - half;
        const end = data.mode === "raw" ? (i + 1 < times.length ? times[i + 1] : times[i] + 0.05) : times[i] + half;
        const x0 = x(start);
        ctx.fillStyle = color;
        ctx.fillRect(x0, top, Math.max(1, x(end) - x0), h);
      }
    }
    ctx.strokeStyle = grid;
    ctx.globalAlpha = 0.5;
    ctx.beginPath();
    ctx.moveTo(g.left, Math.round(top + h + 1) + 0.5);
    ctx.lineTo(g.right, Math.round(top + h + 1) + 0.5);
    ctx.stroke();
    ctx.globalAlpha = 1;
  });
}
