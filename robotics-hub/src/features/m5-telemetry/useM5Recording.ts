import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { lookupCameraForRecording } from "./m5CameraResolve";
import {
  deleteRecording,
  fetchAllRecordingFrames,
  fetchRecording,
  fetchRecordings,
  patchRecording,
} from "./m5RecordApi";
import type { M5Cmd, M5Control, M5Frame, M5HistoryPoint, M5Profile, M5RecordMeta, M5RecordStatus, M5Scan } from "./types";
import { controlFromFrame, frameToHistory } from "./types";

export type M5ViewMode = "live" | "replay";

const HISTORY_MAX = 160;
const RATES = [0.25, 0.5, 1, 2] as const;
const STEPS = [1, 5, 10] as const;

function clampIndex(i: number, n: number): number {
  if (n <= 0) return 0;
  return Math.max(0, Math.min(n - 1, i));
}

function elapsedOf(frames: M5Frame[], i: number): number {
  const t0 = frames[0]?.t;
  const t = frames[i]?.t;
  if (typeof t0 === "number" && typeof t === "number" && Number.isFinite(t0) && Number.isFinite(t)) {
    return Math.max(0, t - t0);
  }
  return i * 0.05;
}

export function useM5Recording(opts: {
  recordStatus: M5RecordStatus | null;
  send: (cmd: M5Cmd) => void;
  /** 本記録と同時に robot-recorder を切る */
  startCamera?: () => Promise<unknown>;
  stopCamera?: () => Promise<unknown>;
}) {
  const { recordStatus, send, startCamera, stopCamera } = opts;
  const [library, setLibrary] = useState<M5RecordMeta[]>([]);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [mode, setMode] = useState<M5ViewMode>("live");
  const [meta, setMeta] = useState<M5RecordMeta | null>(null);
  const [frames, setFrames] = useState<M5Frame[]>([]);
  const [replayProfile, setReplayProfile] = useState<M5Profile | null>(null);
  const [replayScan, setReplayScan] = useState<M5Scan | null>(null);
  const [replayControlBase, setReplayControlBase] = useState<M5Control | null>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState<(typeof RATES)[number]>(1);
  const [loadProgress, setLoadProgress] = useState<{ loaded: number; total: number } | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const playRef = useRef(playing);
  playRef.current = playing;

  const refreshLibrary = useCallback(async () => {
    setLibraryLoading(true);
    try {
      const rows = await fetchRecordings();
      setLibrary(rows);
      setLibraryError(null);
    } catch (e) {
      setLibraryError(e instanceof Error ? e.message : String(e));
    } finally {
      setLibraryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (libraryOpen) void refreshLibrary();
  }, [libraryOpen, refreshLibrary, recordStatus?.recording, recordStatus?.sample_count]);

  const startRecord = useCallback(
    (name: string, notes: string) => {
      // 数値本記録はすぐ開始。映像は待って開始し、失敗はカメラ側の startError に残る
      send({ op: "record_start", name, notes });
      if (startCamera) {
        void startCamera();
      }
    },
    [send, startCamera]
  );

  const stopRecord = useCallback(() => {
    send({ op: "record_stop" });
    if (stopCamera) {
      void stopCamera();
    }
    window.setTimeout(() => void refreshLibrary(), 400);
  }, [send, stopCamera, refreshLibrary]);

  const exitReplay = useCallback(() => {
    setPlaying(false);
    setMode("live");
    setMeta(null);
    setFrames([]);
    setReplayProfile(null);
    setReplayScan(null);
    setReplayControlBase(null);
    setIndex(0);
    setLoadProgress(null);
  }, []);

  const loadReplay = useCallback(async (id: string) => {
    setBusy(true);
    setLoadProgress({ loaded: 0, total: 1 });
    try {
      const detail = await fetchRecording(id);
      const camera = await lookupCameraForRecording(detail);
      const linked = camera ? { ...detail, camera } : detail;
      if (camera && (!detail.camera?.mp4_url || !detail.camera.take_id)) {
        void patchRecording(id, { camera }).catch(() => {
          /* 次回の一覧用。再生自体は linked で進める */
        });
      }
      const all = await fetchAllRecordingFrames(id, (loaded, total) => {
        setLoadProgress({ loaded, total });
      });
      setMeta(linked);
      setFrames(all);
      setReplayProfile(detail.profile ?? null);
      setReplayScan(detail.scan ?? null);
      setReplayControlBase(detail.control ?? null);
      setIndex(0);
      setPlaying(false);
      setMode("replay");
      setLibraryOpen(false);
      setLibraryError(null);
    } catch (e) {
      setLibraryError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setLoadProgress(null);
    }
  }, []);

  const saveMeta = useCallback(
    async (id: string, name: string, notes: string) => {
      const row = await patchRecording(id, { name, notes });
      setLibrary((prev) => prev.map((x) => (x.id === id ? { ...x, ...row } : x)));
      setMeta((prev) => (prev && prev.id === id ? { ...prev, ...row } : prev));
    },
    []
  );

  const removeRecording = useCallback(
    async (id: string) => {
      await deleteRecording(id);
      if (meta?.id === id) exitReplay();
      await refreshLibrary();
    },
    [meta?.id, exitReplay, refreshLibrary]
  );

  const step = useCallback(
    (delta: number) => {
      setPlaying(false);
      setIndex((i) => clampIndex(i + delta, frames.length));
    },
    [frames.length]
  );

  const seek = useCallback(
    (next: number) => {
      setIndex(clampIndex(next, frames.length));
    },
    [frames.length]
  );

  useEffect(() => {
    if (mode !== "replay" || !playing || frames.length === 0) return;
    const ms = Math.max(16, 50 / rate);
    const timer = window.setInterval(() => {
      setIndex((i) => {
        if (i >= frames.length - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, ms);
    return () => window.clearInterval(timer);
  }, [mode, playing, rate, frames.length]);

  const frame = mode === "replay" ? (frames[index] ?? null) : null;
  const history: M5HistoryPoint[] | null = useMemo(() => {
    if (mode !== "replay" || frames.length === 0) return null;
    const start = Math.max(0, index - (HISTORY_MAX - 1));
    return frames.slice(start, index + 1).map(frameToHistory);
  }, [mode, frames, index]);

  const control = useMemo(() => {
    if (mode !== "replay" || !frame) return null;
    return controlFromFrame(frame, replayControlBase);
  }, [mode, frame, replayControlBase]);

  const tNow = frames.length ? elapsedOf(frames, index) : 0;
  const tEnd = frames.length ? elapsedOf(frames, frames.length - 1) : 0;

  return {
    mode,
    library,
    libraryOpen,
    setLibraryOpen,
    libraryError,
    libraryLoading,
    refreshLibrary,
    recordStatus,
    startRecord,
    stopRecord,
    draftName,
    setDraftName,
    draftNotes,
    setDraftNotes,
    meta,
    frames,
    index,
    playing,
    setPlaying,
    rate,
    setRate,
    rates: RATES,
    steps: STEPS,
    step,
    seek,
    loadReplay,
    exitReplay,
    saveMeta,
    removeRecording,
    loadProgress,
    busy,
    frame,
    history,
    control,
    replayProfile,
    replayScan,
    tNow,
    tEnd,
    sampleCount: frames.length,
  };
}
