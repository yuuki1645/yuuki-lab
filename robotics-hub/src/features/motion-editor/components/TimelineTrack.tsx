import { useRef } from "react";
import { TIMELINE_KEYFRAME_CENTER_OFFSET_PX } from "@/shared/constants";
import { useTimelineContext } from "../contexts/TimelineContext";
import TimelineKeyframe from "./TimelineKeyframe";
import "./Timeline.css";

interface TimelineTrackProps {
  channel: number;
}

const TAP_MAX_DURATION_MS = 400;

export default function TimelineTrack({ channel }: TimelineTrackProps) {
  const {
    keyframes,
    currentTime,
    timeToX,
    xToTime,
    getClientX,
    isDragging,
    isPlayheadDragging,
    selectedKeyframeId,
    onTimeClick,
  } = useTimelineContext();

  const touchStartRef = useRef<{
    clientX: number;
    time: number;
  } | null>(null);

  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.target instanceof HTMLElement && e.target.closest(".timeline-track-content")) {
      const t = e.changedTouches[0] ?? e.touches[0];
      if (t) {
        touchStartRef.current = { clientX: t.clientX, time: Date.now() };
      }
    }
  };

  const handleTouchMove = () => {
    touchStartRef.current = null;
  };

  const handleTrackClick = (e: React.MouseEvent | React.TouchEvent) => {
    if (isDragging || isPlayheadDragging) return;
    if (
      (e.target as HTMLElement).closest(".timeline-keyframe") ||
      (e.target as HTMLElement).closest(".timeline-track-label") ||
      (e.target as HTMLElement).closest(".timeline-playhead")
    ) {
      return;
    }
    const trackContent = (e.target as HTMLElement).closest(
      ".timeline-track-content"
    );
    if (!trackContent) return;

    if (e.type === "touchend" && !touchStartRef.current) {
      return;
    }
    const trackRect = (trackContent as HTMLElement).getBoundingClientRect();
    let clientX: number;
    if (e.type === "touchend" && touchStartRef.current) {
      const start = touchStartRef.current;
      clientX = Date.now() - start.time <= TAP_MAX_DURATION_MS ? start.clientX : getClientX(e);
      touchStartRef.current = null;
    } else {
      clientX = getClientX(e);
    }
    const x = clientX - trackRect.left - TIMELINE_KEYFRAME_CENTER_OFFSET_PX;
    const time = xToTime(x);
    onTimeClick(time, channel);
  };

  return (
    <div
      className="timeline-track"
      data-channel={channel}
      onClick={handleTrackClick}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTrackClick}
    >
      <div
        className="timeline-track-content"
        onClick={handleTrackClick}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTrackClick}
      >
        <div
          className={`timeline-playhead ${isPlayheadDragging ? "dragging" : ""}`}
          style={{ left: `${timeToX(currentTime)}px` }}
        />
        {keyframes.map((kf) => {
          if (kf.channel !== channel) return null;
          const x = timeToX(kf.time);
          const isSelected = selectedKeyframeId === kf.id;
          return (
            <TimelineKeyframe
              key={kf.id}
              keyframe={kf}
              keyframeId={kf.id}
              channel={channel}
              x={x}
              isSelected={isSelected}
              angle={kf.angle ?? 90}
            />
          );
        })}
      </div>
    </div>
  );
}
