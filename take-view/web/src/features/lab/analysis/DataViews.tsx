/**
 * Numbers views next to the plots:
 *  - DataTable: the recorded rows around the cursor, one click away
 *  - RangeStats: min / max / mean / percentiles of the visible range,
 *    where min and max jump to the row that produced them
 */

import { memo, useEffect, useRef } from "react";
import { L, MAG_LABEL, SEVERITY_LABEL, fmt } from "../labels";
import type { LabRangeStats, LabRows } from "../types";
import { channelLabel } from "./panels";
import { formatNumber, formatOffset } from "./plotMath";
import { angleDisplayOf, formatAnglePair, radiansToDisplayDeg, type AngleDisplay } from "./screenAngle";

type Tone = "bad" | "warn" | undefined;

/** Highlight rule for a table cell, by channel field. */
function cellTone(channel: string, value: number | null, th: Record<string, number>): Tone {
  if (value == null) return undefined;
  const field = channel.split(".")[1];
  switch (field) {
    case "sev":
      return value >= 3 ? "bad" : value >= 2 ? "warn" : undefined;
    case "as_ok":
    case "ok":
      return value === 0 ? "bad" : undefined;
    case "mag":
      if (value === 0) return undefined;
      return value === 2 || value === 3 ? "warn" : "bad";
    case "seq_gap":
      return value > 0 ? "warn" : value < 0 ? "bad" : undefined;
    case "i2c_delta":
      return value > 0 ? "warn" : undefined;
    case "amp":
      return value >= th.amp_crit ? "bad" : value >= th.amp_warn ? "warn" : undefined;
    case "dt_ms":
      return value >= th.rx_gap_crit_sec * 1000 ? "bad" : value >= th.rx_gap_warn_sec * 1000 ? "warn" : undefined;
    default:
      return undefined;
  }
}

function cellValue(channel: string, value: number | null, uprightDeg: number): string {
  if (value == null) return L.missing;
  const angle = angleDisplayOf(channel);
  if (angle) return formatAnglePair(radiansToDisplayDeg(value, angle, angle === "screen" ? uprightDeg : 0), value);
  const field = channel.split(".")[1];
  if (field === "sev") return SEVERITY_LABEL[value] ?? String(value);
  if (field === "mag") return MAG_LABEL[value] ?? String(value);
  if (field === "as_ok" || field === "ina_ok" || field === "map_ok" || field === "ok" || field === "out") {
    return value >= 1 ? "1" : "0";
  }
  return formatNumber(value, 4);
}

type TableProps = {
  rows: LabRows | null;
  loading: boolean;
  cursorIndex: number | null;
  thresholds: Record<string, number>;
  /** Straight-down degrees of the focused joint. Radian joint channels use it. */
  uprightDeg: number;
  onPickIndex: (index: number) => void;
  onPage: (delta: number) => void;
};

export const DataTable = memo(function DataTable({ rows, loading, cursorIndex, thresholds, uprightDeg, onPickIndex, onPage }: TableProps) {
  const cursorRef = useRef<HTMLTableRowElement>(null);

  // Keep the cursor row in sight without yanking the whole page.
  useEffect(() => {
    const node = cursorRef.current;
    const box = node?.closest(".lab-data-scroll");
    if (!node || !box) return;
    const top = node.offsetTop - box.clientHeight / 2 + node.clientHeight / 2;
    box.scrollTo({ top: Math.max(0, top) });
  }, [rows, cursorIndex]);

  return (
    <section className="lab-data">
      <header className="lab-data-head">
        <h3 className="lab-section-title">
          {L.tableTitle}
          {loading ? <span className="lab-plot-loading" aria-hidden /> : null}
        </h3>
        <div className="lab-inspector-nav">
          <button type="button" className="btn btn-sm" onClick={() => onPage(-1)} disabled={!rows || rows.start <= 0}>
            {"\u25b2"} {L.earlier}
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onPage(1)} disabled={!rows || rows.end >= rows.total}>
            {"\u25bc"} {L.later}
          </button>
        </div>
      </header>
      <p className="lab-muted lab-small">{L.tableHint}</p>
      {rows ? (
        <div className="lab-data-scroll">
          <table className="lab-table lab-data-table">
            <thead>
              <tr>
                <th>{L.index}</th>
                <th>{L.time}</th>
                <th>seq</th>
                {rows.channels.map((channel) => (
                  <th key={channel} title={channel}>
                    {channelLabel(channel)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.index.map((index, position) => {
                const isCursor = index === cursorIndex;
                return (
                  <tr
                    key={index}
                    ref={isCursor ? cursorRef : undefined}
                    className={isCursor ? "is-selected is-cursor" : undefined}
                    onClick={() => onPickIndex(index)}
                  >
                    <td>{index}</td>
                    <td>{formatOffset(rows.t[position], 0.001)}</td>
                    <td>{rows.seq[position] ?? L.missing}</td>
                    {rows.channels.map((channel) => {
                      const value = rows.series[channel]?.[position] ?? null;
                      const tone = cellTone(channel, value, thresholds);
                      const className = [tone ? `lab-cell-${tone}` : "", value == null ? "lab-cell-missing" : ""]
                        .filter(Boolean)
                        .join(" ");
                      return (
                        <td key={channel} className={className || undefined}>
                          {cellValue(channel, value, uprightDeg)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="lab-muted">{loading ? L.loading : L.noCursor}</p>
      )}
    </section>
  );
});

type StatChannel = {
  key: string;
  label: string;
  digits: number;
  /** Set when the API number is still radians from upright. */
  angle?: AngleDisplay;
  uprightDeg?: number;
};

/**
 * One statistic. Radian joint channels become degrees, with the radian in parentheses.
 * A spread (std, max−min) stays a difference, so a hip does not gain 135°.
 */
function showStat(channel: StatChannel, value: number | null | undefined, spread = false): string {
  if (value == null || !Number.isFinite(value)) return formatNumber(value, channel.digits);
  if (!channel.angle) return formatNumber(value, channel.digits);
  const display: AngleDisplay = spread ? "delta" : channel.angle;
  const upright = display === "screen" ? (channel.uprightDeg ?? 0) : 0;
  return formatAnglePair(radiansToDisplayDeg(value, display, upright), value);
}

type StatsProps = {
  stats: LabRangeStats | null;
  loading: boolean;
  channels: StatChannel[];
  onPickIndex: (index: number) => void;
};

export const RangeStats = memo(function RangeStats({ stats, loading, channels, onPickIndex }: StatsProps) {
  const span = stats ? stats.to - stats.from : 0;
  return (
    <section className="lab-stats">
      <h3 className="lab-section-title">
        {L.statsTitle}
        {loading ? <span className="lab-plot-loading" aria-hidden /> : null}
      </h3>
      {stats ? (
        <p className="lab-muted lab-small">
          {fmt(L.statsRange, {
            from: formatOffset(stats.from, 0.1),
            to: formatOffset(stats.to, 0.1),
            span: span.toFixed(1),
            n: stats.sample_count.toLocaleString(),
          })}
          {" \u00b7 "}
          {L.statsHint}
        </p>
      ) : null}
      {stats ? (
        <div className="lab-table-wrap">
          <table className="lab-table lab-stats-table">
            <thead>
              <tr>
                <th />
                <th>{L.statN}</th>
                <th>{L.statMissing}</th>
                <th>{L.statMin}</th>
                <th>{L.statMax}</th>
                <th>{L.statMean}</th>
                <th>{L.statStd}</th>
                <th>{L.statP05}</th>
                <th>{L.statP50}</th>
                <th>{L.statP95}</th>
                <th>{L.statDelta}</th>
              </tr>
            </thead>
            <tbody>
              {channels.map((channel) => {
                const item = stats.stats[channel.key];
                if (!item) return null;
                const jump = (index: number | undefined, value: number | null | undefined) =>
                  index == null ? (
                    showStat(channel, value)
                  ) : (
                    <button type="button" className="lab-take-link" onClick={() => onPickIndex(index)}>
                      {showStat(channel, value)}
                    </button>
                  );
                return (
                  <tr key={channel.key}>
                    <th scope="row" title={channel.key}>
                      {channel.label}
                    </th>
                    <td>{item.n.toLocaleString()}</td>
                    <td className={item.missing > 0 ? "lab-cell-warn" : undefined}>{item.missing.toLocaleString()}</td>
                    <td>{jump(item.min_index, item.min)}</td>
                    <td>{jump(item.max_index, item.max)}</td>
                    <td>{showStat(channel, item.mean)}</td>
                    <td>{showStat(channel, item.std, true)}</td>
                    <td>{showStat(channel, item.p05)}</td>
                    <td>{showStat(channel, item.p50)}</td>
                    <td>{showStat(channel, item.p95)}</td>
                    <td>{showStat(channel, item.delta, true)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="lab-muted">{L.loading}</p>
      )}
    </section>
  );
});
