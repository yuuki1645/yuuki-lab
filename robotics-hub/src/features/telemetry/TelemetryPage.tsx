import { memo, useEffect, useMemo, useState } from "react";
import { trainingTelemetryFetchConfig, trainingTelemetrySetStepWallSleepSec } from "@/shared/api/telemetryApi";
import { useDaemonImuTelemetry } from "@/shared/contexts/DaemonImuTelemetryContext";
import { useTrainingTelemetryStream } from "@/shared/hooks/useTrainingTelemetryStream";
import type { ImuDaemonSamplePayload } from "@/shared/types/imuDaemon";
import "./TelemetryPage.css";

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

function VecTable({
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
  /** 数値列ヘッダ（例: 「値 (°)」） */
  valueHeader?: string;
  /** 各行の表示レンジ（バー表示用） */
  ranges?: Array<LogicalRange | null>;
  /** true のとき外側パネルを描画しない */
  noPanel?: boolean;
  /** false のとき内側の h2（title）を出さない */
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

function daemonSampleToAccelGyroAngle(s: ImuDaemonSamplePayload | null): {
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

const ACC_LABELS = ["ax", "ay", "az"];
const GYRO_LABELS = ["gx", "gy", "gz"];
const ANGLE_LABELS = ["pitch", "roll", "yaw"];

const RAD_TO_DEG = 180 / Math.PI;

function radPerSecToDegPerSec(values: number[] | undefined): number[] {
  const v = values ?? [];
  return v.map((x) => (typeof x === "number" && Number.isFinite(x) ? x * RAD_TO_DEG : Number.NaN));
}

/** ``imu/sample`` の ``timestamp``（ラズパイ ``perf_counter``）だけ描画し、親の再描画コストを抑える */
const ImuPerfTimestampReadout = memo(function ImuPerfTimestampReadout({
  perfS,
}: {
  perfS: number | undefined;
}) {
  if (typeof perfS !== "number" || !Number.isFinite(perfS)) {
    return <span className="telemetry__perf-value">—</span>;
  }
  return <span className="telemetry__perf-value">{perfS.toFixed(9)}</span>;
});

export default function TelemetryPage() {
  const stream = useTrainingTelemetryStream(true);
  const imuStream = useDaemonImuTelemetry();
  const csvRecording = imuStream.lastStatus?.csv_recording === true;
  const csvEnabledOnServer = imuStream.lastStatus?.csv_enabled !== false;
  const imuStreaming = Boolean(imuStream.lastStatus?.streaming);
  const step = stream.lastStep;
  const reset = stream.lastReset;
  const names =
    step?.actuator_names?.length ? step.actuator_names : reset?.actuator_names ?? [];
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
  const [stepWallSleepSec, setStepWallSleepSec] = useState(0);
  const [settingSleep, setSettingSleep] = useState(false);
  const [sleepError, setSleepError] = useState<string | null>(null);

  const { acc: daemonAcc, gyro: daemonGyro, angle: daemonAngle } = useMemo(
    () => daemonSampleToAccelGyroAngle(imuStream.lastSample),
    [imuStream.lastSample]
  );

  const trainingGyroDisplayDegS = useMemo(
    () => radPerSecToDegPerSec(step?.obs_gyro),
    [step?.obs_gyro]
  );

  useEffect(() => {
    let cancelled = false;
    trainingTelemetryFetchConfig()
      .then((cfg) => {
        if (cancelled) return;
        const v = typeof cfg.step_wall_sleep_sec === "number" ? cfg.step_wall_sleep_sec : 0;
        setStepWallSleepSec(v);
      })
      .catch(() => {
        // テレメトリ未起動時などは無視して、step payload 側の値で追従する。
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof step?.step_wall_sleep_sec !== "number") return;
    setStepWallSleepSec(step.step_wall_sleep_sec);
  }, [step?.step_wall_sleep_sec]);

  useEffect(() => {
    if (imuStream.wsStatus === "connected") {
      imuStream.requestImuStatus();
    }
  }, [imuStream.wsStatus, imuStream.requestImuStatus]);

  const applyStepWallSleep = async () => {
    setSettingSleep(true);
    setSleepError(null);
    try {
      await trainingTelemetrySetStepWallSleepSec(stepWallSleepSec);
    } catch (e) {
      setSleepError(e instanceof Error ? e.message : "step_wall_sleep の更新に失敗しました");
    } finally {
      setSettingSleep(false);
    }
  };

  return (
    <div className="telemetry">
      <header className="telemetry__header">
        <h1>テレメトリ</h1>
        <p>
          学習時は <code>mujoco_rl_sim.scripts.train_002_full_actuators</code> の Socket.IO（
          <code>rl_telemetry/*</code>）で観測・行動を表示します。実機は{" "}
          <code>robot-daemon</code> の IMU（<code>imu/start</code> 後の <code>imu/sample</code>
          ）を同一ページに表示します。ラズパイへの CSV ログは <code>imu/log_start</code> /{" "}
          <code>imu/log_stop</code> で開始・停止します（ハブ内の別画面に移っても接続は維持されます）。学習ストリームの関節は
          <strong>論理角（deg）</strong>です。
        </p>
      </header>

      <h2 className="telemetry__section-title">学習ストリーム（mujoco_rl_sim）</h2>
      <div className="telemetry__status">
        <span
          className={"telemetry__status-badge telemetry__status-badge--" + stream.wsStatus}
        >
          {stream.wsStatus === "connected"
            ? "接続中"
            : stream.wsStatus === "connecting"
              ? "接続試行中"
              : "未接続"}
        </span>
        <span className="telemetry__url">{stream.url}</span>
        <span className="telemetry__logical-tag">関節角: 論理角 (deg)</span>
        {typeof step?.num_timesteps === "number" && (
          <span className="telemetry__meta">SB3 num_timesteps: {step.num_timesteps}</span>
        )}
        <span className="telemetry__meta">受信 step 数: {stream.stepCount}</span>
      </div>
      {stream.lastError && <div className="telemetry__error">{stream.lastError}</div>}

      <h2 className="telemetry__section-title">実機 IMU（robot-daemon）</h2>
      <div className="telemetry__status">
        <span className={"telemetry__status-badge telemetry__status-badge--" + imuStream.wsStatus}>
          {imuStream.wsStatus === "connected"
            ? "接続中"
            : imuStream.wsStatus === "connecting"
              ? "接続試行中"
              : "未接続"}
        </span>
        <span className="telemetry__url">{imuStream.url}</span>
        <span className="telemetry__meta">
          streaming: {String(Boolean(imuStream.lastStatus?.streaming))}
        </span>
        <span className="telemetry__meta">受信サンプル数: {imuStream.sampleCount}</span>
        <span className="telemetry__meta">
          CSV ログ: {csvRecording ? "記録中" : "停止"}
          {imuStream.lastStatus?.csv_enabled === false ? "（サーバ無効）" : ""}
        </span>
        {imuStream.lastSample?.mock ? (
          <span className="telemetry__logical-tag">モック IMU</span>
        ) : null}
      </div>
      <div className="telemetry__perf-readout" aria-live="polite">
        <span className="telemetry__perf-label">
          perf_timestamp（ラズパイ <code>perf_counter</code>、秒）
        </span>
        <ImuPerfTimestampReadout perfS={imuStream.lastSample?.timestamp} />
      </div>
      {imuStream.lastError && <div className="telemetry__error">{imuStream.lastError}</div>}
      {imuStream.lastImuError && (
        <div className="telemetry__error">IMU: {imuStream.lastImuError}</div>
      )}
      {imuStream.lastLogStatus?.ok === false && (
        <div className="telemetry__error">
          CSV ログ:{" "}
          {imuStream.lastLogStatus.reason === "csv_disabled"
            ? "サーバで CSV が無効です（IMU_LOG_DISABLE 等）"
            : imuStream.lastLogStatus.reason === "imu_not_streaming"
              ? "先に IMU ストリームを開始してください"
              : imuStream.lastLogStatus.reason ?? "開始に失敗しました"}
        </div>
      )}
      <div className="telemetry__actions">
        <button type="button" className="telemetry__btn" onClick={() => imuStream.reconnect()}>
          IMU 再接続（imu/start を再送）
        </button>
        <button
          type="button"
          className="telemetry__btn"
          onClick={() => imuStream.startCsvLog()}
          disabled={
            imuStream.wsStatus !== "connected" ||
            !imuStreaming ||
            !csvEnabledOnServer ||
            csvRecording
          }
        >
          CSV ログ開始
        </button>
        <button
          type="button"
          className="telemetry__btn"
          onClick={() => imuStream.stopCsvLog()}
          disabled={imuStream.wsStatus !== "connected" || !csvRecording}
        >
          CSV ログ停止
        </button>
      </div>

      <div className="telemetry__actions" style={{ marginTop: "0.75rem" }}>
        <button type="button" className="telemetry__btn" onClick={() => stream.reconnect()}>
          学習ストリーム再接続
        </button>
        <div className="telemetry__sleep-control">
          <label htmlFor="step-wall-sleep" className="telemetry__sleep-label">
            step-wall-sleep: {stepWallSleepSec.toFixed(3)} s
          </label>
          <input
            id="step-wall-sleep"
            type="range"
            min={0}
            max={0.2}
            step={0.005}
            value={stepWallSleepSec}
            onChange={(e) => setStepWallSleepSec(Number(e.target.value))}
          />
          <button
            type="button"
            className="telemetry__btn"
            onClick={applyStepWallSleep}
            disabled={settingSleep}
          >
            {settingSleep ? "適用中..." : "速度を適用"}
          </button>
        </div>
      </div>
      {sleepError && <div className="telemetry__error">{sleepError}</div>}

      {step && (
        <p className="telemetry__meta" style={{ marginTop: "0.75rem" }}>
          episode_step={step.episode_step}
          {typeof step.num_timesteps === "number" && <> · num_timesteps={step.num_timesteps}</>}
        </p>
      )}

      <div className="telemetry__data-zones">
        <div className="telemetry__grid">
          <div className="telemetry__panel">
            <h2>実機 IMU（局所・robot-daemon）</h2>
            <p className="telemetry__meta">
              MPU6050 の生スケールを 16384 で割った値（g）。学習ストリームの加速度も g（MuJoCo は{" "}
              <code>|opt.gravity|</code> で正規化）で揃えています。
            </p>
            <VecTable
              title="加速度（スケール g 相当）"
              labels={ACC_LABELS}
              values={daemonAcc}
              valueHeader="値"
              noPanel
            />
            <VecTable
              title="角速度 (deg/s)"
              labels={GYRO_LABELS}
              values={daemonGyro}
              valueHeader="値"
              noPanel
            />
          </div>
          <div className="telemetry__panel">
            <h2>実機 IMU（推定角 deg）</h2>
            <VecTable
              title=""
              labels={ANGLE_LABELS}
              values={daemonAngle}
              valueHeader="値"
              noPanel
              showTitle={false}
            />
          </div>
        </div>

        <hr className="telemetry__divider" aria-hidden />

        <div className="telemetry__grid">
          <ScalarPanel
            title="報酬と判定（学習 step）"
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
          <div className="telemetry__panel">
            <h2>学習: 入力 IMU（局所・シミュ値）</h2>
            <VecTable
              title={`加速度 (${step?.obs_acc_unit === "m/s2" ? "m/s²" : "g"})`}
              labels={ACC_LABELS}
              values={step?.obs_acc ?? []}
              noPanel
            />
            <p className="telemetry__meta">
              角速度は受信ペイロードが rad/s のため、下表のみ deg/s（×180/π）に換算して表示しています。
            </p>
            <VecTable
              title="角速度 (deg/s)"
              labels={GYRO_LABELS}
              values={trainingGyroDisplayDegS}
              noPanel
            />
          </div>
          <VecTable
            title="学習: 行動 目標角（論理角 deg）"
            labels={
              actionLabels.length
                ? actionLabels
                : actionLogical.map((_, i) => `action[${i}]`)
            }
            values={actionLogical}
            valueHeader="値 (論理角 deg)"
            ranges={actionRanges}
          />
          <div className="telemetry__grid-row2">
            <VecTable
              title="学習: 観測内 prev（論理角 deg, 1 step 遅れ）"
              labels={prevCtrlLabels}
              values={prevLogical}
              valueHeader="値 (論理角 deg)"
              ranges={prevRanges}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
