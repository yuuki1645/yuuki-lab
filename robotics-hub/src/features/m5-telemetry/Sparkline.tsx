import { M5_COLORS } from "./types";

export type SparkSeries = {
  key: string;
  color: string;
  values: Array<number | null | undefined>;
  /** 省略時は Sparkline の yMin/yMax（または autoScale） */
  yMin?: number;
  yMax?: number;
  /** 目盛りを出すとき、左＝角度・右＝電圧/電流 */
  axis?: "left" | "right";
  unit?: string;
};

type AxisInfo = {
  min: number;
  max: number;
  unit: string;
  color: string;
  ticks: number[];
};

type Props = {
  series: SparkSeries[];
  height?: number;
  yMin?: number;
  yMax?: number;
  /** 右軸など、系列ごとに自動スケールしたいとき true（yMin/yMax は無視） */
  autoScale?: boolean;
  className?: string;
  /** 左右の数値目盛り（単位付き）。既存のコンパクト表示は false のまま */
  showAxes?: boolean;
};

function finiteNums(values: Array<number | null | undefined>): number[] {
  const nums: number[] = [];
  for (const v of values) {
    if (typeof v === "number" && Number.isFinite(v)) nums.push(v);
  }
  return nums;
}

/** 上（最大）→下（最小）の等間隔目盛り */
function evenTicks(min: number, max: number, count: number): number[] {
  const n = Math.max(2, count);
  const ticks: number[] = [];
  for (let i = 0; i < n; i++) {
    ticks.push(max - ((max - min) * i) / (n - 1));
  }
  return ticks;
}

function fmtTick(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v - Math.round(v)) < 1e-6) return String(Math.round(v));
  return v.toFixed(1);
}

function spanOf(min: number, max: number): number {
  const s = max - min;
  return s === 0 ? 1 : s;
}

/**
 * 依存なしの折れ線。iPad 向けにタッチスクロールを邪魔しない。
 * showAxes のときは SVG の外側に HTML 目盛りを置き、縮小しても文字が潰れるのを防ぐ。
 */
export function Sparkline({
  series,
  height = 140,
  yMin = 0,
  yMax = 360,
  autoScale = false,
  className = "m5-spark",
  showAxes = false,
}: Props) {
  const w = 640;
  const h = height;
  const padT = 8;
  const padB = 8;
  const padX = showAxes ? 4 : 8;
  const n = Math.max(...series.map((s) => s.values.length), 2);

  let lo = yMin;
  let hi = yMax;
  if (autoScale) {
    const nums: number[] = [];
    for (const s of series) nums.push(...finiteNums(s.values));
    if (nums.length) {
      lo = Math.min(...nums);
      hi = Math.max(...nums);
      if (hi - lo < 1e-3) {
        lo -= 1;
        hi += 1;
      }
    }
  }
  const globalSpan = spanOf(lo, hi);

  const xAt = (i: number) => padX + (i / Math.max(n - 1, 1)) * (w - padX * 2);
  const yAtGlobal = (v: number) => padT + (1 - (v - lo) / globalSpan) * (h - padT - padB);
  const yAtSeries = (s: SparkSeries, v: number) => {
    const sLo = s.yMin ?? lo;
    const sHi = s.yMax ?? hi;
    return padT + (1 - (v - sLo) / spanOf(sLo, sHi)) * (h - padT - padB);
  };

  const leftSeries = series.filter((s) => (s.axis ?? "left") === "left");
  const rightSeries = series.filter((s) => s.axis === "right");

  const leftAxis: AxisInfo | null = (() => {
    if (!showAxes || !leftSeries.length) return null;
    const a = leftSeries[0];
    const min = a.yMin ?? lo;
    const max = a.yMax ?? hi;
    return {
      min,
      max,
      unit: a.unit ?? "",
      color: "#8b9bb0",
      ticks: evenTicks(min, max, 3),
    };
  })();

  const rightAxes: AxisInfo[] = [];
  if (showAxes) {
    for (const s of rightSeries) {
      const min = s.yMin ?? lo;
      const max = s.yMax ?? hi;
      rightAxes.push({
        min,
        max,
        unit: s.unit ?? "",
        color: s.color,
        ticks: evenTicks(min, max, 3),
      });
    }
  }

  const gridYs = leftAxis
    ? leftAxis.ticks.map((t) => yAtSeries(leftSeries[0], t))
    : rightSeries.length
      ? evenTicks(rightSeries[0].yMin ?? lo, rightSeries[0].yMax ?? hi, 3).map((t) =>
          yAtSeries(rightSeries[0], t)
        )
      : [yAtGlobal(lo)];

  const svg = (
    <svg className={showAxes ? "m5-spark-svg" : className} viewBox={`0 0 ${w} ${h}`} role="img" aria-hidden>
      {gridYs.map((yy, i) => (
        <line
          key={i}
          x1={padX}
          x2={w - padX}
          y1={yy}
          y2={yy}
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="1"
        />
      ))}
      {series.map((s) => {
        const pts: string[] = [];
        s.values.forEach((v, i) => {
          if (typeof v !== "number" || !Number.isFinite(v)) return;
          pts.push(`${xAt(i).toFixed(1)},${yAtSeries(s, v).toFixed(1)}`);
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

  if (!showAxes) return svg;

  const wrapClass = [
    className,
    "m5-spark-axes",
    leftAxis ? "" : "m5-spark-axes--no-left",
    rightAxes.length ? "" : "m5-spark-axes--no-right",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={wrapClass}>
      {leftAxis ? (
        <div className="m5-spark-y m5-spark-y--left" aria-hidden>
          {leftAxis.ticks.map((t, i) => (
            <span key={i}>
              {fmtTick(t)}
              {leftAxis.unit}
            </span>
          ))}
        </div>
      ) : (
        <div className="m5-spark-y m5-spark-y--left" aria-hidden />
      )}
      {series.length ? (
        svg
      ) : (
        <p className="m5-spark-empty">系列を選んでください</p>
      )}
      <div className="m5-spark-y m5-spark-y--right" aria-hidden>
        {rightAxes.map((ax) => (
          <div key={ax.unit || ax.color} className="m5-spark-ycol" style={{ color: ax.color }}>
            {ax.ticks.map((t, i) => (
              <span key={i}>
                {fmtTick(t)}
                {ax.unit}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
