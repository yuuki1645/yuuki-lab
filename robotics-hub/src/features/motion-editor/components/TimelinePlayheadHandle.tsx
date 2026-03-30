import { useCallback } from "react";
import { useTimelineContext } from "../contexts/TimelineContext";
import "./Timeline.css";

const HANDLE_CENTER_OFFSET_PX = 20;

export default function TimelinePlayheadHandle() {
  const {
    currentTime,
    timeToX,
    xToTime,
    getClientX,
    scrollableRef,
    isPlayheadDragging,
    onPlayheadDrag,
    onPlayheadDragEnd,
    endKeyframeDrag,
  } = useTimelineContext();

  const setupDrag = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.stopPropagation();
      e.preventDefault();
      endKeyframeDrag?.();
      onPlayheadDrag(currentTime);
      if (!scrollableRef?.current) return;

      const handleMove = (ev: MouseEvent | TouchEvent) => {
        ev.preventDefault();
        if (!scrollableRef?.current) return;
        const clientX = getClientX(ev as unknown as React.MouseEvent);
        const r = scrollableRef.current.getBoundingClientRect();
        const x = clientX - r.left + scrollableRef.current.scrollLeft;
        const playheadLeft = x - HANDLE_CENTER_OFFSET_PX;
        const newTime = xToTime(Math.max(0, playheadLeft));
        onPlayheadDrag(newTime);
      };

      const handleEnd = () => {
        document.removeEventListener("mousemove", handleMove);
        document.removeEventListener("mouseup", handleEnd);
        document.removeEventListener("touchmove", handleMove);
        document.removeEventListener("touchend", handleEnd);
        document.removeEventListener("touchcancel", handleEnd);
        onPlayheadDragEnd?.();
      };

      document.addEventListener("mousemove", handleMove);
      document.addEventListener("mouseup", handleEnd);
      document.addEventListener("touchmove", handleMove as EventListener, {
        passive: false,
      });
      document.addEventListener("touchend", handleEnd);
      document.addEventListener("touchcancel", handleEnd);
    },
    [
      currentTime,
      scrollableRef,
      getClientX,
      xToTime,
      onPlayheadDrag,
      onPlayheadDragEnd,
      endKeyframeDrag,
    ]
  );

  return (
    <div className="timeline-playhead-handle-container">
      <div
        className={`timeline-playhead-handle ${isPlayheadDragging ? "dragging" : ""}`}
        style={{ left: `${timeToX(currentTime)}px` }}
        onMouseDown={setupDrag}
        onTouchStart={setupDrag}
      />
    </div>
  );
}
