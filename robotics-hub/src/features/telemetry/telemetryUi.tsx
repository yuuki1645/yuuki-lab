import { memo, useMemo } from "react";
import type { ImuDaemonSamplePayload } from "@/shared/types/imuDaemon";

export type LogicalRange = { lo: number; hi: number };

export const LOGICAL_RANGE_BY_ACTUATOR: Record<string, LogicalRange> = {
  left_hip_roll_motor: { lo: -30, hi: 90 },
  left_hip_pitch_motor: { lo: -30, hi: 120 },
  left_knee_pitch_motor: { lo: 0, hi: 120 },
  left_ankle_pitch_motor: { lo: -50, hi: 90 },
  left_ankle_roll_motor: { lo: -20, hi: 20 },
  right_hip_roll_motor: { lo: -30, hi: 90 },
  right_hip_pitch_motor: { lo: -30, hi: 120 },
  right_knee_pitch_motor: { lo: 0, hi: 120 },
  right_ankle_pitch_motor: { lo: -50, hi: 90 },
  right_ankle_roll_motor: { lo: -20, hi: 20 },
};

export const ACC_LABELS = ["ax", "ay", "az"];
export const GYRO_LABELS = ["gx", "gy", "gz"];
export const ANGLE_LABELS = ["pitch", "roll", "yaw"];
export const ZAXIS_LABELS = ["zx", "zy", "zz"];
export const FOOT_LABELS = ["左接地", "右接地", "左足 dx", "右足 dx"];

export const RAD_TO_DEG = 180 / Math.PI;

function intPartWidth1dp(values: number[]): number {
  let m = 1;
  for (const v of values) {
    if (typeof v !== "number" || !Number.isFinite(v)) continue;
    const s = v.toFixed(1);
    const dot = s.indexOf(".");
    if (dot <= 0) continue;
    m = Math.max(m, s.slice(0, dot).length);
  }
  return m;
}

function formatValue1dpAligned(v: number | undefined, intWidth: number): string {
  if (typeof v !== "number" || !Number.isFinite(v)) {
    return "\u2014".padStart(intWidth + 2, "\u00a0");
  }
  const s = v.toFixed(1);
  const dot = s.indexOf(".");
  const intSide = dot > 0 ? s.slice(0, dot) : s;
  const decSide = dot > 0 ? s.slice(dot) : "";
  return intSide.padStart(intWidth, "\u00a0") + decSide;
}

export function ScalarPanel({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="telemetry__panel">
      <h2>{title}</h2>
      <table>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td className="telemetry__td-num">{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function VecTable({
  title,
  labels,
  values,
  valueHeader = "値",
  ranges,
  noPanel = false,
  showTitle = true,
}: {
  title: string;
  labels: string[];
  values: number[];
  valueHeader?: string;
  ranges?: Array<LogicalRange | null>;
  noPanel?: boolean;
  showTitle?: boolean;
}) {
  const intWidth = useMemo(() => intPartWidth1dp(values), [values]);
  const showBars = Boolean(ranges?.length);

  const content = (
    <>
      {showTitle && title ? <h2>{title}</h2> : null}
      {values.length === 0 ? (
        <p className="telemetry__empty">データ待ち</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>軸 / 関節</th>
              {showBars && <th className="telemetry__th-pos">位置</th>}
              <th className="telemetry__th-num">{valueHeader}</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((lab, i) => {
              const v = values[i];
              const r = ranges?.[i] ?? null;
              const hasRange =
                r !== null &&
                typeof v === "number" &&
                Number.isFinite(r.lo) &&
                Number.isFinite(r.hi) &&
                r.hi > r.lo &&
                Number.isFinite(v);
              const ratio =
                hasRange && r !== null ? Math.max(0, Math.min(1, (v - r.lo) / (r.hi - r.lo))) : 0;
              return (
                <tr key={lab}>
                  <td>{lab}</td>
                  {showBars && (
                    <td className="telemetry__td-pos">
                      {hasRange ? (
                        <div className="telemetry__range-cell">
                          <div className="telemetry__range-track">
                            <div
                              className="telemetry__range-fill"
                              style={{ width: `${(ratio * 100).toFixed(1)}%` }}
                            />
                            <div className="telemetry__range-midline" />
                          </div>
                          <span className="telemetry__range-label">
                            {r.lo}..{r.hi}
                          </span>
                        </div>
                      ) : (
                        <span className="telemetry__range-label">—</span>
                      )}
                    </td>
                  )}
                  <td className="telemetry__td-num">
                    <span className="telemetry__num-fixed">
                      {formatValue1dpAligned(values[i], intWidth)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );

  if (noPanel) return content;
  return <div className="telemetry__panel">{content}</div>;
}

function triplet(
  a: number | undefined,
  b: number | undefined,
  c: number | undefined
): number[] {
  if (
    typeof a === "number" &&
    Number.isFinite(a) &&
    typeof b === "number" &&
    Number.isFinite(b) &&
    typeof c === "number" &&
    Number.isFinite(c)
  ) {
    return [a, b, c];
  }
  return [];
}

export function daemonSampleToAccelGyroAngle(s: ImuDaemonSamplePayload | null): {
  acc: number[];
  gyro: number[];
  angle: number[];
} {
  if (!s) {
    return { acc: [], gyro: [], angle: [] };
  }
  return {
    acc: triplet(s.accel?.x, s.accel?.y, s.accel?.z),
    gyro: triplet(s.gyro?.x, s.gyro?.y, s.gyro?.z),
    angle: triplet(s.angle?.pitch, s.angle?.roll, s.angle?.yaw),
  };
}

export const ImuPerfTimestampReadout = memo(function ImuPerfTimestampReadout({
  perfS,
}: {
  perfS: number | undefined;
}) {
  if (typeof perfS !== "number" || !Number.isFinite(perfS)) {
    return <span className="telemetry__perf-value">—</span>;
  }
  return <span className="telemetry__perf-value">{perfS.toFixed(9)}</span>;
});

export function wsStatusLabel(
  status: "connected" | "connecting" | "disconnected"
): string {
  if (status === "connected") return "接続中";
  if (status === "connecting") return "接続試行中";
  return "未接続";
}
