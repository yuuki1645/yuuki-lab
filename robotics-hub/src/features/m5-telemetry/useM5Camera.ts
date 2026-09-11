import { useCallback, useEffect, useMemo, useState } from "react";
import { getCaptureRealtimeBaseUrl, getCaptureRealtimeStreamUrl } from "@/shared/constants";
import {
  createExperiment,
  fetchExperiments,
  fetchRecorderStatus,
  selectExperiment,
  startRecording,
  stopRecording,
  type RecorderExperiment,
  type RecorderStatus,
} from "@/shared/recorderApi";
import { patchRecording } from "./m5RecordApi";
import type { M5RecordCamera, M5RecordStatus } from "./types";

function absMedia(base: string, path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return base.replace(/\/$/, "") + (path.startsWith("/") ? path : `/${path}`);
}

function cameraFromStatus(st: RecorderStatus): M5RecordCamera {
  return {
    experiment_id: st.experiment_id ?? "",
    take_id: st.take_id ?? "",
    video_t0_unix: st.video_t0_unix ?? null,
    mp4_url: st.mp4_url ?? null,
    hls_url: st.hls_url ?? null,
    ok: true,
    error: "",
  };
}

/**
 * 実機カメラ（robot-recorder :8766）を M5 画面に載せる。
 * 本記録の開始／停止に合わせて録画し、meta.camera に take を残す。
 */
export function useM5Camera(opts: { recordStatus: M5RecordStatus | null }) {
  const { recordStatus } = opts;
  const baseUrl = useMemo(() => getCaptureRealtimeBaseUrl().replace(/\/$/, ""), []);
  const [nonce, setNonce] = useState(() => Date.now());
  const [status, setStatus] = useState<RecorderStatus | null>(null);
  const [experiments, setExperiments] = useState<RecorderExperiment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const liveUrl = useMemo(
    () => getCaptureRealtimeStreamUrl() + "?t=" + String(nonce),
    [nonce]
  );

  const refresh = useCallback(async () => {
    try {
      const [st, ex] = await Promise.all([fetchRecorderStatus(), fetchExperiments()]);
      setStatus(st);
      setExperiments(ex.experiments);
      setError(null);
      // 録画が本当に始まったら開始失敗表示を消す（ポーリング成功では消さない）
      if (st.recording) setStartError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 1000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const reconnectLive = useCallback(() => {
    setNonce(Date.now());
  }, []);

  const selectExp = useCallback(
    async (id: string) => {
      if (status?.recording) return;
      setBusy(true);
      try {
        await selectExperiment(id);
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [status?.recording, refresh]
  );

  const ensureExperiment = useCallback(async () => {
    const data = await fetchExperiments();
    if (data.active_experiment_id) return data.active_experiment_id;
    const exp = await createExperiment("M5テレメトリ");
    await selectExperiment(exp.id);
    return exp.id;
  }, []);

  const startCapture = useCallback(async () => {
    setBusy(true);
    setStartError(null);
    try {
      await ensureExperiment();
      const deadline = Date.now() + 12_000;
      let lastMsg = "";
      while (Date.now() < deadline) {
        try {
          const st = await startRecording();
          setStatus(st);
          setStartError(null);
          return st;
        } catch (e) {
          lastMsg = e instanceof Error ? e.message : String(e);
          // 既に録画中なら成功扱い（二重開始）
          if (lastMsg.includes("既に録画") || lastMsg.includes("already_recording")) {
            const st = await fetchRecorderStatus();
            setStatus(st);
            setStartError(null);
            return st;
          }
          const retryable =
            lastMsg.includes("フレーム") ||
            lastMsg.includes("no_frame") ||
            lastMsg.includes("開けません") ||
            lastMsg.includes("実験");
          if (!retryable || Date.now() + 350 >= deadline) {
            throw e;
          }
          if (lastMsg.includes("実験")) {
            await ensureExperiment();
          }
          await new Promise((r) => window.setTimeout(r, 400));
        }
      }
      throw new Error(lastMsg || "映像の録画開始に失敗しました");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setStartError(msg);
      return null;
    } finally {
      setBusy(false);
    }
  }, [ensureExperiment]);

  const stopCapture = useCallback(async () => {
    setBusy(true);
    try {
      const st = await stopRecording();
      setStatus(st);
      return st;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      // 録画していない停止は本記録側の停止とずれていても正常
      if (msg.includes("録画していません") || msg.includes("not_recording")) {
        const st = await fetchRecorderStatus().catch(() => null);
        if (st) setStatus(st);
        return st;
      }
      setStartError(msg);
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  // 映像開始に失敗しても、ライブラリで理由が残るようにする
  useEffect(() => {
    const id = recordStatus?.id;
    if (!id || !recordStatus.recording || !startError) return;
    void patchRecording(id, {
      camera: {
        experiment_id: status?.experiment_id ?? "",
        take_id: "",
        video_t0_unix: null,
        mp4_url: null,
        hls_url: null,
        ok: false,
        error: startError,
      },
    }).catch(() => {
      /* ignore */
    });
  }, [recordStatus?.id, recordStatus?.recording, startError, status?.experiment_id]);

  // M5 本記録とカメラ take を meta に結び付ける
  useEffect(() => {
    const id = recordStatus?.id;
    if (!id || !recordStatus.recording || !status?.take_id) return;
    void patchRecording(id, { camera: cameraFromStatus(status) }).catch(() => {
      /* 次の tick で再試行 */
    });
  }, [recordStatus?.id, recordStatus?.recording, status?.take_id, status?.video_t0_unix]);

  useEffect(() => {
    const id = recordStatus?.id;
    if (!id || recordStatus.recording) return;
    if (!status?.mp4_url && !status?.hls_url) return;
    void patchRecording(id, { camera: cameraFromStatus(status) }).catch(() => {
      /* ignore */
    });
  }, [recordStatus?.id, recordStatus?.recording, status?.mp4_url, status?.hls_url]);

  const reviewSrc = useMemo(() => {
    if (!status?.take_id) return null;
    return absMedia(baseUrl, status.mp4_url) ?? absMedia(baseUrl, status.hls_url);
  }, [baseUrl, status]);

  return {
    baseUrl,
    liveUrl,
    status,
    experiments,
    error: startError || error,
    linkError: error,
    startError,
    busy,
    expanded,
    setExpanded,
    reconnectLive,
    selectExp,
    startCapture,
    stopCapture,
    refresh,
    reviewSrc,
  };
}

export function resolveReplayVideoSrc(
  baseUrl: string,
  camera: M5RecordCamera | null | undefined
): string | null {
  if (!camera) return null;
  return absMedia(baseUrl, camera.mp4_url) ?? absMedia(baseUrl, camera.hls_url);
}
