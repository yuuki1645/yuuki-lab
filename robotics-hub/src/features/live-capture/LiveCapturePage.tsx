import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCaptureRealtimeBaseUrl, getCaptureRealtimeStreamUrl } from "@/shared/constants";
import ExperimentManager from "@/features/live-capture/ExperimentManager";
import LiveCaptureDebugAside from "@/features/live-capture/LiveCaptureDebugAside";
import LiveMjpegView from "@/features/live-capture/LiveMjpegView";
import {
  fetchRecorderStatus,
  startRecording,
  stopRecording,
  type RecorderStatus,
} from "@/shared/recorderApi";
import "./LiveCapturePage.css";

/**
 * 横向き iPad 向け: 左に実験管理・カメラ／録画、右にセンサー。
 * IMU は右ペインが Recorder 経由で購読。ライブ MJPEG は memo / iframe で隔離。
 */
export default function LiveCapturePage() {
  const baseUrl = useMemo(() => getCaptureRealtimeBaseUrl(), []);
  const [nonce, setNonce] = useState(() => Date.now());
  const [status, setStatus] = useState<RecorderStatus | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reviewMode, setReviewMode] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const streamUrl = useMemo(
    () => getCaptureRealtimeStreamUrl() + "?t=" + String(nonce),
    [nonce]
  );

  const reviewSrc = useMemo(() => {
    if (!status?.take_id) return null;
    if (status.mp4_url) return baseUrl + status.mp4_url;
    if (status.hls_url) return baseUrl + status.hls_url;
    return null;
  }, [baseUrl, status]);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await fetchRecorderStatus();
      setStatus(data);
      setApiError(null);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void fetchStatus();
    const id = window.setInterval(() => {
      void fetchStatus();
    }, 1000);
    return () => window.clearInterval(id);
  }, [fetchStatus]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !reviewSrc || !reviewMode) return;
    if (el.src !== reviewSrc) {
      el.src = reviewSrc;
      void el.play().catch(() => {
        /* ユーザー操作待ち */
      });
    }
  }, [reviewSrc, reviewMode]);

  const reconnectLive = useCallback(() => {
    setNonce(Date.now());
  }, []);

  const startRecord = useCallback(async () => {
    setBusy(true);
    setApiError(null);
    try {
      const data = await startRecording();
      setStatus(data);
      setReviewMode(true);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : String(e));
      void fetchStatus();
    } finally {
      setBusy(false);
    }
  }, [fetchStatus]);

  const stopRecord = useCallback(async () => {
    setBusy(true);
    setApiError(null);
    try {
      const data = await stopRecording();
      setStatus(data);
      setReviewMode(true);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const seekBack30 = useCallback(() => {
    const el = videoRef.current;
    if (!el) return;
    setReviewMode(true);
    const end =
      el.seekable.length > 0
        ? el.seekable.end(el.seekable.length - 1)
        : Number.isFinite(el.duration) && el.duration > 0
          ? el.duration
          : el.currentTime;
    el.currentTime = Math.max(0, end - 30);
    void el.play().catch(() => {
      /* ignore */
    });
  }, []);

  const jumpLiveEdge = useCallback(() => {
    const el = videoRef.current;
    if (!el) return;
    if (el.seekable.length > 0) {
      el.currentTime = el.seekable.end(el.seekable.length - 1);
    }
    void el.play().catch(() => {
      /* ignore */
    });
  }, []);

  const focusLive = useCallback(() => {
    setReviewMode(false);
    const el = videoRef.current;
    if (el) {
      el.pause();
    }
  }, []);

  const recording = Boolean(status?.recording);
  const canReview = Boolean(reviewSrc);
  const diskWarn = status?.disk?.warning;
  const canStart =
    !busy &&
    Boolean(status?.experiment_id) &&
    status?.disk?.ok_for_record !== false;

  return (
    <div className="live-capture live-capture--split">
      <div className="live-capture__main">
        <header className="live-capture__header">
          <h1>実機カメラ</h1>
          <p>
            Recorder（本線）経由のライブと記録。起動は <code>npm run dev:lab</code>。
          </p>
        </header>

        <ExperimentManager recording={recording} />

        <div className="live-capture__toolbar">
          <span className="live-capture__url">{baseUrl}</span>
          {status?.experiment_id ? (
            <span className="live-capture__meta-pill">実験: {status.experiment_id}</span>
          ) : (
            <span className="live-capture__meta-pill live-capture__meta-pill--warn">
              実験未選択
            </span>
          )}
          {status?.take_id ? (
            <span className="live-capture__meta-pill">take: {status.take_id}</span>
          ) : null}
          <button type="button" className="live-capture__btn" onClick={reconnectLive}>
            ライブ再接続
          </button>
          {recording ? (
            <button
              type="button"
              className="live-capture__btn live-capture__btn--danger"
              disabled={busy}
              onClick={() => void stopRecord()}
            >
              録画停止
              {status?.elapsed_sec != null ? `（${Math.floor(status.elapsed_sec)}s）` : ""}
            </button>
          ) : (
            <button
              type="button"
              className="live-capture__btn live-capture__btn--primary"
              disabled={!canStart}
              onClick={() => void startRecord()}
              title={
                !status?.experiment_id
                  ? "実験フォルダを選択してください"
                  : status?.disk?.ok_for_record === false
                    ? diskWarn ?? "ディスク空き不足"
                    : undefined
              }
            >
              録画開始
            </button>
          )}
          {recording ? (
            <span className="live-capture__rec-badge" aria-live="polite">
              REC
            </span>
          ) : null}
        </div>

        {diskWarn ? (
          <div className="live-capture__error" role="alert">
            ディスク: {diskWarn}
          </div>
        ) : null}
        {apiError ? (
          <div className="live-capture__error" role="alert">
            {apiError}
          </div>
        ) : null}

        <LiveMjpegView streamUrl={streamUrl} />

        <section className="live-capture__section" aria-label="見返し">
          <div className="live-capture__section-head">
            <h2 className="live-capture__section-title">見返し（録画開始以降）</h2>
            <div className="live-capture__review-actions">
              <button
                type="button"
                className="live-capture__btn"
                disabled={!canReview}
                onClick={seekBack30}
              >
                -30秒
              </button>
              <button
                type="button"
                className="live-capture__btn"
                disabled={!canReview || !recording}
                onClick={jumpLiveEdge}
              >
                録画の先端へ
              </button>
              <button
                type="button"
                className="live-capture__btn"
                disabled={!reviewMode}
                onClick={focusLive}
              >
                ライブに戻る
              </button>
            </div>
          </div>
          {!canReview ? (
            <p className="live-capture__hint">録画を開始すると、ここにシーク可能な映像が出ます。</p>
          ) : (
            <div
              className={
                "live-capture__stage" +
                (reviewMode ? " live-capture__stage--review-active" : "")
              }
            >
              <video
                ref={videoRef}
                className="live-capture__video"
                controls
                playsInline
                src={reviewSrc ?? undefined}
              />
            </div>
          )}
          {status?.mp4_url ? (
            <p className="live-capture__hint">
              保存ファイル:{" "}
              <a href={baseUrl + status.mp4_url} target="_blank" rel="noreferrer">
                {status.mp4_url}
              </a>
            </p>
          ) : null}
        </section>
      </div>

      <LiveCaptureDebugAside />
    </div>
  );
}
