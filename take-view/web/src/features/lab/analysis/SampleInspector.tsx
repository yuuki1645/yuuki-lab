/**
 * Sample inspector: everything recorded at the picked instant.
 *
 * Reads the row exactly as stored on disk (the backend returns the parsed
 * object plus the original line), shows all ten axes side by side with
 * suspicious cells coloured, the firmware fields, both feet as a pressure
 * diagram, the detector verdicts at this row and the raw JSON.
 */

import { memo, useState } from "react";
import { KIND_LABEL, L, LANE_LABEL, MAG_LABEL, SEVERITY_LABEL } from "../labels";
import type { LabAnalysis, LabGamepadSample, LabPolicySample, LabSample } from "../types";
import { SEV_COLOR } from "./canvas";
import { formatClock, formatNumber, formatOffset } from "./plotMath";

type Props = {
  sample: LabSample | null;
  loading: boolean;
  analysis: LabAnalysis;
  focusJoint: number;
  onStep: (delta: number) => void;
  onCenter: () => void;
  onFocusJoint: (joint: number) => void;
};

type Tone = "bad" | "warn" | undefined;

const CORNER_KEYS = ["top_left", "top_right", "bottom_right", "bottom_left"] as const;

function at(row: Record<string, unknown>, key: string, index: number): unknown {
  const value = row[key];
  return Array.isArray(value) ? value[index] : undefined;
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** SM105BL reports its own angle. Magnet and INA cells are not faults. */
function feedbackServo(analysis: LabAnalysis, joint: number): boolean {
  return (analysis.context?.servos?.[joint] ?? "") === "SM105BL";
}

/** Cell text: numbers to 4 places, booleans as OK/NG, null as a gap. */
function cellText(value: unknown, digits = 4): string {
  if (value === null || value === undefined) return L.missing;
  if (typeof value === "boolean") return value ? "OK" : "NG";
  if (typeof value === "number") return formatNumber(value, digits);
  return String(value);
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** One key per line, arrays inline: readable without hiding any value. */
function prettyRow(row: Record<string, unknown>): string {
  const lines = Object.entries(row).map(([key, value]) => `  ${JSON.stringify(key)}: ${JSON.stringify(value)}`);
  return `{\n${lines.join(",\n")}\n}`;
}

export const SampleInspector = memo(function SampleInspector({
  sample,
  loading,
  analysis,
  focusJoint,
  onStep,
  onCenter,
  onFocusJoint,
}: Props) {
  const [showRaw, setShowRaw] = useState(false);
  const [copied, setCopied] = useState("");

  if (!sample || !sample.row) {
    return (
      <section className="lab-inspector">
        <h3 className="lab-section-title">{L.inspectorTitle}</h3>
        <p className="lab-muted">{loading ? L.loading : L.noCursor}</p>
      </section>
    );
  }

  const row = sample.row;
  const th = analysis.thresholds;
  const outMask = num(row.out_mask);
  const flags = Object.entries(sample.flags).sort((a, b) => b[1].sev - a[1].sev);

  const flash = async (text: string, label: string) => {
    if (await copyText(text)) {
      setCopied(label);
      window.setTimeout(() => setCopied(""), 1500);
    }
  };

  /** Colour a cell from the same rules the detectors use. */
  const tone = (joint: number, column: string): Tone => {
    const stats = analysis.joint_stats[joint];
    const asOk = at(row, "as_ok", joint);
    const mag = num(at(row, "mag", joint));
    const outOn = outMask != null && (outMask & (1 << joint)) !== 0;
    switch (column) {
      case "as_ok":
        return asOk === false ? "bad" : undefined;
      case "mag":
        if (feedbackServo(analysis, joint)) return undefined;
        if (mag == null || mag === 0 || mag === 255) return undefined;
        return mag === 2 || mag === 3 ? "warn" : "bad";
      case "map_ok":
        if (feedbackServo(analysis, joint)) return undefined;
        return at(row, "map_ok", joint) === false ? "warn" : undefined;
      case "ina_ok":
        if (feedbackServo(analysis, joint)) return undefined;
        return at(row, "ina_ok", joint) === false ? "warn" : undefined;
      case "err": {
        const cmd = num(at(row, "cmd", joint));
        const corr = num(at(row, "corr", joint));
        if (!outOn || cmd == null || corr == null) return undefined;
        const deviation = Math.abs(corr - cmd - (stats?.tracking.median_deg ?? 0));
        if (deviation >= th.track_crit_deg) return "bad";
        return deviation >= th.track_warn_deg ? "warn" : undefined;
      }
      case "amp": {
        if (feedbackServo(analysis, joint)) return undefined;
        const amp = num(at(row, "amp", joint));
        if (amp == null) return undefined;
        if (amp >= th.amp_crit) return "bad";
        return amp >= th.amp_warn ? "warn" : undefined;
      }
      case "volt": {
        if (feedbackServo(analysis, joint)) return undefined;
        const volt = num(at(row, "volt", joint));
        const ref = stats?.power.volt_powered_median;
        if (volt == null || ref == null) return undefined;
        return volt < ref * th.volt_sag_ratio && volt > ref * th.volt_off_ratio ? "warn" : undefined;
      }
      default:
        return undefined;
    }
  };

  const jointRows = Array.from({ length: 10 }, (_, joint) => {
    const cmd = num(at(row, "cmd", joint));
    const corr = num(at(row, "corr", joint));
    const outOn = outMask != null && (outMask & (1 << joint)) !== 0;
    const mag = num(at(row, "mag", joint));
    return {
      joint,
      cells: [
        { key: "cmd", value: at(row, "cmd", joint) },
        { key: "raw", value: at(row, "raw", joint) },
        { key: "unwrap", value: at(row, "unwrap", joint) },
        { key: "corr", value: at(row, "corr", joint) },
        { key: "err", value: cmd != null && corr != null ? corr - cmd : null },
        { key: "as_ok", value: at(row, "as_ok", joint) },
        { key: "mag", value: mag == null ? null : MAG_LABEL[mag] ?? mag },
        { key: "agc", value: at(row, "agc", joint) },
        { key: "map_ok", value: at(row, "map_ok", joint) },
        { key: "volt", value: at(row, "volt", joint) },
        { key: "amp", value: at(row, "amp", joint) },
        { key: "watt", value: at(row, "watt", joint) },
        { key: "ina_ok", value: at(row, "ina_ok", joint) },
        { key: "out", value: outMask == null ? null : outOn },
      ],
    };
  });

  const sysFields: Array<[string, unknown]> = [
    ["seq", row.seq],
    ["period_us", row.period_us],
    ["loop_us", row.loop_us],
    ["sense_us", row.sense_us],
    ["jitter_us", row.jitter_us],
    ["overrun", row.overrun],
    ["i2c_err", row.i2c_err],
    ["servo_ok", row.servo_ok],
    ["mode", row.mode],
    ["out_mask", row.out_mask],
  ];

  return (
    <section className="lab-inspector">
      <header className="lab-inspector-head">
        <h3 className="lab-section-title">{L.inspectorTitle}</h3>
        <div className="lab-inspector-nav">
          <button type="button" className="btn btn-sm" onClick={() => onStep(-1)} disabled={sample.index <= 0}>
            {"\u25c0"} {L.prev}
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onStep(1)} disabled={sample.index >= sample.total - 1}>
            {L.next} {"\u25b6"}
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onCenter}>
            {L.center}
          </button>
        </div>
      </header>

      <dl className="lab-inspector-id">
        <div>
          <dt>{L.sampleNo}</dt>
          <dd>
            #{sample.index.toLocaleString()} / {sample.total.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt>{L.time}</dt>
          <dd>
            +{formatOffset(sample.t_offset, 0.001)} ({formatClock(analysis.t0, sample.t_offset)})
          </dd>
        </div>
        <div>
          <dt>t</dt>
          <dd>{sample.t.toFixed(6)}</dd>
        </div>
        <div>
          <dt>{L.file}</dt>
          <dd>
            <button
              type="button"
              className="lab-link-button"
              title={L.copy}
              onClick={() => flash(`${sample.part}:${sample.line}`, "file")}
            >
              {sample.part}:{sample.line}
            </button>
            {copied === "file" ? <span className="lab-copied">{L.copied}</span> : null}
          </dd>
        </div>
      </dl>

      <div className="lab-flags">
        <span className="lab-muted lab-small">{L.flagsHere}</span>
        {flags.length === 0 ? <span className="lab-muted lab-small">{L.noFlags}</span> : null}
        {flags.map(([lane, flag]) => {
          const joint = lane.startsWith("j") ? Number(lane.slice(1)) : null;
          const name = joint != null ? `${joint} ${analysis.joint_names[joint] ?? ""}` : LANE_LABEL[lane] ?? lane;
          return (
            <span key={lane} className="lab-flag-chip" style={{ borderColor: SEV_COLOR[flag.sev] }}>
              <span className="lab-sev-dot" style={{ background: SEV_COLOR[flag.sev] }} />
              {name}: {KIND_LABEL[flag.kind] ?? flag.kind}
              <span className="lab-muted">{SEVERITY_LABEL[flag.sev]}</span>
            </span>
          );
        })}
      </div>

      <div className="lab-table-wrap">
        <table className="lab-table lab-matrix">
          <thead>
            <tr>
              <th>{L.colJoint}</th>
              <th>{L.colCmd}</th>
              <th>{L.colRaw}</th>
              <th>{L.colUnwrap}</th>
              <th>{L.colCorr}</th>
              <th>{L.colErr}</th>
              <th>{L.colAs}</th>
              <th>{L.colMag}</th>
              <th>{L.colAgc}</th>
              <th>{L.colMap}</th>
              <th>{L.colVolt}</th>
              <th>{L.colAmp}</th>
              <th>{L.colWatt}</th>
              <th>{L.colIna}</th>
              <th>{L.colOut}</th>
            </tr>
          </thead>
          <tbody>
            {jointRows.map(({ joint, cells }) => (
              <tr key={joint} className={joint === focusJoint ? "is-selected" : undefined}>
                <td>
                  <button type="button" className="lab-take-link" onClick={() => onFocusJoint(joint)}>
                    {joint} {analysis.joint_names[joint]}
                  </button>
                </td>
                {cells.map((cell) => {
                  const cellTone = tone(joint, cell.key);
                  const missing = cell.value === null || cell.value === undefined;
                  const className = [cellTone ? `lab-cell-${cellTone}` : "", missing ? "lab-cell-missing" : ""]
                    .filter(Boolean)
                    .join(" ");
                  return (
                    <td key={cell.key} className={className || undefined} title={missing ? undefined : String(cell.value)}>
                      {cellText(cell.value, cell.key === "agc" ? 0 : 4)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="lab-inspector-grid">
        <div>
          <h4 className="lab-sub-title">{L.sysFields}</h4>
          <dl className="lab-kv">
            {sysFields.map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd className={key === "overrun" && value === true ? "lab-cell-bad" : undefined}>{cellText(value, 0)}</dd>
              </div>
            ))}
          </dl>
          {outMask != null ? (
            <div className="lab-bits" title={L.bitsOut}>
              {Array.from({ length: 10 }, (_, bit) => (
                <span key={bit} className={(outMask & (1 << bit)) !== 0 ? "lab-bit is-on" : "lab-bit"}>
                  {bit}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <div>
          <h4 className="lab-sub-title">{L.feet}</h4>
          <div className="lab-feet">
            <FootPad label={L.footRightShort} payload={row.foot} rated={th.foot_rated_kg} />
            <FootPad label={L.footLeftShort} payload={row.foot_left} rated={th.foot_rated_kg} />
          </div>
        </div>
      </div>

      {analysis.gamepad ? (
        <div className="lab-pad-readout">
          <h4 className="lab-sub-title">{L.padTitle}</h4>
          {sample.gamepad?.row ? (
            <PadReadout pad={sample.gamepad} />
          ) : (
            <p className="lab-muted lab-small">{L.padBefore}</p>
          )}
        </div>
      ) : null}

      {analysis.policy ? (
        <div className="lab-pad-readout">
          <h4 className="lab-sub-title">{L.policyTitle}</h4>
          {sample.policy?.row ? (
            <PolicyReadout
              policy={sample.policy}
              focusJoint={focusJoint}
              policyIndex={analysis.context?.policy_of_fw?.[focusJoint] ?? -1}
              jointName={analysis.joint_names[focusJoint] ?? ""}
            />
          ) : (
            <p className="lab-muted lab-small">{L.policyBefore}</p>
          )}
        </div>
      ) : null}

      <div className="lab-raw">
        <div className="lab-raw-head">
          <button type="button" className="lab-link-button" onClick={() => setShowRaw((value) => !value)}>
            {showRaw ? L.hideRaw : L.showRaw}
          </button>
          {sample.raw_line ? (
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => flash(sample.raw_line ?? "", "raw")}>
              {L.copy}
            </button>
          ) : null}
          {copied === "raw" ? <span className="lab-copied">{L.copied}</span> : null}
        </div>
        {showRaw ? (
          <>
            <p className="lab-muted lab-small">{L.rawJson}</p>
            <pre className="lab-raw-json">{prettyRow(row)}</pre>
          </>
        ) : null}
      </div>
    </section>
  );
});

/**
 * The policy file's own row nearest this sensor time.
 * Arrays in that row are in policy order, so the focused axis is picked
 * with policy_of_fw from context.json rather than the array index.
 */
function PolicyReadout({
  policy,
  focusJoint,
  policyIndex,
  jointName,
}: {
  policy: LabPolicySample;
  focusJoint: number;
  policyIndex: number;
  jointName: string;
}) {
  const row = policy.row ?? {};
  const atIndex = (key: string): unknown => {
    if (policyIndex < 0) return undefined;
    const value = row[key];
    return Array.isArray(value) ? value[policyIndex] : undefined;
  };
  return (
    <>
      <p className="lab-muted lab-small">
        {L.policyHeld}
        {" \u00b7 "}
        {policy.part}:{policy.line}
        {" \u00b7 +"}
        {formatOffset(policy.t_offset, 0.001)}
      </p>
      <dl className="lab-kv">
        <div>
          <dt>{L.policyReason}</dt>
          <dd>{cellText(row.reason_text || row.reason, 0)}</dd>
        </div>
        <div>
          <dt>{L.policySafety}</dt>
          <dd>{cellText(row.safety_text || row.safety, 0)}</dd>
        </div>
        <div>
          <dt>{L.stBearing}</dt>
          <dd>{cellText(row.foot_bearing)}</dd>
        </div>
        <div>
          <dt>{L.stDist}</dt>
          <dd>{cellText(row.dist_ok)}</dd>
        </div>
        <div>
          <dt>
            {focusJoint} {jointName}
          </dt>
          <dd>
            {L.sObs} {cellText(atIndex("obs"), 4)}
            {" \u00b7 "}
            {L.sActionRad} {cellText(atIndex("action_rad"), 4)}
            {" \u00b7 "}
            {L.sPolCmd} {cellText(atIndex("cmd_rad"), 4)}
          </dd>
        </div>
      </dl>
    </>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function heelText(value: unknown): string {
  if (!Array.isArray(value)) return L.missing;
  return value.map((item) => (typeof item === "number" ? item.toFixed(4) : L.missing)).join(", ");
}

/**
 * The pad file's own row at this sensor time. Accepted here is that row's
 * flag. The chart's accepted strip is 1 when any row in the sensor interval
 * advanced, so the two can disagree at the end of a burst.
 */
function PadReadout({ pad }: { pad: LabGamepadSample }) {
  const row = pad.row ?? {};
  return (
    <>
      <p className="lab-muted lab-small">
        {L.padHeld}
        {" \u00b7 "}
        {pad.part}:{pad.line}
        {" \u00b7 +"}
        {formatOffset(pad.t_offset, 0.001)}
      </p>
      <dl className="lab-kv">
        <div>
          <dt>{L.padConnected}</dt>
          <dd>{cellText(row.connected)}</dd>
        </div>
        <div>
          <dt>{L.padHoming}</dt>
          <dd>{cellText(row.homing)}</dd>
        </div>
      </dl>
      <div className="lab-inspector-grid">
        <PadSide
          label={L.padLeft}
          stick={asRecord(row.left)}
          accepted={row.accepted_left}
          floorHold={row.floor_hold_left}
          heel={row.heel_left}
        />
        <PadSide
          label={L.padRight}
          stick={asRecord(row.right)}
          accepted={row.accepted_right}
          floorHold={row.floor_hold_right}
          heel={row.heel_right}
        />
      </div>
    </>
  );
}

function PadSide({
  label,
  stick,
  accepted,
  floorHold,
  heel,
}: {
  label: string;
  stick: Record<string, unknown>;
  accepted: unknown;
  floorHold: unknown;
  heel: unknown;
}) {
  return (
    <div>
      <h4 className="lab-sub-title">{label}</h4>
      <dl className="lab-kv">
        <div>
          <dt>{L.padForward}</dt>
          <dd>{cellText(stick.forward, 3)}</dd>
        </div>
        <div>
          <dt>{L.padLateral}</dt>
          <dd>{cellText(stick.lateral, 3)}</dd>
        </div>
        <div>
          <dt>{L.padVertical}</dt>
          <dd>{cellText(stick.vertical, 3)}</dd>
        </div>
        <div>
          <dt>{L.padAcceptRow}</dt>
          <dd>{cellText(accepted)}</dd>
        </div>
        <div>
          <dt>{L.padFloor}</dt>
          <dd>{cellText(floorHold)}</dd>
        </div>
        <div>
          <dt>{L.padHeel}</dt>
          <dd>{heelText(heel)}</dd>
        </div>
      </dl>
    </div>
  );
}

/**
 * Foot as seen from above: four corner load cells as circles sized by
 * load (relative to the 2 kg rating) and the centre of pressure as a dot.
 */
function FootPad({ label, payload, rated }: { label: string; payload: unknown; rated: number }) {
  const foot = (payload && typeof payload === "object" ? payload : {}) as Record<string, unknown>;
  const ok = foot.ok === true;
  const mask = num(foot.mask);
  const corners = (foot.corners && typeof foot.corners === "object" ? foot.corners : {}) as Record<string, unknown>;
  const loads = CORNER_KEYS.map((key) => {
    const corner = corners[key];
    return corner && typeof corner === "object" ? num((corner as Record<string, unknown>).force_kg) : null;
  });
  const total = loads.every((value) => value != null) ? loads.reduce((sum, value) => sum + (value ?? 0), 0) : null;
  // Same convention as the backend cop_x / cop_y: x right minus left, y top minus bottom.
  const cop =
    ok && total != null && total > 0.02
      ? {
          x: ((loads[1] ?? 0) + (loads[2] ?? 0) - (loads[0] ?? 0) - (loads[3] ?? 0)) / total,
          y: ((loads[0] ?? 0) + (loads[1] ?? 0) - (loads[3] ?? 0) - (loads[2] ?? 0)) / total,
        }
      : null;
  const W = 120;
  const H = 150;
  const pos = [
    { x: 24, y: 26 },
    { x: W - 24, y: 26 },
    { x: W - 24, y: H - 26 },
    { x: 24, y: H - 26 },
  ];
  return (
    <figure className="lab-foot">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        <rect x={6} y={6} width={W - 12} height={H - 12} rx={18} className={ok ? "lab-foot-outline" : "lab-foot-outline is-off"} />
        {pos.map((point, index) => {
          const load = ok ? loads[index] : null;
          const fitted = mask == null || (mask & (1 << index)) !== 0;
          const share = load == null ? 0 : Math.min(1, Math.max(0, load / rated));
          const over = load != null && load >= rated;
          const missing = ok && fitted && load == null;
          return (
            <g key={CORNER_KEYS[index]}>
              <circle
                cx={point.x}
                cy={point.y}
                r={6 + share * 14}
                className={over ? "lab-foot-cell is-over" : missing ? "lab-foot-cell is-missing" : "lab-foot-cell"}
                style={{ opacity: load == null ? 0.35 : 0.35 + share * 0.65 }}
              />
              <text x={point.x} y={point.y + (index < 2 ? 30 : -24)} className="lab-foot-text" textAnchor="middle">
                {load == null ? L.dash : load.toFixed(2)}
              </text>
            </g>
          );
        })}
        {cop ? <circle cx={W / 2 + (cop.x * (W - 48)) / 2} cy={H / 2 - (cop.y * (H - 52)) / 2} r={5} className="lab-foot-cop" /> : null}
      </svg>
      <figcaption>
        <strong>{label}</strong> {L.footOk} {ok ? "OK" : "NG"}
        <br />
        {L.total} {ok ? cellText(foot.force_kg, 3) : L.missing} {L.kg}
        {mask != null ? ` \u00b7 ${L.fitted} 0b${mask.toString(2).padStart(4, "0")}` : ""}
      </figcaption>
    </figure>
  );
}
