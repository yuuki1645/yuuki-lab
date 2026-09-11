import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { cameraFromRecorderStatus, resolveReplayVideoSrc as resolveReplaySrc } from "./m5CameraResolve";
import { patchRecording } from "./m5RecordApi";
import type { M5RecordStatus } from "./types";

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
  /** 本記録停止後は status.id が消えるので、結び用に残す */
  const lastRecIdRef = useRef<string | null>(null);

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
    if (recordStatus?.id && recordStatus.recording) {
      lastRecIdRef.current = recordStatus.id;
    }
  }, [recordStatus?.id, recordStatus?.recording]);

  const attachCamera = useCallback(async (st: RecorderStatus, recId?: string | null) => {
    const id = recId || recordStatus?.id || lastRecIdRef.current;
    if (!id || !st.take_id) return;
    await patchRecording(id, { camera: cameraFromRecorderStatus(st) });
  }, [recordStatus?.id]);

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
      await attachCamera(st).catch(() => {
        /* 停止後の結びは再生時 lookup でも拾う */
      });
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
  }, [attachCamera]);

  // 開始失敗は take が無いときだけ書く。成功した take を空で上書きしない
  useEffect(() => {
    const id = recordStatus?.id;
    if (!id || !recordStatus.recording || !startError) return;
    if (status?.take_id) return;
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
  }, [recordStatus?.id, recordStatus?.recording, startError, status?.experiment_id, status?.take_id]);

  useEffect(() => {
    if (!recordStatus?.recording || !status?.take_id) return;
    void attachCamera(status, recordStatus.id).catch(() => {
      /* 次の tick */
    });
  }, [
    recordStatus?.recording,
    recordStatus?.id,
    status?.take_id,
    status?.mp4_url,
    status?.hls_url,
    status?.video_t0_unix,
    attachCamera,
  ]);

  const reviewSrc = useMemo(() => {
    if (!status?.take_id) return null;
    return resolveReplaySrc(baseUrl, cameraFromRecorderStatus(status));
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

export { resolveReplayVideoSrc } from "./m5CameraResolve";
