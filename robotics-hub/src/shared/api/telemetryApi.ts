import { getTrainingTelemetrySocketUrl } from "@/shared/constants";

export interface TrainingTelemetryConfigResponse {
  step_wall_sleep_sec: number | null;
}

export interface TrainingTelemetryConfigSetResponse {
  status: "ok";
  step_wall_sleep_sec: number;
}

async function readError(response: Response, fallback: string): Promise<string> {
  let detail = "";
  try {
    detail = await response.text();
  } catch {
    /* keep empty */
  }
  try {
    const j = JSON.parse(detail) as { error?: string };
    if (j.error) return j.error;
  } catch {
    /* keep text */
  }
  return detail || fallback;
}

export async function trainingTelemetryFetchConfig(): Promise<TrainingTelemetryConfigResponse> {
  const base = getTrainingTelemetrySocketUrl();
  const response = await fetch(`${base}/api/rl_telemetry/config`);
  if (!response.ok) {
    throw new Error(`Training telemetry config: HTTP ${response.status}`);
  }
  return (await response.json()) as TrainingTelemetryConfigResponse;
}

export async function trainingTelemetrySetStepWallSleepSec(
  stepWallSleepSec: number
): Promise<TrainingTelemetryConfigSetResponse> {
  const base = getTrainingTelemetrySocketUrl();
  const response = await fetch(`${base}/api/rl_telemetry/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step_wall_sleep_sec: stepWallSleepSec }),
  });
  if (!response.ok) {
    const detail = await readError(response, `Training telemetry config: HTTP ${response.status}`);
    throw new Error(detail);
  }
  return (await response.json()) as TrainingTelemetryConfigSetResponse;
}
