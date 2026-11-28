/**
 * Findings list: every detected problem, grouped by (kind, lane), with
 * its intervals. Clicking a finding zooms the plots to it, focuses its
 * joint and puts the cursor on its worst row; expanding it lists every
 * interval so they can be stepped through one by one.
 */

import { memo, useMemo, useState } from "react";
import { KIND_HINT, KIND_LABEL, L, LANE_LABEL, MAG_LABEL, SEVERITY_LABEL, THRESHOLD_LABEL, fmt } from "../labels";
import type { LabFinding, LabInterval } from "../types";
import { SEV_COLOR } from "./canvas";
import { formatNumber, formatOffset, formatPct } from "./plotMath";

type Scope = "all" | "joints" | "system";
type Sort = "severity" | "time";

type Props = {
  findings: LabFinding[];
  jointNames: string[];
  thresholds: Record<string, number>;
  selectedId: string | null;
  activeInterval: { id: string; index: number } | null;
  showInfo: boolean;
  onShowInfo: (value: boolean) => void;
  onSelect: (finding: LabFinding) => void;
  onInterval: (finding: LabFinding, interval: LabInterval, index: number) => void;
};

/** Units of peak_value per kind, so "3.94" reads as "3.94 A". */
const PEAK_UNIT: Record<string, string> = {
  tracking: L.deg,
  track_offset: L.deg,
  jump: L.deg,
  overcurrent: "A",
  undervolt: "V",
  rx_gap: L.sec,
  overrun: "\u00b5s",
  jitter: "\u00b5s",
  foot_saturated: L.kg,
};

export function laneName(lane: string, joint: number | null, jointNames: string[]): string {
  if (joint != null) return `${joint} ${jointNames[joint] ?? ""}`;
  return LANE_LABEL[lane] ?? lane;
}

/** One-line facts under the title, specific to the kind. */
function detailLines(finding: LabFinding, jointNames: string[]): string[] {
  const out: string[] = [];
  const detail = finding.detail;
  const unit = PEAK_UNIT[finding.kind];
  if (finding.kind === "track_offset" && detail.median_deg != null) {
    out.push(`${L.median} ${detail.median_deg > 0 ? "+" : ""}${formatNumber(detail.median_deg, 2)}${L.deg}`);
  } else if (unit && finding.peak_value != null) {
    out.push(`${L.peak} ${formatNumber(finding.peak_value, 3)} ${unit}`);
  }
  if (detail.mag) {
    const parts = Object.entries(detail.mag)
      .filter(([code]) => code !== "0")
      .map(([code, count]) => `${MAG_LABEL[Number(code)] ?? code} ${count}`);
    if (parts.length) out.push(`${L.colMag}: ${parts.join(" / ")}`);
  }
  if (detail.dropped_total != null) out.push(`${L.dropped} ${detail.dropped_total}`);
  if (detail.i2c_total != null) out.push(`${L.i2cTotal} ${detail.i2c_total}`);
  if (finding.periodic_sec != null) out.push(fmt(L.periodicEvery, { sec: finding.periodic_sec.toFixed(2) }));
  if (detail.related?.length) {
    const text = detail.related.map((item) => `${laneName(`j${item.joint}`, item.joint, jointNames)} ${formatPct(item.ratio)}`);
    out.push(`${L.related}: ${text.join(", ")}`);
  }
  if (detail.mentioned?.length) {
    const text = detail.mentioned.map((item) => `${item.joint} (${item.count})`);
    out.push(`${L.mentioned}: ${text.join(", ")}`);
  }
  if (detail.stop_reason) out.push(detail.stop_reason);
  for (const text of detail.texts ?? []) out.push(text);
  return out;
}

export const FindingsPanel = memo(function FindingsPanel({
  findings,
  jointNames,
  thresholds,
  selectedId,
  activeInterval,
  showInfo,
  onShowInfo,
  onSelect,
  onInterval,
}: Props) {
  const [scope, setScope] = useState<Scope>("all");
  const [sort, setSort] = useState<Sort>("severity");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [showRules, setShowRules] = useState(false);

  const counts = useMemo(() => {
    const result = { 3: 0, 2: 0, 1: 0 } as Record<number, number>;
    for (const item of findings) result[item.severity] = (result[item.severity] ?? 0) + 1;
    return result;
  }, [findings]);

  const shown = useMemo(() => {
    const list = findings.filter((item) => {
      if (!showInfo && item.severity < 2) return false;
      if (scope === "joints") return item.joint != null;
      if (scope === "system") return item.joint == null;
      return true;
    });
    if (sort === "time") return [...list].sort((a, b) => a.first_offset - b.first_offset);
    return list;
  }, [findings, scope, sort, showInfo]);

  return (
    <section className="lab-findings">
      <header className="lab-findings-head">
        <h3 className="lab-section-title">{L.findingsTitle}</h3>
        <div className="lab-findings-counts">
          {[3, 2, 1].map((sev) => (
            <span key={sev} className="lab-count" style={{ color: SEV_COLOR[sev] }}>
              {SEVERITY_LABEL[sev]} {counts[sev] ?? 0}
            </span>
          ))}
        </div>
      </header>
      <div className="lab-findings-tools">
        <div className="lab-seg" role="group">
          {(
            [
              ["all", L.filterAll],
              ["joints", L.filterJoints],
              ["system", L.filterSystem],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={scope === value ? "is-on" : undefined}
              onClick={() => setScope(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="lab-seg" role="group">
          {(
            [
              ["severity", L.sortSeverity],
              ["time", L.sortTime],
            ] as const
          ).map(([value, label]) => (
            <button key={value} type="button" className={sort === value ? "is-on" : undefined} onClick={() => setSort(value)}>
              {label}
            </button>
          ))}
        </div>
        <label className="lab-check">
          <input type="checkbox" checked={showInfo} onChange={(event) => onShowInfo(event.target.checked)} />
          {L.showInfo}
        </label>
      </div>
      <p className="lab-muted lab-small">{L.findingNav}</p>

      {shown.length === 0 ? <p className="lab-muted">{L.noFindings}</p> : null}
      <ol className="lab-finding-list">
        {shown.map((finding) => {
          const expanded = open[finding.id] ?? false;
          const selected = finding.id === selectedId;
          const lines = detailLines(finding, jointNames);
          return (
            <li key={finding.id} className={selected ? "lab-finding is-selected" : "lab-finding"}>
              <div className="lab-finding-row">
                <span className="lab-sev-dot" style={{ background: SEV_COLOR[finding.severity] }} />
                <button type="button" className="lab-finding-main" onClick={() => onSelect(finding)}>
                  <span className="lab-finding-title">
                    <strong>{KIND_LABEL[finding.kind] ?? finding.kind}</strong>
                    <span className="lab-finding-lane">{laneName(finding.lane, finding.joint, jointNames)}</span>
                  </span>
                  <span className="lab-finding-meta">
                    {formatOffset(finding.first_offset, 0.1)}
                    {finding.last_offset > finding.first_offset ? ` \u2013 ${formatOffset(finding.last_offset, 0.1)}` : ""}
                    {" \u00b7 "}
                    {finding.interval_count} {L.intervals}
                    {" \u00b7 "}
                    {finding.sample_count.toLocaleString()} {L.samplesUnit} ({formatPct(finding.ratio, 1)})
                  </span>
                  {lines.length ? <span className="lab-finding-detail">{lines.join(" \u00b7 ")}</span> : null}
                </button>
                {finding.intervals.length > 1 ? (
                  <button
                    type="button"
                    className="lab-finding-toggle"
                    aria-expanded={expanded}
                    onClick={() => setOpen((prev) => ({ ...prev, [finding.id]: !expanded }))}
                  >
                    {expanded ? "\u25b4" : "\u25be"}
                  </button>
                ) : null}
              </div>
              {selected ? <p className="lab-finding-hint">{KIND_HINT[finding.kind]}</p> : null}
              {expanded ? (
                <ol className="lab-interval-list">
                  {finding.intervals.map((interval, index) => {
                    const active = activeInterval?.id === finding.id && activeInterval.index === index;
                    return (
                      <li key={`${interval.start_index}-${index}`}>
                        <button
                          type="button"
                          className={active ? "lab-interval is-active" : "lab-interval"}
                          onClick={() => onInterval(finding, interval, index)}
                        >
                          <span className="lab-sev-dot" style={{ background: SEV_COLOR[interval.severity] }} />
                          <span>
                            {formatOffset(interval.start_offset, 0.1)}
                            {interval.end_offset > interval.start_offset ? ` \u2013 ${formatOffset(interval.end_offset, 0.1)}` : ""}
                          </span>
                          <span className="lab-muted">
                            {interval.count} {L.samplesUnit}
                          </span>
                          {interval.peak_value != null ? (
                            <span className="lab-muted">
                              {L.peak} {formatNumber(interval.peak_value, 3)}
                            </span>
                          ) : null}
                        </button>
                      </li>
                    );
                  })}
                  {finding.interval_count > finding.intervals.length ? (
                    <li className="lab-muted">{fmt(L.moreIntervals, { n: finding.interval_count - finding.intervals.length })}</li>
                  ) : null}
                </ol>
              ) : null}
            </li>
          );
        })}
      </ol>

      <button type="button" className="lab-link-button" onClick={() => setShowRules((value) => !value)}>
        {L.thresholdsTitle} {showRules ? "\u25b4" : "\u25be"}
      </button>
      {showRules ? (
        <dl className="lab-rules">
          {Object.entries(thresholds).map(([key, value]) => (
            <div key={key}>
              <dt>{THRESHOLD_LABEL[key] ?? key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
});
