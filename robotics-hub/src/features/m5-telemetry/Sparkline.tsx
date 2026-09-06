import { M5_COLORS } from "./types";

type Series = {
  key: string;
  color: string;
  values: Array<number | null | undefined>;
};

type Props = {
  series: Series[];
  height?: number;
  yMin?: number;
  yMax?: number;
  /** 右軸など、系列ごとに自動スケールしたいとき true（yMin/yMax は無視） */
  autoScale?: boolean;
};

/**
 * 依存なしの折れ線。iPad 向けにタッチスクロールを邪魔しない。
 */
export function Sparkline({ series, height = 140, yMin = 0, yMax = 360, autoScale = false }: Props) {
  const w = 640;
  const h = height;
  const pad = 8;
  const n = Math.max(...series.map((s) => s.values.length), 2);

  let lo = yMin;
  let hi = yMax;
  if (autoScale) {
    const nums: number[] = [];
    for (const s of series) {
      for (const v of s.values) {
        if (typeof v === "number" && Number.isFinite(v)) nums.push(v);
      }
    }
    if (nums.length) {
      lo = Math.min(...nums);
      hi = Math.max(...nums);
      if (hi - lo < 1e-3) {
        lo -= 1;
        hi += 1;
      }
    }
  }
  const span = hi - lo || 1;

  const xAt = (i: number) => pad + (i / Math.max(n - 1, 1)) * (w - pad * 2);
  const yAt = (v: number) => pad + (1 - (v - lo) / span) * (h - pad * 2);

  return (
    <svg className="m5-spark" viewBox={`0 0 ${w} ${h}`} role="img" aria-hidden>
      <line
        x1={pad}
        x2={w - pad}
        y1={yAt(lo)}
        y2={yAt(lo)}
        stroke="rgba(255,255,255,0.12)"
        strokeWidth="1"
      />
      {series.map((s) => {
        const pts: string[] = [];
        s.values.forEach((v, i) => {
          if (typeof v !== "number" || !Number.isFinite(v)) return;
          pts.push(`${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`);
        });
        if (pts.length < 2) return null;
        return (
          <polyline
            key={s.key}
            fill="none"
            stroke={s.color || M5_COLORS.cmd}
            strokeWidth="2"
            points={pts.join(" ")}
          />
        );
      })}
    </svg>
  );
}
