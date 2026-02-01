import { useTimelineContext } from "../contexts/TimelineContext";
import { MAX_MOTION_DURATION } from "../constants";
import "./Timeline.css";

export default function TimelineRuler() {
  const { timeToX, currentTime, isPlayheadDragging } = useTimelineContext();

  const displayDuration = MAX_MOTION_DURATION;
  const markerCount = 20;

  const timeMarkers: number[] = [];
  for (let i = 0; i <= markerCount; i++) {
    const time = (displayDuration / markerCount) * i;
    timeMarkers.push(time);
  }

  const playheadLeft = Math.max(0, timeToX(currentTime));

  return (
    <div className="timeline-header">
      <div className="timeline-ruler">
        {timeMarkers.map((time, i) => (
          <div
            key={i}
            className="timeline-marker"
            style={{ left: `${timeToX(time)}px` }}
          >
            <div className="timeline-marker-line" />
            <div className="timeline-marker-label">
              {(time / 1000).toFixed(1)}s
            </div>
          </div>
        ))}
        <div
          className={`timeline-ruler-playhead ${isPlayheadDragging ? "dragging" : ""}`}
          style={{ left: `${playheadLeft}px` }}
        />
      </div>
    </div>
  );
}
