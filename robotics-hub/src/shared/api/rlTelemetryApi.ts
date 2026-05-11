import { getRlTelemetrySocketUrl } from "@/shared/constants";

export interface RlTelemetryConfigResponse {
  step_wall_sleep_sec: number | null;
}

export interface RlTelemetryConfigSetResponse {
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

export async function rlTelemetryFetchConfig(): Promise<RlTelemetryConfigResponse> {
  const base = getRlTelemetrySocketUrl();
  const response = await fetch(`${base}/api/rl_telemetry/config`);
  if (!response.ok) {
    throw new Error(`RL telemetry config: HTTP ${response.status}`);
  }
  return (await response.json()) as RlTelemetryConfigResponse;
}

export async function rlTelemetrySetStepWallSleepSec(
  stepWallSleepSec: number
): Promise<RlTelemetryConfigSetResponse> {
  const base = getRlTelemetrySocketUrl();
  const response = await fetch(`${base}/api/rl_telemetry/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step_wall_sleep_sec: stepWallSleepSec }),
  });
  if (!response.ok) {
    const detail = await readError(response, `RL telemetry config: HTTP ${response.status}`);
    throw new Error(detail);
  }
  return (await response.json()) as RlTelemetryConfigSetResponse;
}
