import { useEffect, useId, useRef, useState, type PointerEvent } from "react";
import { LEG_ROWS, legJoint, type LegSide } from "./rightLeg";
import type { M5HistoryPoint } from "./types";
import "./CycleSweep.css";

/**
 * 脚タブ上部の制御タイムライン。
 *
 * 各軸カード右のグラフは、新しいサンプルが右へ積もる窓である。
 * こちらは 2 秒の窓を固定し、再生バーだけが左から右へ進む。
 * 右端に着いたら左へ戻り、まだ上書きしていない前の周は薄く残す。
 *
 * 印は、PC がフレームを受け取った時刻をその周期の終わりにして、
 * 指令送信 → 腰の指令 → 脚センサ の順に所要時間を左へ積む。
 * 脚が PWM を書く時刻は計測に無いので、ここには出さない。
 * 所要時間が 0 の接続では、3 段とも受信時刻の点になる。
 */

const WINDOW_S = 2;
const SLOT_COUNT = 5;
const CSS_H = 348;
const STORAGE_KEY = "m5-sweep-slots";

const MARKS = [
  { key: "sense", label: "脚センサ", color: "#54a0ff" },
  { key: "core", label: "腰の指令", color: "#ff9f43" },
  { key: "act", label: "指令送信", color: "#1dd1a1" },
] as const;

type MarkKey = (typeof MARKS)[number]["key"];
type FieldKey = "cmd" | "raw" | "corr" | "volt" | "amp";
type Ink = "bright" | "dim";

const FIELDS: { key: FieldKey; label: string; unit: string }[] = [
  { key: "cmd", label: "指令", unit: "°" },
  { key: "raw", label: "生角", unit: "°" },
  { key: "corr", label: "補正", unit: "°" },
  { key: "volt", label: "電圧", unit: "V" },
  { key: "amp", label: "電流", unit: "A" },
];

/** 段の色。同じ種類を 2 本選んでも線が重なって見えなくならないように、段ごとに固定する。 */
const SLOT_COLORS = ["#ff9f43", "#54a0ff", "#00d2d3", "#ff6b81", "#feca57"];

const DEFAULT_SLOTS = ["3:cmd", "3:raw", "4:amp", "0:cmd", "1:volt"];

type SlotSpec = {
  ch: number;
  field: FieldKey;
} | null;

type Props = {
  history: M5HistoryPoint[];
  /**
   * 再生中は記録の時刻 [s]。
   * null のときは壁時計で再生バーを進める（ライブ）。
   */
  clockSec: number | null;
  /** ライブのとき true。再生中は記録時刻に合わせ、壁時計では動かさない。 */
  live: boolean;
};

function loadSlots(): string[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    if (
      Array.isArray(parsed) &&
      parsed.length === SLOT_COUNT &&
      parsed.every((v) => typeof v === "string")
    ) {
      return parsed;
    }
  } catch {
    // 保存が読めないときは既定の 5 本に戻す。
  }
  return DEFAULT_SLOTS.slice();
}

function channelName(ch: number): string {
  const side: LegSide = ch >= 5 ? "left" : "right";
  const row = ch % LEG_ROWS.length;
  return `ch${ch} ${legJoint(side, row).label}`;
}

function parseSlot(raw: string): SlotSpec {
  if (!raw) return null;
  const [chText, field] = raw.split(":");
  const ch = Number(chText);
  const known = FIELDS.find((f) => f.key === field);
  if (!known || !Number.isInteger(ch) || ch < 0 || ch > 9) return null;
  return { ch, field: known.key };
}

function fieldMeta(field: FieldKey): { label: string; unit: string } {
  return FIELDS.find((f) => f.key === field) ?? { label: "指令", unit: "°" };
}

function sampleValue(point: M5HistoryPoint, spec: SlotSpec): number | null {
  if (!spec) return null;
  const xs = point[spec.field];
  const v = xs && spec.ch < xs.length ? xs[spec.ch] : undefined;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** 2 秒窓の中で、この時刻が今の周か、まだ残っている前の周か。 */
function inkOf(t: number, now: number): Ink | null {
  const lap = Math.floor(t / WINDOW_S);
  const nowLap = Math.floor(now / WINDOW_S);
  const phase = t - lap * WINDOW_S;
  const nowPhase = now - nowLap * WINDOW_S;
  if (lap === nowLap && phase <= nowPhase + 1e-4) return "bright";
  if (lap === nowLap - 1 && phase > nowPhase) return "dim";
  return null;
}

function phaseOf(t: number): number {
  return t - Math.floor(t / WINDOW_S) * WINDOW_S;
}

type Slice = { a: number; b: number; ink: Ink };

/** 区間を窓の境界と再生バーで割り、見える断片だけ返す。点（a===b）も 1 個になる。 */
function slices(t0: number, t1: number, now: number): Slice[] {
  const lo = Math.min(t0, t1);
  const hi = Math.max(t0, t1);
  const cuts = [lo, hi, now, now - WINDOW_S];
  let boundary = Math.ceil(lo / WINDOW_S) * WINDOW_S;
  while (boundary < hi) {
    cuts.push(boundary);
    boundary += WINDOW_S;
  }
  const uniq = cuts
    .filter((c) => c >= lo - 1e-9 && c <= hi + 1e-9)
    .sort((a, b) => a - b)
    .filter((c, i, arr) => {
      const prev = arr[i - 1];
      return i === 0 || prev === undefined || c - prev > 1e-6;
    });
  const first = uniq[0];
  if (uniq.length === 1 && first !== undefined) {
    const ink = inkOf(first, now);
    return ink ? [{ a: first, b: first, ink }] : [];
  }
  const out: Slice[] = [];
  for (let i = 0; i < uniq.length - 1; i++) {
    const a = uniq[i];
    const b = uniq[i + 1];
    if (a === undefined || b === undefined) continue;
    const ink = inkOf((a + b) / 2, now);
    if (ink) out.push({ a, b, ink });
  }
  return out;
}

function stageIntervals(point: M5HistoryPoint): { key: MarkKey; t0: number; t1: number }[] {
  // 受信時刻を終わりにして、送信・腰・センサの順に左へ戻す。
  let cursor = point.t;
  const act = Math.max(0, point.act_ms) / 1000;
  const core = Math.max(0, point.state_ms + point.policy_ms) / 1000;
  const sense = Math.max(0, point.sense_ms) / 1000;
  const rows: { key: MarkKey; dur: number }[] = [
    { key: "act", dur: act },
    { key: "core", dur: core },
    { key: "sense", dur: sense },
  ];
  return rows.map((row) => {
    const t1 = cursor;
    const t0 = cursor - row.dur;
    cursor = t0;
    return { key: row.key, t0, t1 };
  });
}

type PropsDraw = {
  ctx: CanvasRenderingContext2D;
  width: number;
  now: number;
  history: M5HistoryPoint[];
  slots: string[];
  hoverPhase: number | null;
};

function drawSweep(d: PropsDraw): void {
  const { ctx, width, now, history, slots, hoverPhase } = d;
  const gutter = width < 560 ? 78 : 118;
  const padR = 12;
  const plotW = Math.max(20, width - gutter - padR);
  const xOf = (t: number) => gutter + (phaseOf(t) / WINDOW_S) * plotW;
  const markH = 16;
  const markTop = 10;
  const laneTop = markTop + MARKS.length * markH + 10;
  const laneH = 46;
  const axisY = laneTop + SLOT_COUNT * (laneH + 4) + 4;

  ctx.clearRect(0, 0, width, CSS_H);
  ctx.font = "11px system-ui, sans-serif";
  ctx.textBaseline = "middle";

  // 0.5 秒ごとの縦格子。系列より先に描き、線の下に敷く。
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 1;
  for (let s = 0; s <= 4; s++) {
    const x = gutter + (s / 4) * plotW;
    ctx.beginPath();
    ctx.moveTo(x, markTop);
    ctx.lineTo(x, axisY - 8);
    ctx.stroke();
  }

  for (let i = 0; i < MARKS.length; i++) {
    const mark = MARKS[i];
    if (!mark) continue;
    const y = markTop + i * markH + markH / 2;
    ctx.fillStyle = "#8b9bb0";
    ctx.textAlign = "right";
    ctx.fillText(mark.label, gutter - 8, y);
  }

  for (const point of history) {
    const colorOf = (key: MarkKey) => MARKS.find((m) => m.key === key)?.color ?? "#8b9bb0";
    for (const span of stageIntervals(point)) {
      const y = markTop + MARKS.findIndex((m) => m.key === span.key) * markH + markH / 2;
      const color = point.overrun ? "#ff6b6b" : colorOf(span.key);
      for (const slice of slices(span.t0, span.t1, now)) {
        ctx.globalAlpha = slice.ink === "bright" ? 1 : 0.35;
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        const x0 = xOf(slice.a);
        const x1 = xOf(slice.b);
        ctx.beginPath();
        if (Math.abs(x1 - x0) < 1.5) {
          ctx.moveTo(x1, y - 5);
          ctx.lineTo(x1, y + 5);
        } else {
          ctx.moveTo(x0, y);
          ctx.lineTo(x1, y);
        }
        ctx.stroke();
      }
    }
  }
  ctx.globalAlpha = 1;

  slots.forEach((raw, index) => {
    const spec = parseSlot(raw);
    const top = laneTop + index * (laneH + 4);
    const meta = spec ? fieldMeta(spec.field) : null;
    const title = spec ? `ch${spec.ch} ${meta?.label ?? ""}` : "空";
    ctx.fillStyle = "#c5d0dc";
    ctx.textAlign = "right";
    ctx.fillText(title, gutter - 8, top + 12);
    ctx.fillStyle = SLOT_COLORS[index] ?? "#f5f6fa";
    ctx.fillRect(gutter - 8 - ctx.measureText(title).width - 12, top + 8, 8, 8);

    const pts: { t: number; v: number; ink: Ink }[] = [];
    if (spec) {
      for (const point of history) {
        const v = sampleValue(point, spec);
        if (v == null) continue;
        const ink = inkOf(point.t, now);
        if (!ink) continue;
        pts.push({ t: point.t, v, ink });
      }
    }
    pts.sort((a, b) => a.t - b.t);

    let lo = Infinity;
    let hi = -Infinity;
    for (const p of pts) {
      lo = Math.min(lo, p.v);
      hi = Math.max(hi, p.v);
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
      lo = 0;
      hi = 1;
    }
    if (hi - lo < 1e-6) {
      lo -= 1;
      hi += 1;
    } else {
      const pad = (hi - lo) * 0.12;
      lo -= pad;
      hi += pad;
    }
    const yOf = (v: number) => top + 8 + ((hi - v) / (hi - lo)) * (laneH - 16);
    ctx.fillStyle = "#8b9bb0";
    ctx.textAlign = "right";
    const unit = meta?.unit ?? "";
    // サンプルが無い段に 0〜1 の仮目盛りを出すと、測った値に見える。
    if (pts.length) {
      ctx.fillText(`${hi.toFixed(Math.abs(hi) >= 20 ? 0 : 1)}${unit}`, gutter - 8, top + 26);
    }

    ctx.strokeStyle = "rgba(255,255,255,0.1)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(gutter, yOf(hi));
    ctx.lineTo(gutter + plotW, yOf(hi));
    ctx.moveTo(gutter, yOf(lo));
    ctx.lineTo(gutter + plotW, yOf(lo));
    ctx.stroke();

    if (!pts.length) {
      ctx.fillStyle = "#5c6b7c";
      ctx.textAlign = "left";
      ctx.fillText(spec ? "この窓には無い" : "表示しない", gutter + 8, top + laneH / 2);
      return;
    }

    ctx.lineWidth = 1.7;
    ctx.strokeStyle = SLOT_COLORS[index] ?? "#f5f6fa";
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    let run: { t: number; v: number; ink: Ink }[] = [];
    const flush = () => {
      const head = run[0];
      if (run.length < 2 || !head) {
        run = [];
        return;
      }
      ctx.globalAlpha = head.ink === "bright" ? 1 : 0.35;
      ctx.beginPath();
      run.forEach((p, i) => {
        const x = xOf(p.t);
        const y = yOf(p.v);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      run = [];
    };
    for (const p of pts) {
      const prev = run[run.length - 1];
      const broke =
        !prev ||
        prev.ink !== p.ink ||
        p.t - prev.t > 0.25 ||
        phaseOf(p.t) + 1e-4 < phaseOf(prev.t);
      if (broke) flush();
      run.push(p);
    }
    flush();
    ctx.globalAlpha = 1;
  });

  ctx.fillStyle = "#8b9bb0";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let s = 0; s <= 4; s++) {
    const x = gutter + (s / 4) * plotW;
    ctx.textAlign = s === 0 ? "left" : s === 4 ? "right" : "center";
    ctx.fillText(`${(s * 0.5).toFixed(1)} s`, x, axisY);
  }

  const playX = gutter + (phaseOf(now) / WINDOW_S) * plotW;
  ctx.strokeStyle = "#f5f6fa";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(playX, markTop - 2);
  ctx.lineTo(playX, axisY - 6);
  ctx.stroke();
  ctx.fillStyle = "#f5f6fa";
  ctx.beginPath();
  ctx.moveTo(playX - 5, markTop - 2);
  ctx.lineTo(playX + 5, markTop - 2);
  ctx.lineTo(playX, markTop + 5);
  ctx.fill();

  if (hoverPhase != null) {
    const hx = gutter + (hoverPhase / WINDOW_S) * plotW;
    ctx.strokeStyle = "rgba(245,246,250,0.45)";
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(hx, markTop);
    ctx.lineTo(hx, axisY - 6);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function hoverText(history: M5HistoryPoint[], slots: string[], now: number, phase: number): string {
  // 見えている周のなかで、カーソルに一番近いサンプルを読む。
  let best: M5HistoryPoint | null = null;
  let bestDist = Infinity;
  for (const point of history) {
    if (inkOf(point.t, now) == null) continue;
    const dist = Math.abs(phaseOf(point.t) - phase);
    if (dist < bestDist) {
      best = point;
      bestDist = dist;
    }
  }
  const head = `${phase.toFixed(2)} s`;
  if (!best || bestDist > 0.08) return head;
  const parts = slots.map((raw) => {
    const spec = parseSlot(raw);
    if (!spec) return null;
    const v = sampleValue(best, spec);
    if (v == null) return null;
    const meta = fieldMeta(spec.field);
    return `ch${spec.ch} ${meta.label} ${v.toFixed(1)}${meta.unit}`;
  });
  return [head, ...parts.filter((p): p is string => Boolean(p))].join(" · ");
}

export function CycleSweep({ history, clockSec, live }: Props) {
  const reactId = useId();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const readoutRef = useRef<HTMLParagraphElement | null>(null);
  const historyRef = useRef(history);
  const slotsRef = useRef<string[]>(DEFAULT_SLOTS);
  const hoverRef = useRef<number | null>(null);
  const paintRef = useRef<() => void>(() => {});
  const clockRef = useRef(clockSec);
  const liveRef = useRef(live);
  historyRef.current = history;
  clockRef.current = clockSec;
  liveRef.current = live;

  const [slots, setSlots] = useState<string[]>(loadSlots);
  const [width, setWidth] = useState(0);
  slotsRef.current = slots;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const apply = () => setWidth(el.clientWidth);
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || width < 40) return;
    let raf = 0;
    // サンプルの t は Unix 秒。再生バーも同じ時計にしないと、波形と印がずれる。
    // requestAnimationFrame の時刻はページを開いてからの秒なので、ここでは使わない。
    const paint = () => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const dpr = window.devicePixelRatio || 1;
      const pxW = Math.floor(width * dpr);
      const pxH = Math.floor(CSS_H * dpr);
      if (canvas.width !== pxW || canvas.height !== pxH) {
        canvas.width = pxW;
        canvas.height = pxH;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const now = liveRef.current ? Date.now() / 1000 : (clockRef.current ?? Date.now() / 1000);
      drawSweep({
        ctx,
        width,
        now,
        history: historyRef.current,
        slots: slotsRef.current,
        hoverPhase: hoverRef.current,
      });
      if (readoutRef.current) {
        const phase = phaseOf(now);
        const hover = hoverRef.current;
        readoutRef.current.textContent =
          hover == null
            ? `${phase.toFixed(2)} / ${WINDOW_S.toFixed(2)} 秒`
            : hoverText(historyRef.current, slotsRef.current, now, hover);
      }
    };
    paintRef.current = paint;
    if (!live) {
      paint();
      return;
    }
    const loop = () => {
      paint();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
    // history は ref 経由で毎フレーム読む。依存に入れると 20 Hz でループを作り直す。
    // 再生中は clockSec が変わるので、止めた時刻でも描き直す。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, live, clockSec, slots]);

  const onPointer = (event: PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || width < 40) return;
    const gutter = width < 560 ? 78 : 118;
    const plotW = Math.max(20, width - gutter - 12);
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const phase = ((x - gutter) / plotW) * WINDOW_S;
    hoverRef.current = phase >= 0 && phase <= WINDOW_S ? phase : null;
    if (!liveRef.current) paintRef.current();
  };

  const options = FIELDS.flatMap((field) =>
    Array.from({ length: 10 }, (_, ch) => ({
      value: `${ch}:${field.key}`,
      label: `${channelName(ch)} ${field.label}`,
    }))
  );

  return (
    <section className="m5-sweep" aria-label="制御タイムライン">
      <div className="m5-sweep__head">
        <div>
          <h2>制御タイムライン</h2>
          <p>
            2.0 秒で左から右へ進み、右端で左に戻る。印は受信時刻を周期の終わりにした所要時間。脚が PWM
            を書く時刻は含まない。
          </p>
        </div>
        <p className="m5-sweep__readout" ref={readoutRef}>
          0.00 / 2.00 秒
        </p>
      </div>
      <div className="m5-sweep__picks">
        {slots.map((value, index) => (
          <label key={index}>
            表示 {index + 1}
            <select
              id={`${reactId}-slot-${index}`}
              value={options.some((o) => o.value === value) ? value : ""}
              onChange={(e) => {
                const next = slots.slice();
                next[index] = e.target.value;
                setSlots(next);
                try {
                  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
                } catch {
                  // 保存できなくても、この表示のあいだは選んだ段のまま。
                }
              }}
            >
              <option value="">表示しない</option>
              {options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <div className="m5-sweep__canvas" ref={wrapRef}>
        <canvas
          ref={canvasRef}
          className="m5-sweep__plot"
          role="img"
          aria-label="2秒の制御タイムライン。上段が処理の印、下が選んだ値。再生バーは左から右へ進む。"
          onPointerMove={onPointer}
          onPointerLeave={() => {
            hoverRef.current = null;
            if (!liveRef.current) paintRef.current();
          }}
        />
      </div>
      <div className="m5-sweep__legend">
        {MARKS.map((m) => (
          <span key={m.key}>
            <i style={{ background: m.color }} />
            {m.label}
          </span>
        ))}
        <span className="m5-sweep__legend-note">赤は overrun。薄く残る線は、前の周でまだ上書きされていない部分。</span>
      </div>
    </section>
  );
}
