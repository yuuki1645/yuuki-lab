/**
 * 関節カード用の校正マップ。
 * 点列はボードの map_get で届く。USB を占有するので、同時に取るのは 1 関節だけ。
 */
import { useEffect, useRef, useState } from "react";
import { M5_COLORS, type M5Cal, type M5CalPoint, type M5Cmd } from "./types";

const FETCH_MS = 12000;

export type CalMapPhase = "ready" | "empty" | "busy" | "wait" | "error" | "offline";

type Cache = Record<number, M5CalPoint[]>;

export function useJointCalMaps(cal: M5Cal | null, send: (cmd: M5Cmd) => void, canCmd: boolean) {
  const [maps, setMaps] = useState<Cache>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const mapsRef = useRef<Cache>({});
  const busyRef = useRef<number | null>(null);
  const waitRef = useRef<number[]>([]);
  const sendRef = useRef(send);
  const canCmdRef = useRef(canCmd);
  sendRef.current = send;
  canCmdRef.current = canCmd;

  const remember = (ch: number, pts: M5CalPoint[]) => {
    mapsRef.current = { ...mapsRef.current, [ch]: pts };
    setMaps(mapsRef.current);
  };

  const pumpRef = useRef<(prefer?: number) => void>(() => {});
  pumpRef.current = (prefer?: number) => {
    if (busyRef.current !== null) {
      if (prefer !== undefined && prefer !== busyRef.current && !waitRef.current.includes(prefer)) {
        waitRef.current = [...waitRef.current, prefer];
      }
      return;
    }
    if (!canCmdRef.current) {
      if (prefer !== undefined && !waitRef.current.includes(prefer)) {
        waitRef.current = [...waitRef.current, prefer];
      }
      return;
    }
    const q = [...waitRef.current];
    let ch = prefer;
    if (ch === undefined) ch = q.shift();
    else {
      const i = q.indexOf(ch);
      if (i >= 0) q.splice(i, 1);
    }
    while (ch !== undefined && mapsRef.current[ch] !== undefined) ch = q.shift();
    waitRef.current = q;
    if (ch === undefined) return;
    busyRef.current = ch;
    setBusy(ch);
    setNotes((prev) => {
      if (!prev[ch!]) return prev;
      const next = { ...prev };
      delete next[ch!];
      return next;
    });
    sendRef.current({ op: "map_get", ch });
  };

  useEffect(() => {
    if (!cal) return;
    const ch = Number(cal.map_ch);
    if (!Number.isFinite(ch)) return;
    const pts = Array.isArray(cal.map_points) ? cal.map_points : [];
    const answered = busyRef.current === ch;
    // 起動時の空イベントで、まだ取っていない関節を「なし」にしない
    if (pts.length < 2 && !answered) return;
    remember(ch, pts);
    if (!answered) return;
    busyRef.current = null;
    setBusy(null);
    pumpRef.current();
  }, [cal]);

  useEffect(() => {
    if (busy === null) return;
    const ch = busy;
    const timer = window.setTimeout(() => {
      if (busyRef.current !== ch) return;
      busyRef.current = null;
      setBusy(null);
      setNotes((prev) => ({
        ...prev,
        [ch]: "取得がタイムアウトしました。",
      }));
      pumpRef.current();
    }, FETCH_MS);
    return () => window.clearTimeout(timer);
  }, [busy]);

  const ask = (ch: number, mapOk: boolean | undefined, force = false) => {
    const cached = mapsRef.current[ch];
    if (!force && cached && cached.length >= 2) return;
    if (!force && cached && cached.length === 0 && mapOk !== true) return;
    if (cached && (force || mapOk === true)) {
      const next = { ...mapsRef.current };
      delete next[ch];
      mapsRef.current = next;
      setMaps(next);
    }
    if (!force && mapOk === false) {
      remember(ch, []);
      return;
    }
    if (busyRef.current === ch) return;
    pumpRef.current(ch);
  };

  const phaseOf = (ch: number): CalMapPhase => {
    const pts = maps[ch];
    if (pts && pts.length >= 2) return "ready";
    if (pts && pts.length === 0) return "empty";
    if (notes[ch]) return "error";
    if (!canCmd && busy !== ch) return "offline";
    if (busy !== null && busy !== ch) return "wait";
    return "busy";
  };

  return { maps, notes, phaseOf, ask };
}

type PlotProps = {
  phase: CalMapPhase;
  points: M5CalPoint[];
  note: string;
  cmd: number | null;
  unwrap: number | null;
  onRetry: () => void;
};

function finite(v: number | null | undefined): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function tickLabel(v: number): string {
  if (Math.abs(v - Math.round(v)) < 0.05) return String(Math.round(v));
  return v.toFixed(1);
}

/** 横軸はサーボ角、縦軸はマップに入っている unwrap（360° をまたいで連続）。 */
function MapCurve({ points, cmd, unwrap }: { points: M5CalPoint[]; cmd: number | null; unwrap: number | null }) {
  const servos = points.map((p) => p.servo).filter(finite);
  const angs = points.map((p) => p.as5600).filter(finite);
  if (servos.length < 2 || angs.length < 2) return null;
  let x0 = Math.min(...servos);
  let x1 = Math.max(...servos);
  let y0 = Math.min(...angs);
  let y1 = Math.max(...angs);
  if (x1 - x0 < 1) {
    x0 -= 1;
    x1 += 1;
  }
  if (y1 - y0 < 1) {
    y0 -= 1;
    y1 += 1;
  }
  const w = 320;
  const h = 148;
  const padL = 46;
  const padR = 10;
  const padT = 10;
  const padB = 22;
  const sx = (x: number) => padL + ((x - x0) / (x1 - x0)) * (w - padL - padR);
  const sy = (y: number) => padT + (1 - (y - y0) / (y1 - y0)) * (h - padT - padB);
  const sorted = [...points].filter((p) => finite(p.servo) && finite(p.as5600)).sort((a, b) => a.servo - b.servo);
  const d = sorted
    .map((p, i) => `${i === 0 ? "M" : "L"}${sx(p.servo).toFixed(1)},${sy(p.as5600).toFixed(1)}`)
    .join(" ");
  const cmdV = finite(cmd) ? cmd : null;
  const angV = finite(unwrap) ? unwrap : null;
  const cmdOn = cmdV !== null && cmdV >= x0 && cmdV <= x1;
  const angOn = angV !== null && angV >= y0 && angV <= y1;
  const xTicks = [x0, (x0 + x1) / 2, x1];
  return (
    <svg className="m5-calmap__svg" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="校正マップ">
      <text x={4} y={sy(y1) + 3} fill="#8b9bb0" fontSize="10">
        {tickLabel(y1)}
      </text>
      <text x={4} y={sy(y0) + 3} fill="#8b9bb0" fontSize="10">
        {tickLabel(y0)}
      </text>
      {xTicks.map((x) => (
        <text key={x} x={sx(x)} y={h - 6} fill="#8b9bb0" fontSize="10" textAnchor="middle">
          {tickLabel(x)}
        </text>
      ))}
      <path d={d} fill="none" stroke={M5_COLORS.unwrap} strokeWidth="1.75" />
      {cmdOn && cmdV !== null ? (
        <line
          x1={sx(cmdV)}
          x2={sx(cmdV)}
          y1={padT}
          y2={h - padB}
          stroke={M5_COLORS.cmd}
          strokeWidth="1"
          strokeDasharray="3 3"
        />
      ) : null}
      {cmdOn && angOn && cmdV !== null && angV !== null ? (
        <circle cx={sx(cmdV)} cy={sy(angV)} r="3.6" fill={M5_COLORS.cmd} />
      ) : null}
    </svg>
  );
}

export function JointCalMap({ phase, points, note, cmd, unwrap, onRetry }: PlotProps) {
  const cmdText = finite(cmd) ? `${cmd.toFixed(1)}°` : "—";
  const angText = finite(unwrap) ? `${unwrap.toFixed(1)}°` : "—";
  return (
    <div className="m5-calmap">
      {phase === "ready" ? (
        <>
          <MapCurve points={points} cmd={cmd} unwrap={unwrap} />
          <p className="m5-calmap__cap">
            {points.length}点 · 横 サーボ° · 縦 unwrap° · いまの指令 {cmdText} / unwrap {angText}
          </p>
        </>
      ) : null}
      {phase === "empty" ? <p className="m5-calmap__cap">この関節の校正マップはありません。</p> : null}
      {phase === "busy" ? (
        <p className="m5-calmap__cap">ボードから取得しています。このあいだテレメトリは少し止まります。</p>
      ) : null}
      {phase === "wait" ? <p className="m5-calmap__cap">ほかの関節の取得が終わるのを待っています。</p> : null}
      {phase === "offline" ? <p className="m5-calmap__cap">接続中だけボードから取得できます。</p> : null}
      {phase === "error" ? (
        <p className="m5-calmap__cap">
          {note || "取得できませんでした。"}
          <button type="button" className="m5-calmap__retry" onClick={onRetry}>
            再取得
          </button>
        </p>
      ) : null}
    </div>
  );
}
