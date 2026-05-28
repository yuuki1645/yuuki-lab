import { useEffect, useMemo, useState } from "react";
import { trainingTelemetryFetchConfig, trainingTelemetrySetStepWallSleepSec } from "@/shared/api/telemetryApi";
import { useTrainingTelemetryStream } from "@/shared/hooks/useTrainingTelemetryStream";
import {
  isBipedPpoTelemetry,
  type TrainingTelemetryResetPayload,
  type TrainingTelemetryStepPayload,
} from "@/shared/types/trainingTelemetry";
import {
  ACC_LABELS,
  FOOT_LABELS,
  GYRO_LABELS,
  LOGICAL_RANGE_BY_ACTUATOR,
  RAD_TO_DEG,
  ScalarPanel,
  VecTable,
  ZAXIS_LABELS,
  wsStatusLabel,
} from "./telemetryUi";
import "./TelemetryPage.css";

function trainingGyroRadS(
  step: TrainingTelemetryStepPayload | null,
  reset: TrainingTelemetryResetPayload | null
): number[] {
  const raw =
    step?.obs_imu_gyro ??
    reset?.obs_imu_gyro ??
    step?.obs_gyro ??
    reset?.obs_gyro ??
    [];
  return raw.map((x) => (typeof x === "number" && Number.isFinite(x) ? x * RAD_TO_DEG : Number.NaN));
}

function trainingPrevAction(
  step: TrainingTelemetryStepPayload | null,
  reset: TrainingTelemetryResetPayload | null
): { values: number[]; unitLabel: string } {
  const biped = isBipedPpoTelemetry(step) || isBipedPpoTelemetry(reset);
  if (biped) {
    const v =
      step?.obs_prev_action_norm ??
      reset?.obs_prev_action_norm ??
      step?.obs_prev_ctrl ??
      reset?.obs_prev_ctrl ??
      [];
    return { values: v, unitLabel: "値 (正規化 [-1,1])" };
  }
  const v =
    step?.obs_prev_action_logical_deg ??
    reset?.obs_prev_action_logical_deg ??
    step?.obs_prev_ctrl ??
    reset?.obs_prev_ctrl ??
    [];
  return { values: v, unitLabel: "値 (論理角 deg)" };
}

export default function TrainingTelemetryPage() {
  const stream = useTrainingTelemetryStream(true);
  const step = stream.lastStep;
  const reset = stream.lastReset;
  const names =
    step?.actuator_names?.length ? step.actuator_names : reset?.actuator_names ?? [];
  const bipedStream = isBipedPpoTelemetry(step) || isBipedPpoTelemetry(reset);
  const prevAction = trainingPrevAction(step, reset);
  const prevLogical = prevAction.values;
  const actionLogical = step?.action_logical_deg ?? [];
  const prevCtrlLabels = names.length
    ? names.map((n) => `prev ${n}`)
    : prevLogical.map((_, i) => `prev[${i}]`);
  const actionLabels = names.length ? names.map((n) => `action ${n}`) : [];
  const logicalRanges = names.map((n) => LOGICAL_RANGE_BY_ACTUATOR[n] ?? null);
  const prevRanges =
    !bipedStream && logicalRanges.length === prevLogical.length ? logicalRanges : [];
  const actionRanges = logicalRanges.length === actionLogical.length ? logicalRanges : [];
  const rewardTotal = step?.reward_total ?? step?.reward;
  const rewardEffortPenalty =
    step?.reward_effort_penalty ?? step?.reward_action_penalty;
  const rewardFallPenalty = step?.reward_fall_penalty;
  const torsoHeight = step?.torso_height;
  const expLabel = step?.exp_name ?? reset?.exp_name;
  const [stepWallSleepSec, setStepWallSleepSec] = useState(0);
  const [settingSleep, setSettingSleep] = useState(false);
  const [sleepError, setSleepError] = useState<string | null>(null);

  const trainingGyroDisplayDegS = useMemo(
    () => trainingGyroRadS(step, reset),
    [step, reset]
  );

  const footObsValues = useMemo(() => {
    if (!bipedStream || !step) return [];
    return [
      step.obs_left_foot_contact ?? Number.NaN,
      step.obs_right_foot_contact ?? Number.NaN,
      step.obs_left_foot_dx ?? Number.NaN,
      step.obs_right_foot_dx ?? Number.NaN,
    ];
  }, [bipedStream, step]);

  const zaxisValues = useMemo(() => {
    if (!bipedStream) return [];
    return step?.obs_imu_zaxis ?? reset?.obs_imu_zaxis ?? [];
  }, [bipedStream, step, reset]);

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
        <h1>学習テレメトリ</h1>
        <p>
          強化学習時は{" "}
          <code>mujoco_rl_sim.experiments.exp_019_biped_ppo_hop_balance.train</code> の Socket.IO（
          <code>rl_telemetry/*</code>・スキーマ <code>biped_ppo_v1</code>）で観測・行動を表示します。
          関節は<strong>論理角（deg）</strong>です。
        </p>
      </header>

      <div className="telemetry__status">
        <span
          className={"telemetry__status-badge telemetry__status-badge--" + stream.wsStatus}
        >
          {wsStatusLabel(stream.wsStatus)}
        </span>
        <span className="telemetry__url">{stream.url}</span>
        <span className="telemetry__logical-tag">
          {bipedStream ? "exp_019 · 行動=論理角 (deg)" : "関節角: 論理角 (deg)"}
        </span>
        {expLabel ? <span className="telemetry__meta">{expLabel}</span> : null}
        {typeof step?.num_timesteps === "number" && (
          <span className="telemetry__meta">env_steps: {step.num_timesteps}</span>
        )}
        <span className="telemetry__meta">受信 step 数: {stream.stepCount}</span>
      </div>
      {stream.lastError && <div className="telemetry__error">{stream.lastError}</div>}

      <div className="telemetry__actions">
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
          <ScalarPanel
            title="報酬と判定（学習 step）"
            rows={[
              {
                label: "報酬 total",
                value: typeof rewardTotal === "number" ? rewardTotal.toFixed(5) : "—",
              },
              {
                label: bipedStream ? "effort ペナルティ" : "角度ペナルティ",
                value:
                  typeof rewardEffortPenalty === "number"
                    ? rewardEffortPenalty.toFixed(5)
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
            <h2>学習: 入力 IMU / 足（シミュ値）</h2>
            {bipedStream ? (
              <>
                <VecTable
                  title="IMU z 軸（単位ベクトル）"
                  labels={ZAXIS_LABELS}
                  values={zaxisValues}
                  noPanel
                />
                <VecTable
                  title="角速度 (deg/s)"
                  labels={GYRO_LABELS}
                  values={trainingGyroDisplayDegS}
                  noPanel
                />
                <p className="telemetry__meta">
                  角速度は MuJoCo imu_gyro（rad/s）を deg/s に換算。IMU 高さ norm:{" "}
                  {typeof step?.obs_imu_z_norm === "number"
                    ? step.obs_imu_z_norm.toFixed(4)
                    : "—"}
                </p>
                {footObsValues.length > 0 && (
                  <VecTable
                    title="足接地・足元 dx（正規化）"
                    labels={FOOT_LABELS}
                    values={footObsValues}
                    noPanel
                  />
                )}
              </>
            ) : (
              <>
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
              </>
            )}
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
              title={
                bipedStream
                  ? "学習: 観測内 prev action（正規化, 1 step 遅れ）"
                  : "学習: 観測内 prev（論理角 deg, 1 step 遅れ）"
              }
              labels={prevCtrlLabels}
              values={prevLogical}
              valueHeader={prevAction.unitLabel}
              ranges={prevRanges}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
