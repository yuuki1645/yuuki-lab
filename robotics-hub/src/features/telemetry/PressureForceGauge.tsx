import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { PressureTelemetrySample } from "@/shared/types/pressureTelemetry";
import "./PressureForceGauge.css";

/** DF9-40@10kg のフルスケール */
const FORCE_MAX_KG = 10;

type Props = {
  sample: PressureTelemetrySample | null;
  /** 直近サンプルからの経過秒。大きいと「古い」表示 */
  staleSec: number | null;
  connected: boolean;
};

function clamp01(x: number): number {
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

/**
 * 力に応じたヒート色（低: シアン → 中: 黄 → 高: 赤）。
 * CSS 変数用の hsl 文字列を返す。
 */
function forceHeatHsl(ratio: number): string {
  const t = clamp01(ratio);
  // 190°(cyan) → 45°(amber) → 8°(red)
  const hue = t < 0.5 ? 190 - t * 2 * 145 : 45 - (t - 0.5) * 2 * 37;
  const sat = 78 + t * 12;
  const light = 52 - t * 8;
  return `hsl(${hue.toFixed(1)} ${sat.toFixed(0)}% ${light.toFixed(0)}%)`;
}

function formatKg(kg: number | null): string {
  if (kg == null || !Number.isFinite(kg)) return "—.—";
  if (kg < 0.01) return "0.00";
  return kg.toFixed(2);
}

/**
 * Pico DF9-40 圧力の視覚ゲージ。
 * - 円環が力に比例して埋まる
 * - 中央の数値はスムーズに追従
 * - 力増加時にリップル（パルス）リングを出す
 */
export function PressureForceGauge({ sample, staleSec, connected }: Props) {
  const forceKg = sample?.force_kg ?? null;
  const targetRatio = forceKg == null ? 0 : clamp01(forceKg / FORCE_MAX_KG);

  // 表示用に少し遅れて追従（ガタつき低減）
  const [displayRatio, setDisplayRatio] = useState(0);
  const [displayKg, setDisplayKg] = useState(0);
  const displayRatioRef = useRef(0);
  const displayKgRef = useRef(0);
  const [ripples, setRipples] = useState<{ id: number; ratio: number }[]>([]);
  const rippleIdRef = useRef(0);
  const prevForceRef = useRef(0);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const r = displayRatioRef.current;
      const k = displayKgRef.current;
      const nextR = r + (targetRatio - r) * 0.18;
      const nextK =
        forceKg == null ? k * 0.85 : k + (forceKg - k) * 0.22;
      displayRatioRef.current = nextR;
      displayKgRef.current = nextK;
      setDisplayRatio(nextR);
      setDisplayKg(nextK);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [targetRatio, forceKg]);

  // 急な荷重増加でリップルを発火
  useEffect(() => {
    if (forceKg == null) return;
    const prev = prevForceRef.current;
    const delta = forceKg - prev;
    prevForceRef.current = forceKg;
    if (delta < 0.35) return;
    const id = ++rippleIdRef.current;
    const ratio = clamp01(forceKg / FORCE_MAX_KG);
    setRipples((list) => [...list.slice(-4), { id, ratio }]);
    const t = window.setTimeout(() => {
      setRipples((list) => list.filter((r) => r.id !== id));
    }, 900);
    return () => window.clearTimeout(t);
  }, [forceKg]);

  const heat = useMemo(() => forceHeatHsl(displayRatio), [displayRatio]);
  const stale = staleSec != null && staleSec > 2.5;
  const idle = !connected || forceKg == null;

  // SVG 円環
  const size = 220;
  const cx = size / 2;
  const cy = size / 2;
  const r = 88;
  const stroke = 14;
  const circ = 2 * Math.PI * r;
  const dashOffset = circ * (1 - displayRatio);

  const pct =
    sample?.force_pct != null && Number.isFinite(sample.force_pct)
      ? sample.force_pct
      : displayRatio * 100;

  return (
    <div
      className={
        "pressure-gauge" +
        (idle ? " pressure-gauge--idle" : "") +
        (stale ? " pressure-gauge--stale" : "")
      }
        style={
          {
            "--pressure-heat": heat,
            "--pressure-ratio": String(displayRatio),
          } as CSSProperties
        }
    >
      <div className="pressure-gauge__visual" aria-hidden>
        {/* 背景の柔らかいグロー（力が大きいほど強く） */}
        <div className="pressure-gauge__glow" />

        {ripples.map((ripple) => (
          <div
            key={ripple.id}
            className="pressure-gauge__ripple"
            style={
              {
                "--ripple-heat": forceHeatHsl(ripple.ratio),
              } as CSSProperties
            }
          />
        ))}

        <svg
          className="pressure-gauge__svg"
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
        >
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="rgba(140, 160, 220, 0.18)"
            strokeWidth={stroke}
          />
          <circle
            className="pressure-gauge__arc"
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={heat}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={dashOffset}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
          {/* 内側の薄いリング */}
          <circle
            cx={cx}
            cy={cy}
            r={r - stroke - 6}
            fill="rgba(8, 12, 28, 0.72)"
            stroke="rgba(200, 210, 255, 0.12)"
            strokeWidth={1}
          />
        </svg>

        <div className="pressure-gauge__center">
          <div className="pressure-gauge__value">{formatKg(idle ? null : displayKg)}</div>
          <div className="pressure-gauge__unit">kg</div>
          <div className="pressure-gauge__pct">{pct.toFixed(0)}%</div>
        </div>
      </div>

      <div className="pressure-gauge__bar" role="meter" aria-valuemin={0} aria-valuemax={FORCE_MAX_KG} aria-valuenow={forceKg ?? 0}>
        <div className="pressure-gauge__bar-fill" />
        <div className="pressure-gauge__bar-ticks">
          <span>0</span>
          <span>5</span>
          <span>10 kg</span>
        </div>
      </div>

      <dl className="pressure-gauge__meta">
        <div>
          <dt>電圧</dt>
          <dd>
            {sample?.voltage_v != null && Number.isFinite(sample.voltage_v)
              ? `${sample.voltage_v.toFixed(3)} V`
              : "—"}
          </dd>
        </div>
        <div>
          <dt>Rs</dt>
          <dd>
            {sample?.rs_ohm != null && Number.isFinite(sample.rs_ohm)
              ? `${Math.round(sample.rs_ohm).toLocaleString()} Ω`
              : "—"}
          </dd>
        </div>
        <div>
          <dt>ピン</dt>
          <dd>{sample?.adc_pin != null ? `GP${sample.adc_pin}` : "—"}</dd>
        </div>
        <div>
          <dt>鮮度</dt>
          <dd>
            {staleSec == null
              ? "—"
              : staleSec < 1
                ? "live"
                : `${staleSec.toFixed(1)} s`}
          </dd>
        </div>
      </dl>
    </div>
  );
}
