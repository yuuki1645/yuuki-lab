/**
 * robot-recorder（既定 :8766）の HTTP クライアント。
 * 実機カメラページ・ラボデータビュワーが共通で使う。
 */
import { getCaptureRealtimeBaseUrl } from "@/shared/constants";
import type { ImuDaemonSamplePayload } from "@/shared/types/imuDaemon";

function recorderBaseUrl(): string {
  return getCaptureRealtimeBaseUrl().replace(/\/$/, "");
}

/** Recorder が返すエラー JSON（ok: false）から表示用メッセージを取る。 */
async function readRecorderError(response: Response, fallback: string): Promise<string> {
  let detail = "";
  try {
    detail = await response.text();
  } catch {
    /* keep empty */
  }
  try {
    const j = JSON.parse(detail) as { message?: string; error?: string };
    if (typeof j.message === "string" && j.message.length > 0) return j.message;
    if (typeof j.error === "string" && j.error.length > 0) return j.error;
  } catch {
    /* keep text */
  }
  return detail || fallback;
}

async function recorderFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(recorderBaseUrl() + path, {
    cache: "no-store",
    ...init,
  });
  if (!response.ok) {
    throw new Error(await readRecorderError(response, `HTTP ${response.status}`));
  }
  return (await response.json()) as T;
}

export type RecorderDiskStatus = {
  free_bytes?: number;
  total_bytes?: number;
  ok_for_record?: boolean;
  warning?: string | null;
};

/** GET /api/status（録画開始・停止の応答も同じ形） */
export type RecorderStatus = {
  ok?: boolean;
  recording: boolean;
  experiment_id: string | null;
  take_id: string | null;
  take_experiment_id?: string | null;
  elapsed_sec?: number | null;
  hls_url?: string | null;
  mp4_url?: string | null;
  imu_url?: string | null;
  commands_url?: string | null;
  video_t0_unix?: number | null;
  frame_size?: number[] | null;
  fps?: number;
  burn_timestamp?: boolean;
  format_id?: string;
  data_root?: string;
  disk?: RecorderDiskStatus;
  imu_bridge?: RecorderImuBridgeSnapshot;
};

export type RecorderExperiment = {
  id: string;
  name: string;
  format_id?: string;
  created_at?: number;
  updated_at?: number;
  active?: boolean;
  take_count?: number;
};

export type RecorderExperimentsResponse = {
  ok?: boolean;
  experiments: RecorderExperiment[];
  active_experiment_id: string | null;
};

/** take の meta.json 相当。video_t0_unix で映像とセンサを突き合わせる。 */
export type RecorderTakeMeta = {
  video_t0_unix?: number;
  [key: string]: unknown;
};

/** GET /api/experiments/{id}/takes の 1 件（ビュワー用 URL 付き） */
export type RecorderTakeDescription = {
  take_id: string;
  experiment_id: string;
  format_id: string;
  meta: RecorderTakeMeta;
  has_video?: boolean;
  has_hls?: boolean;
  has_imu?: boolean;
  has_commands?: boolean;
  video_url?: string | null;
  hls_url?: string | null;
  imu_url?: string | null;
  commands_url?: string | null;
  meta_url?: string | null;
};

export type RecorderImuBridgeSnapshot = {
  status: string;
  url?: string;
  rate_hz?: number;
  last_error?: string | null;
};

export type RecorderImuLatestResponse = {
  sample: ImuDaemonSamplePayload | null;
  imu_bridge?: RecorderImuBridgeSnapshot;
};

export async function fetchRecorderStatus(): Promise<RecorderStatus> {
  return recorderFetch<RecorderStatus>("/api/status");
}

export async function startRecording(): Promise<RecorderStatus> {
  return recorderFetch<RecorderStatus>("/api/record/start", { method: "POST" });
}

export async function stopRecording(): Promise<RecorderStatus> {
  return recorderFetch<RecorderStatus>("/api/record/stop", { method: "POST" });
}

export async function fetchExperiments(): Promise<RecorderExperimentsResponse> {
  return recorderFetch<RecorderExperimentsResponse>("/api/experiments");
}

export async function createExperiment(name: string): Promise<RecorderExperiment> {
  const data = await recorderFetch<{ experiment: RecorderExperiment }>("/api/experiments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return data.experiment;
}

export async function selectExperiment(experimentId: string): Promise<void> {
  await recorderFetch(`/api/experiments/${encodeURIComponent(experimentId)}/select`, {
    method: "POST",
  });
}

export async function renameExperiment(
  experimentId: string,
  name: string
): Promise<RecorderExperiment> {
  const data = await recorderFetch<{ experiment: RecorderExperiment }>(
    `/api/experiments/${encodeURIComponent(experimentId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }
  );
  return data.experiment;
}

export async function deleteExperiment(experimentId: string): Promise<void> {
  await recorderFetch(`/api/experiments/${encodeURIComponent(experimentId)}`, {
    method: "DELETE",
  });
}

export async function fetchExperimentTakes(
  experimentId: string
): Promise<RecorderTakeDescription[]> {
  const data = await recorderFetch<{ takes?: RecorderTakeDescription[] }>(
    `/api/experiments/${encodeURIComponent(experimentId)}/takes`
  );
  return data.takes ?? [];
}

/** ライブ IMU（Pi → Recorder の最新サンプル）。未受信なら sample は null。 */
export async function fetchRecorderImuLatest(): Promise<RecorderImuLatestResponse> {
  const data = await recorderFetch<{
    sample?: ImuDaemonSamplePayload | null;
    imu_bridge?: RecorderImuBridgeSnapshot;
  }>("/api/imu/latest");
  return {
    sample: data.sample ?? null,
    imu_bridge: data.imu_bridge,
  };
}
