/**
 * 関節カード用の校正マップ。
 * 点列はボードの map_get で届く。USB を占有するので、同時に取るのは 1 関節だけ。
 */
import { useEffect, useRef, useState } from "react";
import type { M5Cal, M5CalPoint, M5Cmd } from "./types";

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

function degText(v: number, digits: number): string {
  return v.toFixed(digits);
}

/** サーボ角の昇順。いまの指令に一番近い行だけ印を付ける。 */
function MapTable({ points, cmd }: { points: M5CalPoint[]; cmd: number | null }) {
  const rows = [...points].filter((p) => finite(p.servo) && finite(p.as5600)).sort((a, b) => a.servo - b.servo);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const markedRef = useRef<HTMLTableRowElement>(null);
  let marked = -1;
  if (finite(cmd) && rows.length) {
    let best = 0;
    let bestAbs = Math.abs(rows[0]!.servo - cmd);
    for (let i = 1; i < rows.length; i++) {
      const d = Math.abs(rows[i]!.servo - cmd);
      if (d < bestAbs) {
        best = i;
        bestAbs = d;
      }
    }
    marked = best;
  }
  useEffect(() => {
    const box = scrollerRef.current;
    const row = markedRef.current;
    if (!box || !row) return;
    const top = row.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
    box.scrollTop = Math.max(0, top - box.clientHeight / 2 + row.offsetHeight / 2);
  }, [marked, rows.length]);
  if (rows.length < 2) return null;
  return (
    <div className="m5-calmap__scroll" ref={scrollerRef}>
      <table className="m5-calmap__table">
        <thead>
          <tr>
            <th scope="col">サーボ°</th>
            <th scope="col">unwrap°</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p, i) => (
            <tr key={`${p.servo}-${i}`} ref={i === marked ? markedRef : undefined} className={i === marked ? "m5-calmap__row--now" : undefined}>
              <td>{degText(p.servo, 1)}</td>
              <td>{degText(p.as5600, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function JointCalMap({ phase, points, note, cmd, unwrap, onRetry }: PlotProps) {
  const cmdText = finite(cmd) ? `${cmd.toFixed(1)}°` : "—";
  const angText = finite(unwrap) ? `${unwrap.toFixed(1)}°` : "—";
  return (
    <div className="m5-calmap">
      {phase === "ready" ? (
        <>
          <MapTable points={points} cmd={cmd} />
          <p className="m5-calmap__cap">
            {points.length}点 · 強調はいまの指令 {cmdText} · unwrap {angText}
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
