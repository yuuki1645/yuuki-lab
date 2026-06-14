import { useId, useMemo, useState } from "react";
import type { IsaacRlLogScalarPoint } from "@/shared/types/isaacRlLog";

export interface MetricLineChartProps {
  title: string;
  subtitle?: string;
  color: string;
  data: IsaacRlLogScalarPoint[];
  /** モバイルではチャート高さを少し低く */
  compact?: boolean;
  valueDecimals?: number;
}

/** 依存ライブラリなしの SVG 折れ線グラフ（PC / スマホ両対応） */
export function MetricLineChart({
  title,
  subtitle,
  color,
  data,
  compact = false,
  valueDecimals = 2,
}: MetricLineChartProps) {
  const gradId = useId().replace(/:/g, "");
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const layout = useMemo(() => {
    const w = 640;
    const h = compact ? 160 : 200;
    const pad = { top: 12, right: 12, bottom: 28, left: 52 };
    const innerW = w - pad.left - pad.right;
    const innerH = h - pad.top - pad.bottom;

    if (data.length === 0) {
      return { w, h, pad, innerW, innerH, path: "", yTicks: [] as number[], xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    }

    const xs = data.map((d) => d.step);
    const ys = data.map((d) => d.value);
    const xMin = xs[0] ?? 0;
    const xLast = xs[xs.length - 1] ?? xMin;
    const xMax = xLast === xMin ? xMin + 1 : xLast;
    let yMin = Math.min(...ys);
    let yMax = Math.max(...ys);
    if (yMin === yMax) {
      yMin -= 1;
      yMax += 1;
    }
    const yPad = (yMax - yMin) * 0.08 || 1;
    yMin -= yPad;
    yMax += yPad;

    const xScale = (x: number) => pad.left + ((x - xMin) / (xMax - xMin)) * innerW;
    const yScale = (y: number) => pad.top + innerH - ((y - yMin) / (yMax - yMin)) * innerH;

    const path = data
      .map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(d.step).toFixed(2)} ${yScale(d.value).toFixed(2)}`)
      .join(" ");

    const yTicks = [yMin, (yMin + yMax) / 2, yMax];

    return { w, h, pad, innerW, innerH, path, yTicks, xMin, xMax, yMin, yMax, xScale, yScale };
  }, [data, compact]);

  const hoverPoint = hoverIdx !== null && data[hoverIdx] ? data[hoverIdx] : null;
  const latest = data[data.length - 1];

  return (
    <figure className="isaac-log-chart">
      <figcaption className="isaac-log-chart__head">
        <div>
          <h3 className="isaac-log-chart__title">{title}</h3>
          {subtitle ? <p className="isaac-log-chart__sub">{subtitle}</p> : null}
        </div>
        {latest && (
          <div className="isaac-log-chart__latest">
            <span className="isaac-log-chart__latest-label">最新</span>
            <span className="isaac-log-chart__latest-value" style={{ color }}>
              {latest.value.toFixed(valueDecimals)}
            </span>
            <span className="isaac-log-chart__latest-step">iter {Math.round(latest.step)}</span>
          </div>
        )}
      </figcaption>

      {data.length === 0 ? (
        <p className="isaac-log-chart__empty">データなし</p>
      ) : (
        <div
          className="isaac-log-chart__svg-wrap"
          onMouseLeave={() => setHoverIdx(null)}
          onTouchEnd={() => setHoverIdx(null)}
        >
          <svg
            viewBox={`0 0 ${layout.w} ${layout.h}`}
            className="isaac-log-chart__svg"
            role="img"
            aria-label={`${title} の折れ線グラフ`}
          >
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0.02} />
              </linearGradient>
            </defs>

            {/* 横グリッド */}
            {layout.yTicks.map((yt) => {
              const yMin = layout.yMin;
              const yMax = layout.yMax;
              const y =
                layout.pad.top + layout.innerH - ((yt - yMin) / (yMax - yMin)) * layout.innerH;
              return (
                <g key={yt}>
                  <line
                    x1={layout.pad.left}
                    y1={y}
                    x2={layout.pad.left + layout.innerW}
                    y2={y}
                    stroke="rgba(200,210,255,0.08)"
                  />
                  <text x={layout.pad.left - 6} y={y + 4} textAnchor="end" className="isaac-log-chart__axis">
                    {yt.toFixed(valueDecimals)}
                  </text>
                </g>
              );
            })}

            {/* 塗りつぶし領域 */}
            {layout.path && layout.xScale && (
              <path
                d={`${layout.path} L ${layout.xScale(layout.xMax).toFixed(2)} ${(layout.pad.top + layout.innerH).toFixed(2)} L ${layout.xScale(layout.xMin).toFixed(2)} ${(layout.pad.top + layout.innerH).toFixed(2)} Z`}
                fill={`url(#${gradId})`}
              />
            )}

            <path d={layout.path} fill="none" stroke={color} strokeWidth={2.2} vectorEffect="non-scaling-stroke" />

            {/* ホバー用透明ヒットエリア（タッチでも反応） */}
            {layout.xScale &&
              data.map((d, i) => {
                const segW = layout.innerW / data.length;
                return (
                  <rect
                    key={`${d.step}-${i}`}
                    x={layout.pad.left + i * segW}
                    y={layout.pad.top}
                    width={segW}
                    height={layout.innerH}
                    fill="transparent"
                    onMouseEnter={() => setHoverIdx(i)}
                    onTouchStart={() => setHoverIdx(i)}
                  />
                );
              })}

            {hoverPoint && layout.xScale && layout.yScale && (
              <>
                <line
                  x1={layout.xScale(hoverPoint.step)}
                  y1={layout.pad.top}
                  x2={layout.xScale(hoverPoint.step)}
                  y2={layout.pad.top + layout.innerH}
                  stroke={color}
                  strokeOpacity={0.45}
                  strokeDasharray="4 3"
                />
                <circle
                  cx={layout.xScale(hoverPoint.step)}
                  cy={layout.yScale(hoverPoint.value)}
                  r={5}
                  fill={color}
                  stroke="#0b1020"
                  strokeWidth={2}
                />
              </>
            )}

            <text
              x={layout.pad.left + layout.innerW / 2}
              y={layout.h - 6}
              textAnchor="middle"
              className="isaac-log-chart__axis"
            >
              learning iteration
            </text>
          </svg>

          {hoverPoint ? (
            <div className="isaac-log-chart__tooltip" role="status">
              iter {Math.round(hoverPoint.step)} · {hoverPoint.value.toFixed(valueDecimals)}
            </div>
          ) : null}
        </div>
      )}
    </figure>
  );
}
