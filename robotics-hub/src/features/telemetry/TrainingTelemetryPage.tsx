import { useEffect, useMemo, useState } from "react";
import { trainingTelemetryFetchConfig, trainingTelemetrySetStepWallSleepSec } from "@/shared/api/telemetryApi";
import { useTrainingTelemetryStream } from "@/shared/hooks/useTrainingTelemetryStream";
import {
  isBipedPpoTelemetry,
  type TrainingTelemetryResetPayload,
  type TrainingTelemetryStepPayload,
} from "@/shared/types/trainingTelemetry";
import { BipedObservationInputPanel } from "./BipedObservationInputPanel";
import {
  ACC_LABELS,
  GYRO_LABELS,
  LOGICAL_RANGE_BY_ACTUATOR,
  RAD_TO_DEG,
  ScalarPanel,
  VecTable,
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

export default function TrainingTelemetryPage() {
  const stream = useTrainingTelemetryStream(true);
  const step = stream.lastStep;
  const reset = stream.lastReset;
  const names =
    step?.actuator_names?.length ? step.actuator_names : reset?.actuator_names ?? [];
  const bipedStream = isBipedPpoTelemetry(step) || isBipedPpoTelemetry(reset);
  const actionLogical = step?.action_logical_deg ?? [];
  const actionLabels = names.length ? names.map((n) => `action ${n}`) : [];
  const logicalRanges = names.map((n) => LOGICAL_RANGE_BY_ACTUATOR[n] ?? null);
  const actionRanges = logicalRanges.length === actionLogical.length ? logicalRanges : [];
  const rewardTotal = step?.reward_total ?? step?.reward;
  const rewardEffortPenalty =
    step?.reward_effort_penalty ?? step?.reward_action_penalty;
  const rewardFallPenalty = step?.reward_fall_penalty;
  const torsoHeight = step?.torso_height;
  const expLabel = step?.exp_name ?? reset?.exp_name;
  const schemaLabel = step?.schema ?? reset?.schema;
  const [stepWallSleepSec, setStepWallSleepSec] = useState(0);
  const [settingSleep, setSettingSleep] = useState(false);
  const [sleepError, setSleepError] = useState<string | null>(null);

  const trainingGyroDisplayDegS = useMemo(
    () => trainingGyroRadS(step, reset),
    [step, reset]
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
          強化学習時は MuJoCo 実験の Socket.IO（<code>rl_telemetry/*</code>・スキーマ{" "}
          <code>biped_ppo_v1</code>）で観測・行動を表示します。中央列は契約どおりの全入力次元、右列は行動（論理角
          deg）です。
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
          {bipedStream ? "biped_ppo_v1 · 行動=論理角 (deg)" : "関節角: 論理角 (deg)"}
        </span>
        {schemaLabel ? <span className="telemetry__meta">schema: {schemaLabel}</span> : null}
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
        <div className="telemetry__grid telemetry__grid--training">
          <div className="telemetry__col telemetry__col--meta">
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
                {
                  label: "is_fallen",
                  value: step?.is_fallen === true ? "true" : step?.is_fallen === false ? "false" : "—",
                },
                {
                  label: "step_wall_sleep (s)",
                  value:
                    typeof step?.step_wall_sleep_sec === "number"
                      ? step.step_wall_sleep_sec.toFixed(4)
                      : "—",
                },
              ]}
            />
          </div>

          <div className="telemetry__col telemetry__col--inputs">
            {bipedStream ? (
              <BipedObservationInputPanel
                step={step}
                reset={reset}
                actuatorNames={names}
              />
            ) : (
              <div className="telemetry__panel telemetry__panel--obs-inputs">
                <h2>学習: 入力（旧 6 次元 IMU）</h2>
                <VecTable
                  title={`加速度 (${step?.obs_acc_unit === "m/s2" ? "m/s²" : "g"})`}
                  labels={ACC_LABELS}
                  values={step?.obs_acc ?? reset?.obs_acc ?? []}
                  noPanel
                />
                <p className="telemetry__meta">
                  角速度は受信ペイロードが rad/s のため deg/s に換算して表示しています。
                </p>
                <VecTable
                  title="角速度 (deg/s)"
                  labels={GYRO_LABELS}
                  values={trainingGyroDisplayDegS}
                  noPanel
                />
              </div>
            )}
          </div>

          <div className="telemetry__col telemetry__col--action">
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
          </div>
        </div>
      </div>
    </div>
  );
}
