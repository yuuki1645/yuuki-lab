import { useCallback, useEffect, useMemo, useState } from "react";
import { getCaptureRealtimeBaseUrl, getCaptureRealtimeStreamUrl } from "@/shared/constants";
import ExperimentManager from "@/features/live-capture/ExperimentManager";
import LiveCaptureLiveImuPanel from "@/features/live-capture/LiveCaptureLiveImuPanel";
import LiveCaptureReviewPlayer from "@/features/live-capture/LiveCaptureReviewPlayer";
import LiveCaptureReviewTelemetry from "@/features/live-capture/LiveCaptureReviewTelemetry";
import LiveMjpegView from "@/features/live-capture/LiveMjpegView";
import {
  fetchRecorderStatus,
  startRecording,
  stopRecording,
  type RecorderStatus,
} from "@/shared/recorderApi";
import "./LiveCapturePage.css";

/**
 * 横向き iPad 向け 3 段構成:
 * 1) 実験フォルダ / 録画操作
 * 2) ライブ（左: 映像、右: リアルタイム IMU）
 * 3) 見返し（左: シーク映像、右: 再生位置同期データ）
 */
export default function LiveCapturePage() {
  const baseUrl = useMemo(() => getCaptureRealtimeBaseUrl(), []);
  const [nonce, setNonce] = useState(() => Date.now());
  const [status, setStatus] = useState<RecorderStatus | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /** 見返し操作中（シーク／再生）。ライブ MJPEG は常時表示のまま。 */
  const [reviewActive, setReviewActive] = useState(false);
  /** 見返し video の currentTime（秒）→ 見返しデータ同期用 */
  const [reviewCurrentTime, setReviewCurrentTime] = useState(0);

  const streamUrl = useMemo(
    () => getCaptureRealtimeStreamUrl() + "?t=" + String(nonce),
    [nonce]
  );

  // 録画中は HLS、停止後は mp4 を優先（シーク安定）
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

  const reconnectLive = useCallback(() => {
    setNonce(Date.now());
  }, []);

  const startRecord = useCallback(async () => {
    setBusy(true);
    setApiError(null);
    try {
      const data = await startRecording();
      setStatus(data);
      setReviewActive(true);
      setReviewCurrentTime(0);
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
      setReviewActive(true);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const recording = Boolean(status?.recording);
  const canReview = Boolean(reviewSrc);
  const diskWarn = status?.disk?.warning;
  const canStart =
    !busy &&
    Boolean(status?.experiment_id) &&
    status?.disk?.ok_for_record !== false;

  // 見返しテレメトリ: take があり t0 または jsonl があるとき有効
  const reviewTelemetryEnabled = Boolean(
    status?.take_id &&
      (status.video_t0_unix != null || status.imu_url || status.commands_url)
  );

  return (
    <div className="live-capture live-capture--tiers">
      {/* ── 1段目: 実験フォルダ + 録画操作 ── */}
      <section className="live-capture__tier live-capture__tier--top" aria-label="実験と録画">
        <header className="live-capture__header">
          <h1>実機カメラ</h1>
          <p>
            Recorder（本線）経由のライブと記録。起動は <code>npm run dev:lab</code>。
            見返しはシークバーで録画開始以降を自由に移動できます。
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
      </section>

      {/* ── 2段目: ライブ映像 | ライブ IMU ── */}
      <section className="live-capture__tier live-capture__tier--live" aria-label="ライブ">
        <h2 className="live-capture__tier-title">ライブ（低遅延）</h2>
        <div className="live-capture__band">
          <div className="live-capture__band-media">
            <LiveMjpegView streamUrl={streamUrl} />
          </div>
          <div className="live-capture__band-data">
            <LiveCaptureLiveImuPanel />
          </div>
        </div>
      </section>

      {/* ── 3段目: 見返し映像 | 見返し時点データ ── */}
      <section className="live-capture__tier live-capture__tier--review" aria-label="見返し">
        <h2 className="live-capture__tier-title">見返し（録画開始以降・シーク可）</h2>
        <div className="live-capture__band">
          <div className="live-capture__band-media">
            <LiveCaptureReviewPlayer
              src={canReview ? reviewSrc : null}
              recording={recording}
              reviewActive={reviewActive}
              onReviewActiveChange={setReviewActive}
              onCurrentTimeChange={setReviewCurrentTime}
            />
            {status?.mp4_url ? (
              <p className="live-capture__hint">
                保存ファイル:{" "}
                <a href={baseUrl + status.mp4_url} target="_blank" rel="noreferrer">
                  {status.mp4_url}
                </a>
              </p>
            ) : null}
          </div>
          <div className="live-capture__band-data">
            <LiveCaptureReviewTelemetry
              recorderBaseUrl={baseUrl}
              imuUrl={status?.imu_url ?? null}
              commandsUrl={status?.commands_url ?? null}
              videoT0Unix={status?.video_t0_unix ?? null}
              reviewCurrentTime={reviewCurrentTime}
              recording={recording}
              enabled={reviewTelemetryEnabled}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
