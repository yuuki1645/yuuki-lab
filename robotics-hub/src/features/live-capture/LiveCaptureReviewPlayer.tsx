import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type LiveCaptureReviewPlayerProps = {
  /** HLS or mp4 の絶対 URL */
  src: string | null;
  recording: boolean;
  /** 見返し操作中（ハイライト） */
  reviewActive: boolean;
  onReviewActiveChange: (active: boolean) => void;
  /** 再生位置（秒）を親へ通知 → 見返しテレメトリ同期 */
  onCurrentTimeChange: (t: number) => void;
};

function fmtClock(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return "0:00";
  const s = Math.floor(sec);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

/**
 * 見返し映像 + カスタムシークバー（録画開始以降の DVR 操作）。
 * ネイティブ controls に加え、iPad でも使いやすい range を並べる。
 */
export default function LiveCaptureReviewPlayer({
  src,
  recording,
  reviewActive,
  onReviewActiveChange,
  onCurrentTimeChange,
}: LiveCaptureReviewPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [seekEnd, setSeekEnd] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [dragValue, setDragValue] = useState(0);
  const followLiveRef = useRef(true);
  const lastSrcRef = useRef<string | null>(null);

  const refreshSeekable = useCallback(() => {
    const el = videoRef.current;
    if (!el) return;
    let end = 0;
    if (el.seekable.length > 0) {
      end = el.seekable.end(el.seekable.length - 1);
    } else if (Number.isFinite(el.duration) && el.duration > 0) {
      end = el.duration;
    }
    if (Number.isFinite(end) && end >= 0) {
      setSeekEnd(end);
    }
    if (!dragging) {
      setCurrentTime(el.currentTime);
      onCurrentTimeChange(el.currentTime);
    }
  }, [dragging, onCurrentTimeChange]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !src) return;
    if (lastSrcRef.current !== src) {
      const prevTime = el.currentTime;
      el.src = src;
      lastSrcRef.current = src;
      // mp4 に切り替わったときなど、可能なら位置を維持
      const onLoaded = () => {
        if (prevTime > 0 && Number.isFinite(el.duration)) {
          el.currentTime = Math.min(prevTime, el.duration || prevTime);
        }
        refreshSeekable();
      };
      el.addEventListener("loadedmetadata", onLoaded, { once: true });
    }
  }, [src, refreshSeekable]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const onTime = () => {
      if (dragging) return;
      setCurrentTime(el.currentTime);
      onCurrentTimeChange(el.currentTime);
      if (el.seekable.length > 0) {
        const end = el.seekable.end(el.seekable.length - 1);
        setSeekEnd(end);
        // 先端付近なら「ライブ追従」フラグを維持
        if (end - el.currentTime < 1.25) {
          followLiveRef.current = true;
        }
      }
    };
    const onSeeking = () => onReviewActiveChange(true);
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("seeked", onTime);
    el.addEventListener("progress", refreshSeekable);
    el.addEventListener("durationchange", refreshSeekable);
    el.addEventListener("seeking", onSeeking);
    const id = window.setInterval(refreshSeekable, 500);
    return () => {
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("seeked", onTime);
      el.removeEventListener("progress", refreshSeekable);
      el.removeEventListener("durationchange", refreshSeekable);
      el.removeEventListener("seeking", onSeeking);
      window.clearInterval(id);
    };
  }, [src, dragging, onCurrentTimeChange, onReviewActiveChange, refreshSeekable]);

  // 録画中: 先端追従時は seekable 先端へ寄せる（スクラブ中は無効）
  useEffect(() => {
    if (!recording) return;
    const id = window.setInterval(() => {
      const el = videoRef.current;
      if (!el || !followLiveRef.current || dragging) return;
      if (el.seekable.length === 0) return;
      const end = el.seekable.end(el.seekable.length - 1);
      // プレイリスト延長で先端が進んだときだけ軽く追従
      if (end - el.currentTime > 2.5 && end - el.currentTime < 12) {
        el.currentTime = Math.max(0, end - 0.35);
      }
    }, 1000);
    return () => window.clearInterval(id);
  }, [recording, dragging]);

  const sliderValue = dragging ? dragValue : currentTime;
  const sliderMax = Math.max(seekEnd, sliderValue, 0.01);

  const seekTo = useCallback(
    (t: number) => {
      const el = videoRef.current;
      if (!el) return;
      followLiveRef.current = false;
      onReviewActiveChange(true);
      const end =
        el.seekable.length > 0
          ? el.seekable.end(el.seekable.length - 1)
          : sliderMax;
      el.currentTime = Math.max(0, Math.min(t, end));
      void el.play().catch(() => {
        /* ignore */
      });
    },
    [onReviewActiveChange, sliderMax]
  );

  const seekBack30 = useCallback(() => {
    seekTo(Math.max(0, (videoRef.current?.currentTime ?? 0) - 30));
  }, [seekTo]);

  const jumpLiveEdge = useCallback(() => {
    const el = videoRef.current;
    if (!el || el.seekable.length === 0) return;
    followLiveRef.current = true;
    onReviewActiveChange(true);
    el.currentTime = el.seekable.end(el.seekable.length - 1);
    void el.play().catch(() => {
      /* ignore */
    });
  }, [onReviewActiveChange]);

  const pauseReview = useCallback(() => {
    followLiveRef.current = false;
    onReviewActiveChange(false);
    videoRef.current?.pause();
  }, [onReviewActiveChange]);

  const mediaLabel = useMemo(() => {
    if (!src) return "";
    if (src.includes(".m3u8")) return "HLS（録画中の後追い可）";
    if (src.includes(".mp4")) return "mp4";
    return "video";
  }, [src]);

  if (!src) {
    return (
      <p className="live-capture__hint">録画を開始すると、ここにシーク可能な見返し映像が出ます。</p>
    );
  }

  return (
    <div
      className={
        "live-capture__stage live-capture__stage--review" +
        (reviewActive ? " live-capture__stage--review-active" : "")
      }
    >
      <video
        ref={videoRef}
        className="live-capture__video"
        controls
        playsInline
        preload="auto"
      />

      <div className="live-capture__seek" aria-label="見返しシーク">
        <input
          type="range"
          className="live-capture__seek-range"
          min={0}
          max={sliderMax}
          step={0.05}
          value={Math.min(sliderValue, sliderMax)}
          onPointerDown={() => {
            setDragging(true);
            setDragValue(currentTime);
            followLiveRef.current = false;
            onReviewActiveChange(true);
          }}
          onChange={(e) => {
            const v = Number(e.target.value);
            setDragValue(v);
            setDragging(true);
          }}
          onPointerUp={(e) => {
            const v = Number((e.target as HTMLInputElement).value);
            setDragging(false);
            seekTo(v);
          }}
          onKeyUp={(e) => {
            if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
              seekTo(Number((e.target as HTMLInputElement).value));
            }
          }}
        />
        <div className="live-capture__seek-meta">
          <span>
            {fmtClock(sliderValue)} / {fmtClock(seekEnd)}
            {recording && followLiveRef.current ? " · 先端付近" : ""}
          </span>
          <span className="live-capture__seek-kind">{mediaLabel}</span>
        </div>
      </div>

      <div className="live-capture__review-actions">
        <button type="button" className="live-capture__btn" onClick={seekBack30}>
          -30秒
        </button>
        <button
          type="button"
          className="live-capture__btn"
          disabled={!recording && seekEnd <= 0}
          onClick={jumpLiveEdge}
        >
          録画の先端へ
        </button>
        <button
          type="button"
          className="live-capture__btn"
          disabled={!reviewActive}
          onClick={pauseReview}
        >
          ライブに戻る（見返し一時停止）
        </button>
      </div>
    </div>
  );
}
