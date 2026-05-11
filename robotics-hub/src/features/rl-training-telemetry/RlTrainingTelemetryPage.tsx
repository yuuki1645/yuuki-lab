import { useMemo } from "react";
import { useRlTelemetryStream } from "@/shared/hooks/useRlTelemetryStream";
import "./RlTrainingTelemetryPage.css";

type LogicalRange = { lo: number; hi: number };

const LOGICAL_RANGE_BY_ACTUATOR: Record<string, LogicalRange> = {
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

/** 小数第 1 位。整数部（符号含む）の文字幅を揃えて小数点を縦に揃える */
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

function ScalarPanel({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="rl-telemetry__panel">
      <h2>{title}</h2>
      <table>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td className="rl-telemetry__td-num">{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VecTable({
  title,
  labels,
  values,
  valueHeader = "値",
  ranges,
  noPanel = false,
}: {
  title: string;
  labels: string[];
  values: number[];
  /** 数値列ヘッダ（例: 「値 (°)」） */
  valueHeader?: string;
  /** 各行の表示レンジ（バー表示用） */
  ranges?: Array<LogicalRange | null>;
  /** true のとき外側パネルを描画しない */
  noPanel?: boolean;
}) {
  const intWidth = useMemo(() => intPartWidth1dp(values), [values]);
  const showBars = Boolean(ranges?.length);

  const content = (
    <>
      <h2>{title}</h2>
      {values.length === 0 ? (
        <p className="rl-telemetry__empty">データ待ち</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>軸 / 関節</th>
              {showBars && <th className="rl-telemetry__th-pos">位置</th>}
              <th className="rl-telemetry__th-num">{valueHeader}</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((lab, i) => {
              const v = values[i];
              const r = ranges?.[i] ?? null;
              const hasRange =
                r !== null &&
                Number.isFinite(r.lo) &&
                Number.isFinite(r.hi) &&
                r.hi > r.lo &&
                Number.isFinite(v);
              const ratio = hasRange ? Math.max(0, Math.min(1, (v - r.lo) / (r.hi - r.lo))) : 0;
              return (
                <tr key={lab}>
                  <td>{lab}</td>
                  {showBars && (
                    <td className="rl-telemetry__td-pos">
                      {hasRange ? (
                        <div className="rl-telemetry__range-cell">
                          <div className="rl-telemetry__range-track">
                            <div
                              className="rl-telemetry__range-fill"
                              style={{ width: `${(ratio * 100).toFixed(1)}%` }}
                            />
                            <div className="rl-telemetry__range-midline" />
                          </div>
                          <span className="rl-telemetry__range-label">
                            {r.lo}..{r.hi}
                          </span>
                        </div>
                      ) : (
                        <span className="rl-telemetry__range-label">—</span>
                      )}
                    </td>
                  )}
                  <td className="rl-telemetry__td-num">
                    <span className="rl-telemetry__num-fixed">
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
  return <div className="rl-telemetry__panel">{content}</div>;
}

export default function RlTrainingTelemetryPage() {
  const stream = useRlTelemetryStream(true);
  const step = stream.lastStep;
  const reset = stream.lastReset;
  const names =
    step?.actuator_names?.length ? step.actuator_names : reset?.actuator_names ?? [];
  const accLabels = ["ax", "ay", "az"];
  const gyroLabels = ["gx", "gy", "gz"];
  const prevLogical =
    step?.obs_prev_action_logical_deg ??
    reset?.obs_prev_action_logical_deg ??
    step?.obs_prev_ctrl ??
    reset?.obs_prev_ctrl ??
    [];
  const actionLogical = step?.action_logical_deg ?? [];
  const prevCtrlLabels = names.length
    ? names.map((n) => `prev ${n}`)
    : prevLogical.map((_, i) => `prev_logical[${i}]`);
  const actionLabels = names.length ? names.map((n) => `action ${n}`) : [];
  const logicalRanges = names.map((n) => LOGICAL_RANGE_BY_ACTUATOR[n] ?? null);
  const prevRanges = logicalRanges.length === prevLogical.length ? logicalRanges : [];
  const actionRanges = logicalRanges.length === actionLogical.length ? logicalRanges : [];
  const rewardTotal = step?.reward_total ?? step?.reward;
  const rewardActionPenalty = step?.reward_action_penalty;
  const rewardFallPenalty = step?.reward_fall_penalty;
  const torsoHeight = step?.torso_height;

  return (
    <div className="rl-telemetry">
      <header className="rl-telemetry__header">
        <h1>RL 学習テレメトリ</h1>
        <p>
          <code>mujoco_rl_sim.scripts.train_002_full_actuators</code> 実行中に、方策への入力（IMU
          加速度・角速度・観測内の直前コマンド）と行動（各サーボ目標角）を表示します。関節角の表示は
          <strong>論理角（deg）</strong> です。観測末尾の prev は環境仕様どおり前ステップのコマンドです。
        </p>
      </header>

      <div className="rl-telemetry__status">
        <span
          className={
            "rl-telemetry__status-badge rl-telemetry__status-badge--" + stream.wsStatus
          }
        >
          {stream.wsStatus === "connected"
            ? "接続中"
            : stream.wsStatus === "connecting"
              ? "接続試行中"
              : "未接続"}
        </span>
        <span className="rl-telemetry__url">{stream.url}</span>
        <span className="rl-telemetry__logical-tag">関節角表示: 論理角 (deg)</span>
        {typeof step?.num_timesteps === "number" && (
          <span className="rl-telemetry__meta">SB3 num_timesteps: {step.num_timesteps}</span>
        )}
        <span className="rl-telemetry__meta">受信 step 数: {stream.stepCount}</span>
      </div>

      {stream.lastError && <div className="rl-telemetry__error">{stream.lastError}</div>}

      <div className="rl-telemetry__actions">
        <button type="button" className="rl-telemetry__btn" onClick={() => stream.reconnect()}>
          再接続
        </button>
      </div>

      {step && (
        <p className="rl-telemetry__meta" style={{ marginTop: "0.75rem" }}>
          episode_step={step.episode_step}
          {typeof step.num_timesteps === "number" && <> · num_timesteps={step.num_timesteps}</>}
        </p>
      )}

      <div className="rl-telemetry__grid" style={{ marginTop: "1rem" }}>
        <ScalarPanel
          title="報酬と判定（この step）"
          rows={[
            {
              label: "報酬 total",
              value: typeof rewardTotal === "number" ? rewardTotal.toFixed(5) : "—",
            },
            {
              label: "角度ペナルティ",
              value:
                typeof rewardActionPenalty === "number"
                  ? rewardActionPenalty.toFixed(5)
                  : "—",
            },
            {
              label: "転倒ペナルティ",
              value:
                typeof rewardFallPenalty === "number" ? rewardFallPenalty.toFixed(5) : "—",
            },
            {
              label: "torso height (m)",
              value: typeof torsoHeight === "number" ? torsoHeight.toFixed(4) : "—",
            },
            { label: "terminated", value: step?.terminated ? "true" : "false" },
            { label: "truncated", value: step?.truncated ? "true" : "false" },
          ]}
        />
        <div className="rl-telemetry__panel">
          <h2>入力: IMU（局所）</h2>
          <VecTable title="加速度 (m/s²)" labels={accLabels} values={step?.obs_acc ?? []} noPanel />
          <VecTable title="角速度 (rad/s)" labels={gyroLabels} values={step?.obs_gyro ?? []} noPanel />
        </div>
        <VecTable
          title="行動: 目標角 action（論理角 deg）"
          labels={
            actionLabels.length
              ? actionLabels
              : actionLogical.map((_, i) => `action[${i}]`)
          }
          values={actionLogical}
          valueHeader="値 (論理角 deg)"
          ranges={actionRanges}
        />
        <div className="rl-telemetry__grid-row2">
          <VecTable
            title="入力: 観測内 prev（論理角 deg, 1 step 遅れ）"
            labels={prevCtrlLabels}
            values={prevLogical}
            valueHeader="値 (論理角 deg)"
            ranges={prevRanges}
          />
        </div>
      </div>
    </div>
  );
}
