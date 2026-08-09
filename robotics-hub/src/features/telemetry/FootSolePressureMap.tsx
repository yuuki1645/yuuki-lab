import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type {
  PressureCornerSample,
  PressureFootCorners,
  PressureTelemetrySample,
} from "@/shared/types/pressureTelemetry";
import "./FootSolePressureMap.css";

/** DF9-40@10kg のフルスケール（1 センサ） */
const FORCE_MAX_KG = 10;

type CornerId = keyof PressureFootCorners;

type CornerDef = {
  id: CornerId;
  label: string;
  /** チャンネル表示（未設置は null） */
  channelLabel: string | null;
  /** CSS grid 位置 */
  gridArea: string;
};

/** 上面図・つま先が上。A0=左上 / A1=右上 / A2=右下 / 左下=未設置 */
const CORNER_DEFS: CornerDef[] = [
  { id: "top_left", label: "左上", channelLabel: "A0", gridArea: "tl" },
  { id: "top_right", label: "右上", channelLabel: "A1", gridArea: "tr" },
  { id: "bottom_left", label: "左下", channelLabel: null, gridArea: "bl" },
  { id: "bottom_right", label: "右下", channelLabel: "A2", gridArea: "br" },
];

type Props = {
  sample: PressureTelemetrySample | null;
  staleSec: number | null;
  connected: boolean;
};

function clamp01(x: number): number {
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

/** 力に応じたヒート色（低: シアン → 中: 黄 → 高: 赤） */
function forceHeatHsl(ratio: number): string {
  const t = clamp01(ratio);
  const hue = t < 0.5 ? 190 - t * 2 * 145 : 45 - (t - 0.5) * 2 * 37;
  const sat = 78 + t * 12;
  const light = 52 - t * 8;
  return `hsl(${hue.toFixed(1)} ${sat.toFixed(0)}% ${light.toFixed(0)}%)`;
}

function formatKg(kg: number | null | undefined): string {
  if (kg == null || !Number.isFinite(kg)) return "—.—";
  if (kg < 0.01) return "0.00";
  return kg.toFixed(2);
}

/**
 * レガシー単点サンプルを四隅へ仮マッピング（A0=左上のみ）。
 * 新フォーマットでは corners をそのまま使う。
 */
function resolveCorners(sample: PressureTelemetrySample | null): PressureFootCorners | null {
  if (!sample) return null;
  if (sample.corners) {
    return {
      top_left: sample.corners.top_left ?? null,
      top_right: sample.corners.top_right ?? null,
      bottom_right: sample.corners.bottom_right ?? null,
      bottom_left: sample.corners.bottom_left ?? null,
    };
  }
  // 旧ペイロード互換: 単点を左上に置く
  return {
    top_left: {
      force_kg: sample.force_kg,
      force_pct: sample.force_pct,
      voltage_v: sample.voltage_v,
      rs_ohm: sample.rs_ohm,
    },
    top_right: null,
    bottom_right: null,
    bottom_left: null,
  };
}

type CornerPadProps = {
  def: CornerDef;
  corner: PressureCornerSample | null;
  /** 未設置スロット（配線なし） */
  uninstalled: boolean;
  displayKg: number;
  displayRatio: number;
};

function CornerPad({ def, corner, uninstalled, displayKg, displayRatio }: CornerPadProps) {
  const heat = forceHeatHsl(displayRatio);
  const hasData = !uninstalled && corner != null;

  return (
    <div
      className={
        "foot-sole__pad" +
        (uninstalled ? " foot-sole__pad--missing" : "") +
        (hasData && displayRatio > 0.02 ? " foot-sole__pad--active" : "")
      }
      style={
        {
          gridArea: def.gridArea,
          "--pad-heat": heat,
          "--pad-ratio": String(displayRatio),
        } as CSSProperties
      }
    >
      <div className="foot-sole__pad-blob" aria-hidden />
      <div className="foot-sole__pad-label">
        <span className="foot-sole__pad-name">{def.label}</span>
        <span className="foot-sole__pad-ch">
          {uninstalled ? "未設置" : def.channelLabel}
        </span>
      </div>
      <div className="foot-sole__pad-value">
        {uninstalled ? "—" : formatKg(hasData ? displayKg : null)}
        {!uninstalled && <span className="foot-sole__pad-unit">kg</span>}
      </div>
      {!uninstalled && (
        <div className="foot-sole__pad-bar" aria-hidden>
          <div className="foot-sole__pad-bar-fill" />
        </div>
      )}
    </div>
  );
}

/**
 * 足裏フレーム四隅の圧力をリアルタイム表示する。
 * 四角いフレームの各隅にヒート付きパッドを配置し、中央に合計力を出す。
 */
export function FootSolePressureMap({ sample, staleSec, connected }: Props) {
  const corners = useMemo(() => resolveCorners(sample), [sample]);
  const totalKg = sample?.force_kg ?? null;

  // 各隅のスムーズ表示値
  const [display, setDisplay] = useState<Record<CornerId, { kg: number; ratio: number }>>({
    top_left: { kg: 0, ratio: 0 },
    top_right: { kg: 0, ratio: 0 },
    bottom_left: { kg: 0, ratio: 0 },
    bottom_right: { kg: 0, ratio: 0 },
  });
  const [displayTotal, setDisplayTotal] = useState(0);
  const displayRef = useRef(display);
  const totalRef = useRef(0);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const next = { ...displayRef.current };
      for (const def of CORNER_DEFS) {
        const c = corners?.[def.id] ?? null;
        const uninstalled = def.channelLabel == null;
        const targetKg = uninstalled || c == null ? 0 : c.force_kg;
        const targetRatio = clamp01(targetKg / FORCE_MAX_KG);
        const cur = next[def.id];
        next[def.id] = {
          kg: cur.kg + (targetKg - cur.kg) * 0.22,
          ratio: cur.ratio + (targetRatio - cur.ratio) * 0.18,
        };
      }
      displayRef.current = next;
      setDisplay(next);

      const tTarget = totalKg == null ? 0 : totalKg;
      const tNext =
        totalKg == null
          ? totalRef.current * 0.85
          : totalRef.current + (tTarget - totalRef.current) * 0.22;
      totalRef.current = tNext;
      setDisplayTotal(tNext);

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [corners, totalKg]);

  const stale = staleSec != null && staleSec > 2.5;
  const idle = !connected || sample == null;

  // 重心の簡易推定（設置センサの加重平均 → フレーム内オフセット）
  const cop = useMemo(() => {
    if (!corners) return null;
    // 正規化座標: 左=-1, 右=+1 / 上=-1, 下=+1
    const positions: Record<CornerId, { x: number; y: number }> = {
      top_left: { x: -1, y: -1 },
      top_right: { x: 1, y: -1 },
      bottom_left: { x: -1, y: 1 },
      bottom_right: { x: 1, y: 1 },
    };
    let wx = 0;
    let wy = 0;
    let w = 0;
    for (const def of CORNER_DEFS) {
      const c = corners[def.id];
      if (!c || def.channelLabel == null) continue;
      const f = Math.max(0, c.force_kg);
      if (f < 0.02) continue;
      wx += positions[def.id].x * f;
      wy += positions[def.id].y * f;
      w += f;
    }
    if (w < 0.05) return null;
    return { x: wx / w, y: wy / w };
  }, [corners]);

  return (
    <div
      className={
        "foot-sole" +
        (idle ? " foot-sole--idle" : "") +
        (stale ? " foot-sole--stale" : "")
      }
    >
      <div className="foot-sole__orient" aria-hidden>
        <span>つま先</span>
      </div>

      <div className="foot-sole__frame" role="img" aria-label="足裏フレーム四隅の圧力">
        {/* フレーム枠線 */}
        <div className="foot-sole__plate" />

        {CORNER_DEFS.map((def) => {
          const uninstalled = def.channelLabel == null;
          const corner = corners?.[def.id] ?? null;
          const d = display[def.id];
          return (
            <CornerPad
              key={def.id}
              def={def}
              corner={corner}
              uninstalled={uninstalled}
              displayKg={d.kg}
              displayRatio={d.ratio}
            />
          );
        })}

        {/* 圧力中心のドット（設置センサのみで推定） */}
        {cop && !idle && (
          <div
            className="foot-sole__cop"
            style={
              {
                // plate 中央を 0,0 として ±38% 程度にマップ
                left: `calc(50% + ${cop.x * 38}%)`,
                top: `calc(50% + ${cop.y * 38}%)`,
              } as CSSProperties
            }
            title="圧力中心（概算）"
          />
        )}

        <div className="foot-sole__center">
          <div className="foot-sole__total-label">合計</div>
          <div className="foot-sole__total-value">
            {formatKg(idle ? null : displayTotal)}
            <span className="foot-sole__total-unit">kg</span>
          </div>
          <div className="foot-sole__fresh">
            {staleSec == null
              ? "—"
              : staleSec < 1
                ? "live"
                : `${staleSec.toFixed(1)} s`}
          </div>
        </div>
      </div>

      <div className="foot-sole__orient foot-sole__orient--heel" aria-hidden>
        <span>かかと</span>
      </div>

      <dl className="foot-sole__meta">
        {CORNER_DEFS.map((def) => {
          const c = corners?.[def.id];
          const uninstalled = def.channelLabel == null;
          return (
            <div key={def.id}>
              <dt>
                {def.label}
                {def.channelLabel ? ` (${def.channelLabel})` : ""}
              </dt>
              <dd>
                {uninstalled
                  ? "未設置"
                  : c?.voltage_v != null && Number.isFinite(c.voltage_v)
                    ? `${c.voltage_v.toFixed(3)} V`
                    : "—"}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
