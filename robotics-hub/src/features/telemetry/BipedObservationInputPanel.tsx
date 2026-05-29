import { useMemo } from "react";
import type {
  TrainingTelemetryResetPayload,
  TrainingTelemetryStepPayload,
} from "@/shared/types/trainingTelemetry";
import {
  BIPED_PPO_V1_OBS_DIM,
  BIPED_PPO_V1_OBS_UI_SLICES,
  type BipedObsUiSlice,
} from "./bipedPpoContractUi";
import { RAD_TO_DEG, VecTable } from "./telemetryUi";

type ObsSource = TrainingTelemetryStepPayload | TrainingTelemetryResetPayload;

function scalarValue(source: ObsSource | null, field: BipedObsUiSlice & { kind: "scalar" }): number[] {
  if (!source) return [];
  const v = source[field.field];
  return typeof v === "number" && Number.isFinite(v) ? [v] : [Number.NaN];
}

function vectorValues(
  source: ObsSource | null,
  slice: BipedObsUiSlice & { kind: "vector" }
): number[] {
  if (!source) return [];
  const raw = source[slice.field];
  if (!Array.isArray(raw)) return [];
  const mapped = raw.map((x) =>
    typeof x === "number" && Number.isFinite(x) ? x : Number.NaN
  );
  if (slice.gyroRadToDeg) {
    return mapped.map((x) => (Number.isFinite(x) ? x * RAD_TO_DEG : Number.NaN));
  }
  return mapped;
}

function rowLabels(
  slice: BipedObsUiSlice,
  actuatorNames: string[]
): string[] {
  if (slice.kind === "scalar") return [slice.label];
  if (slice.useActuatorLabels && actuatorNames.length > 0) {
    return actuatorNames;
  }
  if (slice.labels.length > 0) return slice.labels;
  const n = vectorValues(null, slice).length;
  return Array.from({ length: Math.max(n, 10) }, (_, i) => `[${i}]`);
}

export function BipedObservationInputPanel({
  step,
  reset,
  actuatorNames,
}: {
  step: TrainingTelemetryStepPayload | null;
  reset: TrainingTelemetryResetPayload | null;
  actuatorNames: string[];
}) {
  const source: ObsSource | null = step ?? reset;
  const flatLen = source?.obs_flat?.length ?? 0;
  const obsDim = reset?.obs_dim ?? (flatLen || BIPED_PPO_V1_OBS_DIM);

  const sections = useMemo(
    () =>
      BIPED_PPO_V1_OBS_UI_SLICES.map((slice) => {
        const labels = rowLabels(slice, actuatorNames);
        const values =
          slice.kind === "scalar"
            ? scalarValue(source, slice)
            : vectorValues(source, slice);
        return { slice, labels, values };
      }),
    [source, actuatorNames]
  );

  return (
    <div className="telemetry__panel telemetry__panel--obs-inputs">
      <h2>学習: 入力（契約 biped_ppo_v1）</h2>
      <p className="telemetry__meta">
        契約観測 {BIPED_PPO_V1_OBS_DIM} 次元（スライス {BIPED_PPO_V1_OBS_UI_SLICES.length}{" "}
        件）。obs_dim={obsDim}
        {flatLen > 0 ? ` · obs_flat=${flatLen}` : ""}
      </p>
      <div className="telemetry__obs-sections">
        {sections.map(({ slice, labels, values }) => (
          <section key={slice.id} className="telemetry__obs-section">
            <h3 className="telemetry__obs-section-title">{slice.title}</h3>
            <p className="telemetry__meta telemetry__obs-section-desc">{slice.description}</p>
            <VecTable
              title=""
              labels={labels}
              values={values}
              valueHeader={slice.valueHeader ?? "値"}
              noPanel
              showTitle={false}
            />
          </section>
        ))}
      </div>
    </div>
  );
}
