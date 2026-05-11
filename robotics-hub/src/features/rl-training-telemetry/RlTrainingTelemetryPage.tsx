import { useMemo } from "react";
import { useRlTelemetryStream } from "@/shared/hooks/useRlTelemetryStream";
import "./RlTrainingTelemetryPage.css";

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

function VecTable({
  title,
  labels,
  values,
  valueHeader = "値",
}: {
  title: string;
  labels: string[];
  values: number[];
  /** 数値列ヘッダ（例: 「値 (°)」） */
  valueHeader?: string;
}) {
  const intWidth = useMemo(() => intPartWidth1dp(values), [values]);

  return (
    <div className="rl-telemetry__panel">
      <h2>{title}</h2>
      {values.length === 0 ? (
        <p className="rl-telemetry__empty">データ待ち</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>軸 / 関節</th>
              <th className="rl-telemetry__th-num">{valueHeader}</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((lab, i) => (
              <tr key={lab}>
                <td>{lab}</td>
                <td className="rl-telemetry__td-num">
                  <span className="rl-telemetry__num-fixed">
                    {formatValue1dpAligned(values[i], intWidth)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
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
  const actionLogical = step?.action_logical_deg ?? step?.action ?? [];
  const prevCtrlLabels = names.length
    ? names.map((n) => `prev ${n}`)
    : prevLogical.map((_, i) => `prev_logical[${i}]`);
  const actionLabels = names.length ? names.map((n) => `action ${n}`) : [];

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
        <VecTable title="入力: 加速度 (局所 m/s²)" labels={accLabels} values={step?.obs_acc ?? []} />
        <VecTable title="入力: 角速度 (局所 rad/s)" labels={gyroLabels} values={step?.obs_gyro ?? []} />
        <VecTable
          title="入力: 観測内 prev（論理角 deg, 1 step 遅れ）"
          labels={prevCtrlLabels}
          values={prevLogical}
          valueHeader="値 (論理角 deg)"
        />
        <VecTable
          title="行動: 目標角 action（論理角 deg）"
          labels={
            actionLabels.length
              ? actionLabels
              : actionLogical.map((_, i) => `action[${i}]`)
          }
          values={actionLogical}
          valueHeader="値 (論理角 deg)"
        />
      </div>
    </div>
  );
}
