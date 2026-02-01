import { useTimelineContext } from "../contexts/TimelineContext";
import TimelineKeyframe from "./TimelineKeyframe";
import "./Timeline.css";

interface TimelineTrackProps {
  channel: number;
}

export default function TimelineTrack({ channel }: TimelineTrackProps) {
  const {
    keyframes,
    currentTime,
    timeToX,
    xToTime,
    scrollableRef,
    getClientX,
    isDragging,
    isPlayheadDragging,
    selectedKeyframeId,
    onTimeClick,
  } = useTimelineContext();

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
    if (trackContent) {
      if (!scrollableRef.current) return;
      const rect = scrollableRef.current.getBoundingClientRect();
      const clientX = getClientX(e);
      const x = clientX - rect.left;
      const time = xToTime(x);
      onTimeClick(time, channel);
    }
  };

  return (
    <div
      className="timeline-track"
      data-channel={channel}
      onClick={handleTrackClick}
      onTouchEnd={handleTrackClick}
    >
      <div
        className="timeline-track-content"
        onClick={handleTrackClick}
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
