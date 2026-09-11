import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import LiveMjpegView from "@/features/live-capture/LiveMjpegView";
import type { M5RecordCamera } from "./types";
import { resolveReplayVideoSrc, type useM5Camera } from "./useM5Camera";
import "./M5CameraPane.css";

type Cam = ReturnType<typeof useM5Camera>;

type Props = {
  camera: Cam;
  replaying: boolean;
  replayCamera: M5RecordCamera | null | undefined;
  /** 再生ヘッド（映像開始からの秒） */
  playheadSec: number;
  playing: boolean;
};

function fmtClock(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return "00:00.00";
  const ms = Math.floor((sec % 1) * 100);
  const s = Math.floor(sec);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}.${String(ms).padStart(2, "0")}`;
}

/**
 * 右脚タブ左カラム上段の実機映像。
 * ライブは MJPEG（iframe 隔離）、再生は mp4/HLS を記録バーの時刻に合わせる。
 */
export function M5CameraPane({ camera, replaying, replayCamera, playheadSec, playing }: Props) {
  const [peekReview, setPeekReview] = useState(false);
  const recording = Boolean(camera.status?.recording);
  const replaySrc = resolveReplayVideoSrc(camera.baseUrl, replayCamera);
  const showReplay = replaying && Boolean(replaySrc);
  const showReview = !replaying && peekReview && Boolean(camera.reviewSrc);
  const showLive = !showReplay && !showReview;

  const diskWarn = camera.status?.disk?.warning;
  const fps = camera.status?.fps;
  const size = camera.status?.frame_size;

  const body = (
    <div className={"m5-cam" + (camera.expanded ? " m5-cam--expanded" : "")}>
      <header className="m5-cam__chrome">
        <div className="m5-cam__titles">
          {showReplay ? (
            <span className="m5-cam__badge m5-cam__badge--replay">再生映像</span>
          ) : recording ? (
            <span className="m5-cam__badge m5-cam__badge--rec">REC</span>
          ) : (
            <span className="m5-cam__badge m5-cam__badge--live">LIVE</span>
          )}
          <strong>実機カメラ</strong>
          {typeof fps === "number" ? (
            <span className="m5-cam__nums">{fps.toFixed(0)} fps</span>
          ) : null}
          {Array.isArray(size) && size.length >= 2 ? (
            <span className="m5-cam__nums">
              {size[0]}×{size[1]}
            </span>
          ) : null}
        </div>
        <div className="m5-cam__chrome-actions">
          {!replaying && recording && camera.reviewSrc ? (
            <button
              type="button"
              className={"m5-cam__mini" + (peekReview ? " m5-cam__mini--on" : "")}
              onClick={() => setPeekReview((v) => !v)}
            >
              {peekReview ? "ライブへ" : "見返し"}
            </button>
          ) : null}
          <button type="button" className="m5-cam__mini" onClick={camera.reconnectLive}>
            再接続
          </button>
          <button
            type="button"
            className="m5-cam__mini"
            onClick={() => camera.setExpanded(!camera.expanded)}
          >
            {camera.expanded ? "閉じる" : "拡大"}
          </button>
        </div>
      </header>

      <div className="m5-cam__stage">
        {showReplay ? (
          <ScrubVideo src={replaySrc!} currentTime={playheadSec} playing={playing} />
        ) : replaying ? (
          <div className="m5-cam__empty">
            <p>この記録に映像はありません</p>
          </div>
        ) : showReview ? (
          <ScrubVideo
            src={camera.reviewSrc!}
            currentTime={camera.status?.elapsed_sec ?? 0}
            playing={false}
          />
        ) : (
          <div className="m5-cam__live">
            <LiveMjpegView streamUrl={camera.liveUrl} />
            {camera.error && !camera.status ? (
              <div className="m5-cam__empty">
                <p>カメラ未接続</p>
                <span>{camera.error}</span>
                <button type="button" className="m5__btn" onClick={() => void camera.refresh()}>
                  再試行
                </button>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <footer className="m5-cam__foot">
        {replaying ? (
          <span className="m5-cam__nums">{fmtClock(playheadSec)}</span>
        ) : (
          <label className="m5-cam__exp">
            実験
            <select
              disabled={recording || camera.busy}
              value={camera.status?.experiment_id ?? ""}
              onChange={(e) => void camera.selectExp(e.target.value)}
            >
              <option value="">（自動作成）</option>
              {camera.experiments.map((ex) => (
                <option key={ex.id} value={ex.id}>
                  {ex.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {camera.status?.take_id ? (
          <span className="m5-cam__meta">take {camera.status.take_id}</span>
        ) : null}
        {diskWarn ? <span className="m5-cam__warn">{diskWarn}</span> : null}
      </footer>
    </div>
  );

  if (camera.expanded) {
    return (
      <>
        <div className="m5-cam__slot m5-cam__slot--hold" aria-hidden />
        <div className="m5-cam__overlay" role="dialog" aria-label="映像拡大">
          <button
            type="button"
            className="m5-cam__scrim"
            aria-label="拡大を閉じる"
            onClick={() => camera.setExpanded(false)}
          />
          {body}
        </div>
      </>
    );
  }

  return <div className="m5-cam__slot">{body}</div>;
}

/**
 * 再生の時計はテレメトリ側。video.play() すると iPad で
 * currentTime シークと衝突して数秒で止まるので、常に pause してコマ送りする。
 */
function ScrubVideo({
  src,
  currentTime,
}: {
  src: string;
  currentTime: number;
  playing: boolean;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const srcRef = useRef<string | null>(null);
  const wantRef = useRef(currentTime);
  const seekingRef = useRef(false);
  const [failed, setFailed] = useState(false);
  wantRef.current = currentTime;

  const applySeek = useCallback(() => {
    const el = ref.current;
    if (!el || el.readyState < 1 || seekingRef.current) return;
    if (!Number.isFinite(wantRef.current)) return;
    const dur = Number.isFinite(el.duration) && el.duration > 0 ? el.duration : Number.POSITIVE_INFINITY;
    const t = Math.min(Math.max(0, wantRef.current), Math.max(0, dur - 0.04));
    if (Math.abs(el.currentTime - t) < 0.04) return;
    seekingRef.current = true;
    try {
      el.pause();
      el.currentTime = t;
    } catch {
      seekingRef.current = false;
    }
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (srcRef.current !== src) {
      el.pause();
      el.src = src;
      srcRef.current = src;
      seekingRef.current = false;
      setFailed(false);
    }
    const onSeeked = () => {
      seekingRef.current = false;
      applySeek();
    };
    const onReady = () => {
      seekingRef.current = false;
      applySeek();
    };
    el.addEventListener("seeked", onSeeked);
    el.addEventListener("loadedmetadata", onReady);
    el.addEventListener("loadeddata", onReady);
    return () => {
      el.removeEventListener("seeked", onSeeked);
      el.removeEventListener("loadedmetadata", onReady);
      el.removeEventListener("loadeddata", onReady);
    };
  }, [src, applySeek]);

  useEffect(() => {
    applySeek();
  }, [currentTime, applySeek]);

  const kind = useMemo(() => {
    if (src.includes(".m3u8")) return "HLS";
    if (src.includes(".mp4")) return "mp4";
    return "video";
  }, [src]);

  return (
    <div className="m5-cam__review">
      <video
        ref={ref}
        className="m5-cam__video"
        playsInline
        muted
        preload="auto"
        onError={() => setFailed(true)}
      />
      <span className="m5-cam__kind">{kind}</span>
      {failed ? (
        <div className="m5-cam__empty">
          <p>映像ファイルを開けませんでした</p>
          <span>{src}</span>
        </div>
      ) : null}
    </div>
  );
}
