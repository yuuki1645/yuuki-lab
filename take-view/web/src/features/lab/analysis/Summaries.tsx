/**
 * Take-level summaries: per-joint health table, link / timing card and
 * the event + command log. All numbers here cover the whole take; the
 * plots and range stats cover the visible range.
 */

import { memo, useMemo, useState } from "react";
import { L, MAG_LABEL, fmt } from "../labels";
import type { LabAnalysis, LabCommand, LabEventLevel, LabJointStats, LabMarkerEvent } from "../types";
import { SEV_COLOR } from "./canvas";
import { formatNumber, formatOffset, formatPct, type View } from "./plotMath";

type Tone = "bad" | "warn" | undefined;

function cls(tone: Tone): string | undefined {
  return tone ? `lab-cell-${tone}` : undefined;
}

/** Magnet status codes other than "ok" with their row counts. */
function magSummary(counts: Record<string, number>): { text: string; tone: Tone } {
  const parts = Object.entries(counts).filter(([code]) => code !== "0" && code !== "255");
  if (!parts.length) return { text: MAG_LABEL[0], tone: undefined };
  const bad = parts.some(([code]) => code === "1" || code === "4");
  return {
    text: parts.map(([code, count]) => `${MAG_LABEL[Number(code)] ?? code} ${count}`).join(" / "),
    tone: bad ? "bad" : "warn",
  };
}

type JointProps = {
  stats: LabJointStats[];
  thresholds: Record<string, number>;
  focusJoint: number;
  /** Servo model per axis. SM105BL has no magnet and no INA226. */
  servos?: string[];
  onFocusJoint: (joint: number) => void;
  onPickIndex: (index: number) => void;
};

export const JointTable = memo(function JointTable({ stats, thresholds: th, focusJoint, servos, onFocusJoint, onPickIndex }: JointProps) {
  return (
    <section className="lab-card-block">
      <h3 className="lab-section-title">{L.jointTableTitle}</h3>
      <div className="lab-table-wrap">
        <table className="lab-table lab-joint-table">
          <thead>
            <tr>
              <th>{L.colJoint}</th>
              <th>{L.colOnline}</th>
              <th>{L.colAsOk}</th>
              <th>{L.colDropout}</th>
              <th>{L.colMagState}</th>
              <th>{L.colAgcRange}</th>
              <th>{L.colOutRatio}</th>
              <th>{L.colTrack}</th>
              <th>{L.colJumps}</th>
              <th>{L.colAmpMax}</th>
              <th>{L.colVoltState}</th>
              <th>{L.colFindings}</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((item) => {
              const feedback = (servos?.[item.index] ?? "") === "SM105BL";
              const mag = magSummary(item.mag_counts);
              const track = item.tracking;
              const median = track.median_deg;
              const medianTone: Tone =
                median == null
                  ? undefined
                  : Math.abs(median) >= th.offset_crit_deg
                    ? "bad"
                    : Math.abs(median) >= th.offset_warn_deg
                      ? "warn"
                      : undefined;
              const maxTone: Tone =
                track.max_abs_deg == null ? undefined : track.max_abs_deg >= th.track_crit_deg + Math.abs(median ?? 0) ? "bad" : undefined;
              const ampTone: Tone =
                item.power.amp_max == null
                  ? undefined
                  : item.power.amp_max >= th.amp_crit
                    ? "bad"
                    : item.power.amp_max >= th.amp_warn
                      ? "warn"
                      : undefined;
              const asTone: Tone = item.as_ok_ratio == null ? undefined : item.as_ok_ratio < 0.99 ? "bad" : item.as_ok_ratio < 1 ? "warn" : undefined;
              const worst = item.crit ? 3 : item.warn ? 2 : 0;
              return (
                <tr key={item.index} className={item.index === focusJoint ? "is-selected" : undefined}>
                  <td>
                    <button type="button" className="lab-take-link" onClick={() => onFocusJoint(item.index)}>
                      <span className="lab-sev-dot" style={{ background: worst ? SEV_COLOR[worst] : "rgba(61, 220, 132, 0.7)" }} />
                      {item.index} {item.name}
                    </button>
                  </td>
                  <td>{formatPct(item.online_ratio)}</td>
                  <td className={cls(asTone)}>{formatPct(item.as_ok_ratio, 1)}</td>
                  <td className={cls(item.dropout_samples > 0 ? "bad" : undefined)}>{item.dropout_samples.toLocaleString()}</td>
                  <td className={cls(feedback ? undefined : mag.tone)}>{feedback ? L.dash : mag.text}</td>
                  <td>
                    {feedback
                      ? L.dash
                      : `${formatNumber(item.agc_median, 0)}${item.agc_min != null ? ` (${item.agc_min}\u2013${item.agc_max})` : ""}`}
                  </td>
                  <td>{formatPct(item.out_ratio)}</td>
                  <td>
                    <span className={cls(medianTone)}>
                      {median == null ? L.dash : `${median > 0 ? "+" : ""}${formatNumber(median, 2)}`}
                    </span>
                    {" / "}
                    {formatNumber(track.p95_abs_deg, 2)}
                    {" / "}
                    {track.max_index != null ? (
                      <button type="button" className={`lab-take-link ${cls(maxTone) ?? ""}`} onClick={() => onPickIndex(track.max_index as number)}>
                        {formatNumber(track.max_abs_deg, 2)}
                      </button>
                    ) : (
                      formatNumber(track.max_abs_deg, 2)
                    )}
                  </td>
                  <td className={cls(item.jump_count > 0 ? "warn" : undefined)}>{item.jump_count}</td>
                  <td>
                    {feedback ? (
                      L.dash
                    ) : (
                      <>
                        {formatNumber(item.power.amp_p99, 3)}
                        {" / "}
                        {item.power.amp_max_index != null ? (
                          <button
                            type="button"
                            className={`lab-take-link ${cls(ampTone) ?? ""}`}
                            onClick={() => onPickIndex(item.power.amp_max_index as number)}
                          >
                            {formatNumber(item.power.amp_max, 3)}
                          </button>
                        ) : (
                          formatNumber(item.power.amp_max, 3)
                        )}
                      </>
                    )}
                  </td>
                  <td className={cls(!feedback && item.power.volt_sag_samples > 0 ? "warn" : undefined)}>
                    {feedback
                      ? L.dash
                      : `${formatNumber(item.power.volt_powered_median, 2)} / ${formatNumber(item.power.volt_powered_min, 2)}`}
                  </td>
                  <td>
                    {item.crit ? <span style={{ color: SEV_COLOR[3] }}>{item.crit}</span> : null}
                    {item.crit && item.warn ? " / " : null}
                    {item.warn ? <span style={{ color: SEV_COLOR[2] }}>{item.warn}</span> : null}
                    {!item.crit && !item.warn ? L.dash : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
});

export const SystemCard = memo(function SystemCard({ analysis }: { analysis: LabAnalysis }) {
  const s = analysis.system_stats;
  const th = analysis.thresholds;
  const rows: Array<[string, string, Tone]> = [
    [L.rate, s.rate_hz == null ? L.dash : `${formatNumber(s.rate_hz, 2)} Hz`, undefined],
    [
      L.period,
      `${formatNumber(s.period_mean_us, 0)} \u00b1 ${formatNumber(s.period_std_us, 0)} \u00b5s`,
      undefined,
    ],
    [L.periodMax, `${formatNumber(s.period_max_us, 0)} \u00b5s`, (s.period_max_us ?? 0) > (s.target_period_us ?? 50000) * 2 ? "bad" : undefined],
    [L.loopTime, `${formatNumber(s.loop_p99_us, 0)} / ${formatNumber(s.loop_max_us, 0)} \u00b5s`, undefined],
    [L.senseTime, `${formatNumber(s.sense_median_us, 0)} / ${formatNumber(s.sense_max_us, 0)} \u00b5s`, undefined],
    [
      L.rxInterval,
      `${formatNumber(s.dt_median_ms, 1)} / ${formatNumber(s.dt_p99_ms, 1)} / ${formatNumber(s.dt_max_ms, 1)} ms`,
      (s.dt_max_ms ?? 0) >= th.rx_gap_crit_sec * 1000 ? "bad" : undefined,
    ],
    [
      L.seqDrops,
      `${s.seq_drop_events} / ${s.seq_dropped_total}${
        s.seq_drop_periodic_sec != null ? ` (${fmt(L.periodicEvery, { sec: s.seq_drop_periodic_sec.toFixed(2) })})` : ""
      }`,
      s.seq_drop_events > 0 ? "warn" : undefined,
    ],
    [L.rxGaps, `${s.rx_gap_count} / ${formatNumber(s.rx_gap_max_sec, 2)} ${L.sec}`, s.rx_gap_count > 0 ? "warn" : undefined],
    [L.overrunCount, String(s.overrun_count), s.overrun_count > 0 ? "warn" : undefined],
    [L.i2cDelta, s.i2c_delta == null ? L.dash : `${s.i2c_delta} (${s.i2c_start} \u2192 ${s.i2c_end})`, (s.i2c_delta ?? 0) > 0 ? "warn" : undefined],
    [L.i2cPeak, formatNumber(s.i2c_max_per_sec, 0), (s.i2c_max_per_sec ?? 0) >= th.i2c_crit_per_sec ? "bad" : undefined],
    [L.servoOk, formatPct(s.servo_ok_ratio, 1), (s.servo_ok_ratio ?? 1) < 1 ? "warn" : undefined],
    [L.footOkRatio, `${formatPct(s.foot_ok_ratio, 1)} / ${formatPct(s.foot_left_ok_ratio, 1)}`, undefined],
    [L.modes, s.modes.join(", ") || L.dash, undefined],
  ];
  return (
    <section className="lab-card-block">
      <h3 className="lab-section-title">{L.systemTitle}</h3>
      <dl className="lab-kv lab-kv-wide">
        {rows.map(([label, value, tone]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className={cls(tone)}>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
});

type LogProps = {
  events: LabMarkerEvent[];
  eventsTotal: number;
  commands: LabCommand[];
  commandsTotal: number;
  view: View;
  cursorT: number | null;
  onPickTime: (t: number) => void;
};

/** Rows shown at once. The rest is reachable by narrowing the view. */
const LOG_LIMIT = 600;

export const EventLog = memo(function EventLog({ events, eventsTotal, commands, commandsTotal, view, cursorT, onPickTime }: LogProps) {
  const [tab, setTab] = useState<"events" | "commands">("events");
  const [levels, setLevels] = useState<Record<LabEventLevel, boolean>>({ error: true, warn: true, info: true });
  const [inView, setInView] = useState(false);

  const shownEvents = useMemo(
    () =>
      events.filter((event) => {
        if (!levels[event.level]) return false;
        if (inView && (event.offset == null || event.offset < view.from || event.offset > view.to)) return false;
        return true;
      }),
    [events, levels, inView, view]
  );
  const shownCommands = useMemo(
    () => commands.filter((command) => !inView || (command.offset >= view.from && command.offset <= view.to)),
    [commands, inView, view]
  );

  const levelLabel: Record<LabEventLevel, string> = { error: L.levelError, warn: L.levelWarn, info: L.levelInfo };
  const nearCursor = (offset: number | null) => cursorT != null && offset != null && Math.abs(offset - cursorT) < 0.05;

  return (
    <section className="lab-card-block">
      <header className="lab-data-head">
        <div className="lab-seg" role="tablist">
          <button type="button" className={tab === "events" ? "is-on" : undefined} onClick={() => setTab("events")}>
            {L.eventsTitle} ({eventsTotal})
          </button>
          <button type="button" className={tab === "commands" ? "is-on" : undefined} onClick={() => setTab("commands")}>
            {L.commandsTitle} ({commandsTotal})
          </button>
        </div>
        <div className="lab-findings-tools">
          {tab === "events"
            ? (["error", "warn", "info"] as const).map((level) => (
                <label key={level} className="lab-check">
                  <input
                    type="checkbox"
                    checked={levels[level]}
                    onChange={(event) => setLevels((prev) => ({ ...prev, [level]: event.target.checked }))}
                  />
                  {levelLabel[level]}
                </label>
              ))
            : null}
          <label className="lab-check">
            <input type="checkbox" checked={inView} onChange={(event) => setInView(event.target.checked)} />
            {L.onlyInView}
          </label>
        </div>
      </header>
      {tab === "events" ? (
        <ul className="lab-events">
          {shownEvents.length === 0 ? <li className="lab-muted">{L.noEvents}</li> : null}
          {shownEvents.slice(0, LOG_LIMIT).map((event, index) => {
            const visible = event.offset != null && event.offset >= view.from && event.offset <= view.to;
            return (
              <li
                key={`${event.offset ?? "x"}-${index}`}
                className={[`lab-event-${event.level}`, visible ? "is-visible" : "", nearCursor(event.offset) ? "is-cursor" : ""].join(" ")}
              >
                <button
                  type="button"
                  className="lab-event-time lab-take-link"
                  disabled={event.offset == null}
                  onClick={() => event.offset != null && onPickTime(event.offset)}
                >
                  {event.offset == null ? L.dash : formatOffset(event.offset, 0.01)}
                </button>
                <span>{event.text}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <ul className="lab-events">
          {shownCommands.length === 0 ? <li className="lab-muted">{L.noEvents}</li> : null}
          {shownCommands.slice(0, LOG_LIMIT).map((command, index) => (
            <li key={`${command.offset}-${index}`} className={nearCursor(command.offset) ? "is-cursor" : undefined}>
              <button type="button" className="lab-event-time lab-take-link" onClick={() => onPickTime(command.offset)}>
                {formatOffset(command.offset, 0.01)}
              </button>
              <span>
                {command.text}
                {command.ch != null ? ` ch=${command.ch}` : ""}
                {command.deg != null ? ` deg=${command.deg}` : ""}
                {command.on != null ? ` on=${String(command.on)}` : ""}
                {command.mode != null ? ` mode=${command.mode}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
      {(tab === "events" ? shownEvents.length : shownCommands.length) > LOG_LIMIT ? (
        <p className="lab-muted lab-small">{fmt(L.eventsMore, { n: tab === "events" ? shownEvents.length : shownCommands.length })}</p>
      ) : null}
    </section>
  );
});
