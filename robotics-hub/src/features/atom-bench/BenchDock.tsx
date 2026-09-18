/**
 * 机上ラボ下部ドック。ステータスバーの直上に張り付く。
 *
 * Cursor の Terminal ペインと同じく、タブ帯は常時見え、開くと横幅いっぱいの
 * ログ領域が出る。上端ドラッグで高さを変える。今後タブを足せるよう id だけ先に置く。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { UiHelp } from "@/shared/components/UiHelp";
import { EventsLog } from "@/features/m5-telemetry/EventsLog";

/** 今後ここへタブを足す。content が無いものは空プレースホルダ */
export type BenchDockTabId = "events" | "output" | "debug";

const DOCK_TABS: { id: BenchDockTabId; label: string }[] = [
  { id: "events", label: "イベント" },
  { id: "output", label: "出力" },
  { id: "debug", label: "デバッグ" },
];

const H_MIN = 96;
const H_MAX = 720;
const H_DEFAULT = 220;
const H_LS_KEY = "atom-bench-dock-h";

type Props = {
  events: string[];
  eventHeadSeq: number;
  eventTailSeq: number;
  /** 開いているとき本体の高さ（px）。本文の padding 計算用 */
  onLayout: (open: boolean, heightPx: number) => void;
};

export function BenchDock({ events, eventHeadSeq, eventTailSeq, onLayout }: Props) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<BenchDockTabId>("events");
  const [height, setHeight] = useState(readStoredHeight);
  const drag = useRef<{ startY: number; startH: number } | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(H_LS_KEY, String(height));
    } catch {
      /* プライベートモードなどでは捨てる */
    }
  }, [height]);

  useEffect(() => {
    onLayout(open, open ? height : 0);
  }, [open, height, onLayout]);

  const onPointerMove = useCallback((ev: PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    // 上へドラッグすると高くする（Cursor のパネルと同じ）
    const next = clampH(d.startH + (d.startY - ev.clientY));
    setHeight(next);
  }, []);

  const onPointerUp = useCallback(() => {
    drag.current = null;
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    document.body.style.removeProperty("cursor");
    document.body.style.removeProperty("user-select");
  }, [onPointerMove]);

  useEffect(() => {
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
    };
  }, [onPointerMove, onPointerUp]);

  const startResize = (ev: React.PointerEvent) => {
    ev.preventDefault();
    drag.current = { startY: ev.clientY, startH: height };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    document.body.style.cursor = "ns-resize";
    document.body.style.userSelect = "none";
  };

  /** 下端付近にいるときだけ追従。上にスクロールしたら止め、また下まで来たら再開 */
  const pinBottom = useRef(true);

  const selectTab = (id: BenchDockTabId) => {
    if (open && tab === id) {
      setOpen(false);
      return;
    }
    setTab(id);
    setOpen(true);
    if (id === "events") pinBottom.current = true;
  };

  return (
    <div className={"bench-dock" + (open ? " bench-dock--open" : "")} aria-label="下部パネル">
      {open ? (
        <button
          type="button"
          className="bench-dock__resize"
          aria-label="パネルの高さを変更"
          onPointerDown={startResize}
        />
      ) : null}

      <div className="bench-dock__tabs" role="tablist" aria-label="下部パネルのタブ">
        {DOCK_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={open && tab === t.id}
            className={
              "bench-dock__tab" + (open && tab === t.id ? " bench-dock__tab--on" : "")
            }
            onClick={() => selectTab(t.id)}
          >
            {t.label}
          </button>
        ))}
        <UiHelp title="下部パネル" placement="top" wide>
          イベントは lab_debug.py が溜めたログです。新しい行が下、最大 5000 行です。上にスクロールすると追従を止めます。出力とデバッグは予約枠です。上端をドラッグすると高さを変えられます。
        </UiHelp>
        <span className="bench-dock__tabs-sp" />
        {open ? (
          <button
            type="button"
            className="bench-dock__hide"
            aria-label="パネルをしまう"
            onClick={() => setOpen(false)}
          >
            ▾
          </button>
        ) : null}
      </div>

      {open ? (
        <div className="bench-dock__body" style={{ height }}>
          {tab === "events" ? (
            <EventsLog
              className="bench-dock__log"
              lines={events}
              headSeq={eventHeadSeq}
              tailSeq={eventTailSeq}
              pinBottom={pinBottom}
            />
          ) : (
            <EmptyTab tab={tab} />
          )}
        </div>
      ) : null}
    </div>
  );
}

function EmptyTab({ tab }: { tab: BenchDockTabId }) {
  const label = DOCK_TABS.find((t) => t.id === tab)?.label ?? tab;
  return (
    <div className="bench-dock__empty">
      <p>{label}（準備中）</p>
      <p className="bench-dock__empty-sub">このタブは後から中身を足す予約枠です。</p>
    </div>
  );
}

function readStoredHeight(): number {
  try {
    const n = Number(localStorage.getItem(H_LS_KEY));
    if (Number.isFinite(n) && n > 0) return clampH(n);
  } catch {
    /* ignore */
  }
  return H_DEFAULT;
}

function clampH(n: number): number {
  const cap = typeof window === "undefined" ? H_MAX : Math.min(H_MAX, Math.floor(window.innerHeight * 0.7));
  return Math.min(cap, Math.max(H_MIN, Math.round(n)));
}
