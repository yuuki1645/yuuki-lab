import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { DF9_FORCE_MAX_KG } from "@/shared/types/pressureTelemetry";
import type { M5FootCorner, M5FootSample } from "./types";
import "./RightFootSole.css";

type CornerId = "top_left" | "top_right" | "bottom_left" | "bottom_right";

const CORNERS: { id: CornerId; label: string; area: string }[] = [
  { id: "top_left", label: "つま先左", area: "tl" },
  { id: "top_right", label: "つま先右", area: "tr" },
  { id: "bottom_left", label: "かかと左", area: "bl" },
  { id: "bottom_right", label: "かかと右", area: "br" },
];

type Props = {
  sample: M5FootSample | null | undefined;
  /** 右脚タブ左列向け。パッドと数字を大きくする */
  large?: boolean;
};

function clamp01(x: number): number {
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

function heat(ratio: number): string {
  const t = clamp01(ratio);
  const hue = t < 0.5 ? 190 - t * 2 * 145 : 45 - (t - 0.5) * 2 * 37;
  return `hsl(${hue.toFixed(1)} 82% ${52 - t * 8}%)`;
}

function fmtKg(kg: number | null | undefined): string {
  if (kg == null || !Number.isFinite(kg)) return "—";
  if (kg < 0.001) return "0.00";
  return kg.toFixed(2);
}

function cornerKg(c: M5FootCorner | null | undefined): number {
  if (!c || !Number.isFinite(c.force_kg)) return 0;
  return Math.max(0, c.force_kg);
}

/**
 * 右脚タブ左列用のコンパクトな足裏四隅 + 圧力中心。
 * 実機テレメトリ（Pico）の FootSolePressureMap と同じ熱色・CoP の考え方。
 */
export function RightFootSole({ sample, large }: Props) {
  const corners = sample?.corners ?? null;
  const ok = Boolean(sample?.ok);
  const totalKg = sample?.force_kg ?? 0;

  const [display, setDisplay] = useState<Record<CornerId, number>>({
    top_left: 0,
    top_right: 0,
    bottom_left: 0,
    bottom_right: 0,
  });
  const [displayTotal, setDisplayTotal] = useState(0);
  const displayRef = useRef(display);
  const totalRef = useRef(0);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const next = { ...displayRef.current };
      for (const def of CORNERS) {
        const target = ok ? cornerKg(corners?.[def.id]) : 0;
        next[def.id] = next[def.id] + (target - next[def.id]) * 0.22;
      }
      displayRef.current = next;
      setDisplay(next);
      const tTarget = ok ? totalKg : 0;
      totalRef.current += (tTarget - totalRef.current) * 0.22;
      setDisplayTotal(totalRef.current);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [corners, ok, totalKg]);

  const cop = useMemo(() => {
    if (!ok || !corners) return null;
    const pos: Record<CornerId, { x: number; y: number }> = {
      top_left: { x: -1, y: -1 },
      top_right: { x: 1, y: -1 },
      bottom_left: { x: -1, y: 1 },
      bottom_right: { x: 1, y: 1 },
    };
    let wx = 0;
    let wy = 0;
    let w = 0;
    for (const def of CORNERS) {
      const f = cornerKg(corners[def.id]);
      if (f < 0.02) continue;
      wx += pos[def.id].x * f;
      wy += pos[def.id].y * f;
      w += f;
    }
    if (w < 0.05) return null;
    return { x: wx / w, y: wy / w };
  }, [corners, ok]);

  return (
    <div className={"m5-foot" + (ok ? "" : " m5-foot--idle") + (large ? " m5-foot--large" : "")}>
      <div className="m5-foot__head">
        <span className="m5-foot__title">右足裏</span>
        <span className={"m5-foot__badge" + (ok ? " m5-foot__badge--ok" : "")}>
          {ok ? "live" : "未検出"}
        </span>
      </div>
      <div className="m5-foot__orient">つま先</div>
      <div className="m5-foot__plate" role="img" aria-label="右足裏四隅の圧力">
        {CORNERS.map((def) => {
          const kg = display[def.id];
          const ratio = clamp01(kg / DF9_FORCE_MAX_KG);
          return (
            <div
              key={def.id}
              className={"m5-foot__pad" + (ratio > 0.03 ? " m5-foot__pad--on" : "")}
              style={
                {
                  gridArea: def.area,
                  "--heat": heat(ratio),
                  "--ratio": String(ratio),
                } as CSSProperties
              }
            >
              <span className="m5-foot__pad-lab">{def.label}</span>
              <span className="m5-foot__pad-kg">{fmtKg(ok ? kg : null)}</span>
            </div>
          );
        })}
        {cop && ok ? (
          <div
            className="m5-foot__cop"
            style={
              {
                left: `calc(50% + ${cop.x * 34}%)`,
                top: `calc(50% + ${cop.y * 34}%)`,
              } as CSSProperties
            }
            title="圧力中心"
          />
        ) : null}
        <div className="m5-foot__total">
          <span>合計</span>
          <strong>
            {fmtKg(ok ? displayTotal : null)}
            <small>kg</small>
          </strong>
        </div>
      </div>
      <div className="m5-foot__orient m5-foot__orient--heel">かかと</div>
    </div>
  );
}
