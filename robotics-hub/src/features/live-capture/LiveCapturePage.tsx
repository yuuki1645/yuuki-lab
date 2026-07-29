import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCaptureRealtimeBaseUrl, getCaptureRealtimeStreamUrl } from "@/shared/constants";
import { useDaemonImuTelemetry } from "@/shared/contexts/DaemonImuTelemetryContext";
import ImuAttitudeGauges from "@/shared/components/ImuAttitudeGauges";
import "./LiveCapturePage.css";

type CaptureStatus = {
  ok: boolean;
  recording: boolean;
  session_id: string | null;
  elapsed_sec: number | null;
  hls_url: string | null;
  mp4_url: string | null;
  frame_size: number[] | null;
  fps: number;
  has_audio: boolean;
  error?: string;
  message?: string;
};

/**
 * 横向き iPad 向け: 左にカメラ／録画、右にセンサー・デバッグ枠。
 */
export default function LiveCapturePage() {
  const baseUrl = useMemo(() => getCaptureRealtimeBaseUrl(), []);
  const imu = useDaemonImuTelemetry();
  const [nonce, setNonce] = useState(() => Date.now());
  const [imgError, setImgError] = useState(false);
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reviewMode, setReviewMode] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const streamUrl = useMemo(
    () => getCaptureRealtimeStreamUrl() + "?t=" + String(nonce),
    [nonce]
  );

  const reviewSrc = useMemo(() => {
    if (!status?.session_id) return null;
    if (status.mp4_url) return baseUrl + status.mp4_url;
    if (status.hls_url) return baseUrl + status.hls_url;
    return null;
  }, [baseUrl, status]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(baseUrl + "/api/status", { cache: "no-store" });
      if (!res.ok) throw new Error("status HTTP " + String(res.status));
      const data = (await res.json()) as CaptureStatus;
      setStatus(data);
      setApiError(null);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : String(e));
    }
  }, [baseUrl]);

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
    setImgError(false);
    setNonce(Date.now());
  }, []);

  const startRecord = useCallback(async () => {
    setBusy(true);
    setApiError(null);
    try {
      const res = await fetch(baseUrl + "/api/record/start", { method: "POST" });
      const data = (await res.json()) as CaptureStatus;
      if (!res.ok || data.ok === false) {
        throw new Error(data.message ?? data.error ?? "録画開始に失敗しました");
      }
      setStatus(data);
      setReviewMode(true);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [baseUrl]);

  const stopRecord = useCallback(async () => {
    setBusy(true);
    setApiError(null);
    try {
      const res = await fetch(baseUrl + "/api/record/stop", { method: "POST" });
      const data = (await res.json()) as CaptureStatus;
      if (!res.ok) {
        throw new Error(data.message ?? data.error ?? "録画停止に失敗しました");
      }
      setStatus(data);
      setReviewMode(true);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [baseUrl]);

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

  return (
    <div className="live-capture live-capture--split">
      {/* 左: カメラ・録画（横向き iPad の主領域） */}
      <div className="live-capture__main">
        <header className="live-capture__header">
          <h1>実機カメラ</h1>
          <p>
            左: 低遅延ライブと録画見返し。右: センサー／デバッグ。起動は{" "}
            <code>npm run dev:lab</code>。
          </p>
        </header>

        <div className="live-capture__toolbar">
          <span className="live-capture__url">{baseUrl}</span>
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
              disabled={busy}
              onClick={() => void startRecord()}
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

        {apiError ? (
          <div className="live-capture__error" role="alert">
            {apiError}
          </div>
        ) : null}
        {imgError ? (
          <div className="live-capture__error" role="alert">
            ライブ映像を取得できません。serve_realtime / デバイス占有 / ファイアウォールを確認してください。
          </div>
        ) : null}

        <section className="live-capture__section" aria-label="ライブ">
          <h2 className="live-capture__section-title">ライブ（低遅延）</h2>
          <div className="live-capture__stage">
            <img
              key={streamUrl}
              className="live-capture__img"
              src={streamUrl}
              alt="実機カメラのライブ映像"
              onError={() => setImgError(true)}
              onLoad={() => setImgError(false)}
            />
          </div>
        </section>

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

      {/* 右: センサー・ログ・デバッグ（今後ここに追加） */}
      <aside className="live-capture__aside" aria-label="デバッグ・センサー">
        <header className="live-capture__aside-header">
          <h2 className="live-capture__aside-title">デバッグ / センサー</h2>
          <p className="live-capture__aside-sub">
            robot-daemon（{imu.url}）
          </p>
        </header>

        <section className="live-capture__aside-card" aria-label="IMU 姿勢">
          <h3 className="live-capture__aside-card-title">IMU 姿勢（ピッチ／ロール）</h3>
          <p className="live-capture__aside-meta">
            状態:{" "}
            <span
              className={
                "live-capture__ws live-capture__ws--" + imu.wsStatus
              }
            >
              {imu.wsStatus}
            </span>
            {imu.lastError ? ` / ${imu.lastError}` : null}
          </p>
          <ImuAttitudeGauges
            pitch={imu.lastSample?.angle?.pitch}
            roll={imu.lastSample?.angle?.roll}
            connected={imu.wsStatus === "connected"}
          />
        </section>

        <section className="live-capture__aside-card live-capture__aside-card--placeholder">
          <h3 className="live-capture__aside-card-title">ログ・その他</h3>
          <p className="live-capture__hint">今後、デバッグログや他センサーをここに追加します。</p>
        </section>
      </aside>
    </div>
  );
}
