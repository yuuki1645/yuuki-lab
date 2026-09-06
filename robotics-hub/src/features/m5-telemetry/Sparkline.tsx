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

/** 上・中・下の 3 本。左右軸は同じ高さに揃える */
const AXIS_TICK_COUNT = 3;

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

/** 目盛り数値を、SVG 上の y と同じ高さに置く */
function AxisTickLabels({
  ticks,
  unit,
  color,
  tickYs,
  svgH,
}: {
  ticks: number[];
  unit: string;
  color?: string;
  tickYs: number[];
  svgH: number;
}) {
  return (
    <>
      {ticks.map((t, i) => (
        <span
          key={i}
          className="m5-spark-ticklab"
          style={{ top: `${(tickYs[i] / svgH) * 100}%`, color }}
        >
          {fmtTick(t)}
          {unit}
        </span>
      ))}
    </>
  );
}

/**
 * 依存なしの折れ線。iPad 向けにタッチスクロールを邪魔しない。
 * showAxes のときは SVG の外側に HTML 目盛りを置き、縮小しても文字が潰れるのを防ぐ。
 * 目盛りの top% は SVG の y と同じ比率なので、補助線・脇の短い目盛り線と高さが一致する。
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
  // 目盛り文字が枠外で見切れないよう、軸表示時は上下を広めに取る
  const plotT = showAxes ? 12 : 8;
  const plotB = showAxes ? h - 14 : h - 8;
  /** グラフ枠の左右に、短い目盛り線を描く余白 */
  const tickLen = showAxes ? 8 : 0;
  const plotL = showAxes ? tickLen + 1 : 8;
  const plotR = showAxes ? w - tickLen - 1 : w - 8;
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
  const plotH = plotB - plotT;

  const xAt = (i: number) => plotL + (i / Math.max(n - 1, 1)) * (plotR - plotL);
  const yAtGlobal = (v: number) => plotT + (1 - (v - lo) / globalSpan) * plotH;
  const yAtSeries = (s: SparkSeries, v: number) => {
    const sLo = s.yMin ?? lo;
    const sHi = s.yMax ?? hi;
    return plotT + (1 - (v - sLo) / spanOf(sLo, sHi)) * plotH;
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
      ticks: evenTicks(min, max, AXIS_TICK_COUNT),
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
        ticks: evenTicks(min, max, AXIS_TICK_COUNT),
      });
    }
  }

  /**
   * 3 本の水平位置。左右軸はいずれも min〜max を等分するので、
   * プロット矩形の上・中・下に固定する（数値ラベルも同じ y を使う）。
   */
  const tickYs = showAxes
    ? Array.from(
        { length: AXIS_TICK_COUNT },
        (_, i) => plotT + (plotH * i) / (AXIS_TICK_COUNT - 1)
      )
    : [yAtGlobal(lo)];

  const svg = (
    <svg
      className={showAxes ? "m5-spark-svg" : className}
      viewBox={`0 0 ${w} ${h}`}
      /* CSS 上の高さが viewBox と違っても、y が目盛りと同じ比率で伸びるようにする */
      preserveAspectRatio="none"
      role="img"
      aria-hidden
    >
      {showAxes ? (
        <rect
          className="m5-spark-frame"
          x={plotL}
          y={plotT}
          width={plotR - plotL}
          height={plotH}
          fill="none"
          stroke="rgba(255,255,255,0.28)"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
      ) : null}
      {tickYs.map((yy, i) => (
        <g key={i}>
          <line
            x1={plotL}
            x2={plotR}
            y1={yy}
            y2={yy}
            stroke={showAxes ? "rgba(255,255,255,0.28)" : "rgba(255,255,255,0.12)"}
            strokeWidth="1"
            strokeDasharray={showAxes ? "3.5 3.5" : undefined}
            vectorEffect="non-scaling-stroke"
          />
          {showAxes && leftAxis ? (
            <line
              x1={plotL - tickLen}
              x2={plotL}
              y1={yy}
              y2={yy}
              stroke="rgba(200, 214, 230, 0.85)"
              strokeWidth="1.25"
              vectorEffect="non-scaling-stroke"
            />
          ) : null}
          {showAxes && rightAxes.length ? (
            <line
              x1={plotR}
              x2={plotR + tickLen}
              y1={yy}
              y2={yy}
              stroke="rgba(200, 214, 230, 0.85)"
              strokeWidth="1.25"
              vectorEffect="non-scaling-stroke"
            />
          ) : null}
        </g>
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
          <AxisTickLabels
            ticks={leftAxis.ticks}
            unit={leftAxis.unit}
            color={leftAxis.color}
            tickYs={tickYs}
            svgH={h}
          />
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
          <div key={ax.unit || ax.color} className="m5-spark-ycol">
            <AxisTickLabels
              ticks={ax.ticks}
              unit={ax.unit}
              color={ax.color}
              tickYs={tickYs}
              svgH={h}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
