/**
 * Health map: lanes (each joint, then link / timing / I2C / servo / feet /
 * events) against time for the whole take. Colour is the worst severity
 * in each bucket, intensity the share of bad rows, black means nothing was
 * received. The current plot range is the bright window; everything else
 * is dimmed.
 *
 * This is the "where is it broken" view: drag to zoom the plots, click a
 * cell to jump there (and focus that joint), click a joint label to focus.
 */

import { memo, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { KIND_LABEL, L, LANE_LABEL, SEVERITY_LABEL, fmt } from "../labels";
import type { LabAnalysis, LabHealthLane } from "../types";
import { LABEL_FONT, MONO_FONT, SEV_COLOR, readTheme, setupCanvas, useElementWidth } from "./canvas";
import { formatNumber, formatOffset, timeTicks, type View } from "./plotMath";

type Props = {
  analysis: LabAnalysis;
  view: View;
  hoverT: number | null;
  cursorT: number | null;
  focusJoint: number;
  onHover: (t: number | null) => void;
  onPick: (t: number, lane: LabHealthLane | null) => void;
  onView: (view: View) => void;
  onReset: () => void;
  onFocusJoint: (joint: number) => void;
};

const LABEL_W = 156;
const RIGHT_PAD = 10;
const SPARK_H = 34;
const EVENT_H = 12;
const GROUP_H = 18;
const ROW_H = 14;
const AXIS_H = 18;

type Row =
  | { type: "group"; label: string; y: number; h: number }
  | { type: "lane"; lane: LabHealthLane; label: string; y: number; h: number };

/** Fill for one cell from severity, bad-row share and whether anything arrived. */
function cellColor(sev: number, ratio: number, samples: number): string {
  if (samples === 0) return "#04070b";
  // Even one bad row in a bucket must be visible, so intensity starts high.
  const strength = Math.min(1, ratio * 4);
  if (sev >= 3) return `rgba(255, 82, 82, ${0.45 + 0.55 * strength})`;
  if (sev === 2) return `rgba(255, 176, 32, ${0.35 + 0.55 * strength})`;
  if (sev === 1) return "rgba(120, 135, 155, 0.30)";
  return "rgba(61, 220, 132, 0.13)";
}

export const HealthMap = memo(function HealthMap({
  analysis,
  view,
  hoverT,
  cursorT,
  focusJoint,
  onHover,
  onPick,
  onView,
  onReset,
  onFocusJoint,
}: Props) {
  const frameRef = useRef<HTMLDivElement>(null);
  const baseRef = useRef<HTMLCanvasElement>(null);
  const overRef = useRef<HTMLCanvasElement>(null);
  const width = useElementWidth(frameRef);
  const [tip, setTip] = useState<{ x: number; y: number; lines: string[] } | null>(null);
  const dragRef = useRef<{ startX: number; moved: boolean } | null>(null);
  const [dragBox, setDragBox] = useState<[number, number] | null>(null);

  const health = analysis.health;
  const duration = Math.max(analysis.duration_sec, 1e-6);
  const kinds = analysis.kinds;

  // Vertical layout: sparkline, event ticks, then grouped lanes.
  const { rows, height, eventsTop } = useMemo(() => {
    const out: Row[] = [];
    let y = SPARK_H + EVENT_H + 4;
    const eventsTopAt = SPARK_H + 2;
    const byId = new Map(health.lanes.map((lane) => [lane.id, lane]));
    const group = (label: string, ids: string[]) => {
      out.push({ type: "group", label, y, h: GROUP_H });
      y += GROUP_H;
      for (const id of ids) {
        const lane = byId.get(id);
        if (!lane) continue;
        const label =
          lane.joint != null ? `${lane.joint} ${analysis.joint_names[lane.joint] ?? ""}` : LANE_LABEL[id] ?? id;
        out.push({ type: "lane", lane, label, y, h: ROW_H });
        y += ROW_H;
      }
    };
    group(L.groupRight, ["j0", "j1", "j2", "j3", "j4"]);
    group(L.groupLeft, ["j5", "j6", "j7", "j8", "j9"]);
    group(L.groupSystem, ["link", "timing", "i2c", "servo", "foot", "foot_left", "policy", "events"]);
    return { rows: out, height: y + AXIS_H, eventsTop: eventsTopAt };
  }, [health.lanes, analysis.joint_names]);

  const plotLeft = LABEL_W;
  const plotRight = Math.max(LABEL_W + 10, width - RIGHT_PAD);
  const plotW = plotRight - plotLeft;
  const x = (t: number) => plotLeft + (t / duration) * plotW;
  const tAt = (px: number) => Math.min(Math.max(((px - plotLeft) / Math.max(1, plotW)) * duration, 0), duration);

  // ----- base layer: cells, labels, sparklines, events, axis -----------
  useEffect(() => {
    const canvas = baseRef.current;
    if (!canvas || width <= 0) return;
    const ctx = setupCanvas(canvas, width, height);
    if (!ctx) return;
    const theme = readTheme();
    const buckets = health.buckets;
    // Several buckets can share a pixel column. Aggregate so the worst one
    // wins instead of whichever happened to be drawn last.
    const columns = Math.max(1, Math.min(buckets, Math.floor(plotW)));
    const colW = plotW / columns;
    const colOf = (bucket: number) => Math.min(columns - 1, Math.floor((bucket * columns) / buckets));
    const colSamples = new Array<number>(columns).fill(0);
    health.samples.forEach((count, bucket) => {
      colSamples[colOf(bucket)] += count;
    });

    for (const row of rows) {
      if (row.type === "group") {
        ctx.fillStyle = theme.muted;
        ctx.font = `600 ${LABEL_FONT}`;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(row.label, 6, row.y + row.h / 2 + 1);
        continue;
      }
      const lane = row.lane;
      const focused = lane.joint === focusJoint;
      if (focused) {
        ctx.fillStyle = "rgba(77, 166, 255, 0.12)";
        ctx.fillRect(0, row.y, width, row.h);
      }
      ctx.fillStyle = focused ? theme.accent : theme.text;
      ctx.font = focused ? `600 ${LABEL_FONT}` : LABEL_FONT;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(row.label, 14, row.y + row.h / 2 + 0.5, LABEL_W - 18);

      const sev = new Array<number>(columns).fill(0);
      const ratio = new Array<number>(columns).fill(0);
      const out = new Array<number>(columns).fill(0);
      for (let bucket = 0; bucket < buckets; bucket += 1) {
        const col = colOf(bucket);
        if (lane.sev[bucket] > sev[col]) sev[col] = lane.sev[bucket];
        if (lane.ratio[bucket] > ratio[col]) ratio[col] = lane.ratio[bucket];
        const share = lane.out?.[bucket];
        if (share != null && share > out[col]) out[col] = share;
      }
      for (let col = 0; col < columns; col += 1) {
        ctx.fillStyle = cellColor(sev[col], ratio[col], colSamples[col]);
        ctx.fillRect(plotLeft + col * colW, row.y + 1, Math.ceil(colW), row.h - 2);
        if (out[col] > 0) {
          ctx.fillStyle = `rgba(77, 166, 255, ${0.35 + 0.6 * out[col]})`;
          ctx.fillRect(plotLeft + col * colW, row.y + row.h - 3, Math.ceil(colW), 2);
        }
      }
    }

    // Sparklines: total current (area) and worst driven tracking error (line).
    drawSpark(ctx, health.overview.amp_total_max ?? [], plotLeft, plotW, 2, SPARK_H - 4, "rgba(255, 209, 102, 0.55)", true);
    drawSpark(ctx, health.overview.err_driven_max ?? [], plotLeft, plotW, 2, SPARK_H - 4, "#ff7a7a", false);
    const ampMax = Math.max(0, ...(health.overview.amp_total_max ?? []).map((v) => v ?? 0));
    const errMax = Math.max(0, ...(health.overview.err_driven_max ?? []).map((v) => v ?? 0));
    ctx.font = LABEL_FONT;
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(255, 209, 102, 0.9)";
    ctx.fillText(`${L.overviewAmp} ${formatNumber(ampMax, 2)} A`, 6, 3);
    ctx.fillStyle = "#ff7a7a";
    ctx.fillText(`${L.overviewErr} ${formatNumber(errMax, 1)}${L.deg}`, 6, 17);

    // Event ticks: errors full height, warnings half.
    for (const event of analysis.events) {
      if (event.offset == null || event.level === "info") continue;
      const px = Math.round(x(event.offset)) + 0.5;
      ctx.strokeStyle = event.level === "error" ? SEV_COLOR[3] : "rgba(255, 176, 32, 0.6)";
      ctx.beginPath();
      ctx.moveTo(px, eventsTop + (event.level === "error" ? 0 : EVENT_H / 2));
      ctx.lineTo(px, eventsTop + EVENT_H);
      ctx.stroke();
    }

    // Time axis.
    const axisTop = height - AXIS_H;
    const { step, ticks } = timeTicks({ from: 0, to: duration }, Math.max(2, Math.floor(plotW / 90)));
    ctx.fillStyle = theme.muted;
    ctx.font = MONO_FONT;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const tick of ticks) ctx.fillText(formatOffset(tick, step), x(tick), axisTop + 4);
  }, [width, height, rows, health, analysis.events, focusJoint, duration, plotW, plotLeft, eventsTop]);

  // ----- overlay: view window, cursor, hover, drag ---------------------
  useEffect(() => {
    const canvas = overRef.current;
    if (!canvas || width <= 0) return;
    const ctx = setupCanvas(canvas, width, height);
    if (!ctx) return;
    const theme = readTheme();
    const top = SPARK_H;
    const bottom = height - AXIS_H;
    const vx0 = x(view.from);
    const vx1 = x(view.to);
    const whole = view.from <= 1e-6 && view.to >= duration - 1e-6;
    if (!whole) {
      ctx.fillStyle = "rgba(4, 7, 11, 0.55)";
      ctx.fillRect(plotLeft, 0, Math.max(0, vx0 - plotLeft), bottom);
      ctx.fillRect(vx1, 0, Math.max(0, plotRight - vx1), bottom);
      ctx.strokeStyle = theme.accent;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(vx0, 1, Math.max(2, vx1 - vx0), bottom - 2);
      ctx.lineWidth = 1;
    }
    if (dragBox) {
      const [a, b] = dragBox;
      ctx.fillStyle = "rgba(77, 166, 255, 0.2)";
      ctx.fillRect(Math.min(a, b), top, Math.abs(b - a), bottom - top);
    }
    const line = (t: number, color: string, dash: number[]) => {
      const px = Math.round(x(t)) + 0.5;
      ctx.strokeStyle = color;
      ctx.setLineDash(dash);
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, bottom);
      ctx.stroke();
      ctx.setLineDash([]);
    };
    if (cursorT != null) line(cursorT, "rgba(255, 255, 255, 0.9)", []);
    if (hoverT != null) line(hoverT, theme.muted, [3, 3]);
  }, [width, height, view, hoverT, cursorT, dragBox, duration, plotLeft, plotRight]);

  const laneAt = (py: number): LabHealthLane | null => {
    for (const row of rows) {
      if (row.type === "lane" && py >= row.y && py < row.y + row.h) return row.lane;
    }
    return null;
  };

  /** Tooltip lines for one cell: lane, time span, verdict, share. */
  const describe = (lane: LabHealthLane, t: number): string[] => {
    const bucket = Math.min(health.buckets - 1, Math.max(0, Math.floor(t / health.bucket_sec)));
    const start = bucket * health.bucket_sec;
    const end = start + health.bucket_sec;
    const name = lane.joint != null ? `${lane.joint} ${analysis.joint_names[lane.joint] ?? ""}` : LANE_LABEL[lane.id] ?? lane.id;
    const lines = [name, `${formatOffset(start, 0.1)} \u2013 ${formatOffset(end, 0.1)}`];
    if (health.samples[bucket] === 0) {
      lines.push(L.noSamples);
      return lines;
    }
    const sev = lane.sev[bucket];
    const kind = kinds[lane.kind[bucket]] ?? "";
    lines.push(sev ? `${SEVERITY_LABEL[sev]}: ${KIND_LABEL[kind] ?? kind}` : SEVERITY_LABEL[0]);
    if (sev >= 2) lines.push(fmt(L.ratioOfBucket, { pct: Math.round(lane.ratio[bucket] * 100) }));
    const share = lane.out?.[bucket];
    if (share) lines.push(`${L.outOn} ${Math.round(share * 100)}%`);
    return lines;
  };

  const local = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return { px: event.clientX - rect.left, py: event.clientY - rect.top };
  };

  const handleDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0) return;
    const { px, py } = local(event);
    if (px < plotLeft) {
      const lane = laneAt(py);
      if (lane?.joint != null) onFocusJoint(lane.joint);
      return;
    }
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      /* Pointer already gone; the drag still works inside the canvas. */
    }
    dragRef.current = { startX: Math.min(px, plotRight), moved: false };
  };

  const handleMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const { px, py } = local(event);
    const clamped = Math.min(Math.max(px, plotLeft), plotRight);
    const drag = dragRef.current;
    if (drag) {
      if (Math.abs(clamped - drag.startX) > 4) drag.moved = true;
      if (drag.moved) setDragBox([drag.startX, clamped]);
    }
    if (px < plotLeft) {
      onHover(null);
      setTip(null);
      return;
    }
    const t = tAt(clamped);
    onHover(t);
    const lane = laneAt(py);
    setTip(lane ? { x: px, y: py, lines: describe(lane, t) } : null);
  };

  const handleUp = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    dragRef.current = null;
    setDragBox(null);
    if (!drag) return;
    const { px, py } = local(event);
    const clamped = Math.min(Math.max(px, plotLeft), plotRight);
    if (drag.moved) {
      onView({ from: tAt(Math.min(drag.startX, clamped)), to: tAt(Math.max(drag.startX, clamped)) });
    } else {
      onPick(tAt(clamped), laneAt(py));
    }
  };

  return (
    <div className="lab-health" ref={frameRef}>
      <div className="lab-health-frame" style={{ height }}>
        <canvas ref={baseRef} className="lab-plot-canvas" />
        <canvas
          ref={overRef}
          className="lab-plot-canvas lab-plot-overlay lab-health-overlay"
          onPointerDown={handleDown}
          onPointerMove={handleMove}
          onPointerUp={handleUp}
          onPointerCancel={handleUp}
          onPointerLeave={() => {
            setTip(null);
            if (!dragRef.current) onHover(null);
          }}
          onDoubleClick={onReset}
        />
        {tip ? (
          <div
            className="lab-health-tip"
            style={{
              left: Math.min(tip.x + 14, Math.max(0, width - 230)),
              top: tip.y + 14,
            }}
          >
            {tip.lines.map((text, index) => (
              <p key={index} className={index === 0 ? "lab-health-tip-title" : undefined}>
                {text}
              </p>
            ))}
          </div>
        ) : null}
      </div>
      <ul className="lab-health-legend">
        <li>
          <span className="lab-swatch" style={{ background: "rgba(61, 220, 132, 0.35)" }} />
          {L.legendOk}
        </li>
        <li>
          <span className="lab-swatch" style={{ background: "rgba(120, 135, 155, 0.6)" }} />
          {L.legendInfo}
        </li>
        <li>
          <span className="lab-swatch" style={{ background: SEV_COLOR[2] }} />
          {L.legendWarn}
        </li>
        <li>
          <span className="lab-swatch" style={{ background: SEV_COLOR[3] }} />
          {L.legendCrit}
        </li>
        <li>
          <span className="lab-swatch" style={{ background: "#04070b", border: "1px solid var(--border)" }} />
          {L.legendGap}
        </li>
        <li>
          <span className="lab-swatch lab-swatch-line" style={{ background: "rgba(77, 166, 255, 0.9)" }} />
          {L.outOn}
        </li>
      </ul>
    </div>
  );
});

/** Tiny bucketed sparkline, normalised to its own maximum. */
function drawSpark(
  ctx: CanvasRenderingContext2D,
  values: Array<number | null>,
  left: number,
  width: number,
  top: number,
  height: number,
  color: string,
  area: boolean
) {
  const peak = Math.max(0, ...values.map((value) => value ?? 0));
  if (!values.length || peak <= 0) return;
  const step = width / values.length;
  const bottom = top + height;
  ctx.beginPath();
  let pen = false;
  values.forEach((value, index) => {
    const px = left + (index + 0.5) * step;
    if (value == null) {
      if (area && pen) ctx.lineTo(px, bottom);
      pen = false;
      return;
    }
    const py = bottom - (value / peak) * height;
    if (!pen) {
      if (area) {
        ctx.moveTo(px, bottom);
        ctx.lineTo(px, py);
      } else ctx.moveTo(px, py);
    } else ctx.lineTo(px, py);
    pen = true;
  });
  if (area) {
    ctx.lineTo(left + width, bottom);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  } else {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.lineWidth = 1;
  }
}
