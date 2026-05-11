import { useRlTelemetryStream } from "@/shared/hooks/useRlTelemetryStream";
import "./RlTrainingTelemetryPage.css";

function fmt(v: number | null | undefined, digits = 4): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return v.toFixed(digits);
}

function VecTable({
  title,
  labels,
  values,
}: {
  title: string;
  labels: string[];
  values: number[];
}) {
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
              <th>値</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((lab, i) => (
              <tr key={lab}>
                <td>{lab}</td>
                <td>{fmt(values[i], 5)}</td>
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
  const names =
    step?.actuator_names?.length ? step.actuator_names : stream.lastReset?.actuator_names ?? [];
  const accLabels = ["ax", "ay", "az"];
  const gyroLabels = ["gx", "gy", "gz"];
  const prevCtrlLabels = names.length
    ? names.map((n) => `prev ${n}`)
    : step?.obs_prev_ctrl?.map((_, i) => `prev_ctrl[${i}]`) ?? [];
  const actionLabels = names.length ? names.map((n) => `action ${n}`) : [];

  return (
    <div className="rl-telemetry">
      <header className="rl-telemetry__header">
        <h1>RL 学習テレメトリ</h1>
        <p>
          <code>mujoco_rl_sim.scripts.train_002_full_actuators</code> 実行中に、方策への入力（IMU
          加速度・角速度・観測内の直前コマンド）と行動（各サーボ目標角 [rad]）を表示します。観測末尾の
          prev_ctrl は環境仕様どおり前ステップのコマンドです。
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
          title="入力: 観測内 prev_ctrl (rad, 1 step 遅れ)"
          labels={prevCtrlLabels}
          values={step?.obs_prev_ctrl ?? []}
        />
        <VecTable
          title="行動: 目標角 action (rad)"
          labels={
            actionLabels.length
              ? actionLabels
              : (step?.action ?? []).map((_, i) => `action[${i}]`)
          }
          values={step?.action ?? []}
        />
      </div>
    </div>
  );
}
