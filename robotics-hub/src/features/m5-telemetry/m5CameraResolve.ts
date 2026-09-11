/**
 * M5 本記録と robot-recorder の take を結び、再生用 URL を組み立てる。
 * 停止直後は mp4_url が meta に残らないことがあるので、take_id と時刻で補う。
 */
import {
  fetchExperiments,
  fetchExperimentTakes,
  type RecorderStatus,
  type RecorderTakeDescription,
} from "@/shared/recorderApi";
import type { M5RecordCamera, M5RecordMeta } from "./types";

export function absRecorderUrl(baseUrl: string, path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return baseUrl.replace(/\/$/, "") + (path.startsWith("/") ? path : `/${path}`);
}

/** take ディレクトリからの相対パス（Recorder の /data 配下） */
export function takeMediaPaths(experimentId: string, takeId: string): { mp4: string; hls: string } {
  const base = `/data/experiments/${experimentId}/takes/${takeId}`;
  return { mp4: `${base}/video.mp4`, hls: `${base}/index.m3u8` };
}

export function cameraFromRecorderStatus(st: RecorderStatus): M5RecordCamera {
  const exp = st.take_experiment_id || st.experiment_id || "";
  const take = st.take_id || "";
  const paths = exp && take ? takeMediaPaths(exp, take) : null;
  return {
    experiment_id: exp,
    take_id: take,
    video_t0_unix: st.video_t0_unix ?? null,
    mp4_url: st.mp4_url || paths?.mp4 || null,
    hls_url: st.hls_url || paths?.hls || null,
    ok: Boolean(take),
    error: "",
  };
}

export function fillCameraUrls(camera: M5RecordCamera): M5RecordCamera {
  const exp = camera.experiment_id || "";
  const take = camera.take_id || "";
  if (!exp || !take) return camera;
  const paths = takeMediaPaths(exp, take);
  return {
    ...camera,
    mp4_url: camera.mp4_url || paths.mp4,
    hls_url: camera.hls_url || paths.hls,
  };
}

export function resolveReplayVideoSrc(
  baseUrl: string,
  camera: M5RecordCamera | null | undefined
): string | null {
  if (!camera) return null;
  const filled = fillCameraUrls(camera);
  if (filled.ok === false && !filled.take_id && !filled.mp4_url) return null;
  return absRecorderUrl(baseUrl, filled.mp4_url) ?? absRecorderUrl(baseUrl, filled.hls_url);
}

function takeIdToUnix(takeId: string): number | null {
  const m = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/.exec(takeId);
  if (!m) return null;
  const ms = Date.parse(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}+09:00`);
  return Number.isFinite(ms) ? ms / 1000 : null;
}

function takeToCamera(take: RecorderTakeDescription): M5RecordCamera {
  const t0 =
    typeof take.meta.video_t0_unix === "number" ? take.meta.video_t0_unix : takeIdToUnix(take.take_id);
  const paths = takeMediaPaths(take.experiment_id, take.take_id);
  return {
    experiment_id: take.experiment_id,
    take_id: take.take_id,
    video_t0_unix: t0,
    mp4_url: take.video_url || (take.has_video ? paths.mp4 : null),
    hls_url: take.hls_url || (take.has_hls ? paths.hls : null),
    ok: Boolean(take.has_video || take.has_hls || take.video_url || take.hls_url),
    error: "",
  };
}

function recordingWindow(meta: Pick<M5RecordMeta, "started_unix" | "ended_unix" | "duration_sec">): {
  start: number;
  end: number;
} | null {
  const start = Number(meta.started_unix);
  if (!Number.isFinite(start) || start <= 0) return null;
  const ended = Number(meta.ended_unix);
  const dur = Number(meta.duration_sec);
  const end = Number.isFinite(ended) && ended > 0 ? ended : start + (Number.isFinite(dur) ? dur : 120);
  return { start: start - 3, end: end + 3 };
}

function takeOverlaps(take: RecorderTakeDescription, win: { start: number; end: number }): boolean {
  const t0 =
    typeof take.meta.video_t0_unix === "number" ? take.meta.video_t0_unix : takeIdToUnix(take.take_id);
  if (t0 == null) return false;
  return t0 >= win.start && t0 <= win.end;
}

/**
 * 本記録 meta の camera が空でも、Recorder の take 一覧から同時刻の映像を拾う。
 */
export async function lookupCameraForRecording(
  meta: Pick<M5RecordMeta, "started_unix" | "ended_unix" | "duration_sec" | "camera">
): Promise<M5RecordCamera | null> {
  const existing = meta.camera ? fillCameraUrls(meta.camera) : null;
  if (existing?.take_id && (existing.mp4_url || existing.hls_url) && existing.ok !== false) {
    return existing;
  }

  let experiments;
  try {
    experiments = await fetchExperiments();
  } catch {
    return existing;
  }

  const wantTake = existing?.take_id || "";
  const win = recordingWindow(meta);
  let matched: M5RecordCamera | null = existing?.take_id ? existing : null;

  for (const exp of experiments.experiments) {
    let takes: RecorderTakeDescription[];
    try {
      takes = await fetchExperimentTakes(exp.id);
    } catch {
      continue;
    }
    for (const take of takes) {
      if (!(take.has_video || take.has_hls || take.video_url || take.hls_url)) continue;
      const cam = takeToCamera(take);
      if (wantTake && take.take_id === wantTake) return cam;
      if (win && takeOverlaps(take, win)) matched = cam;
    }
  }
  return matched;
}
