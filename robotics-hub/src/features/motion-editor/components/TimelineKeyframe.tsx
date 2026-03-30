import { useRef, useEffect } from "react";
import { useTimelineContext } from "../contexts/TimelineContext";
import type { Keyframe } from "@/shared/types";
import "./Timeline.css";

interface TimelineKeyframeProps {
  keyframe: Keyframe;
  keyframeId: string;
  channel: number;
  x: number;
  isSelected: boolean;
  angle: number;
}

export default function TimelineKeyframe({
  keyframe,
  keyframeId,
  channel,
  x,
  isSelected,
  angle,
}: TimelineKeyframeProps) {
  const { onKeyframeClick, onKeyframeStartDrag } = useTimelineContext();
  const keyframeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = keyframeRef.current;
    if (!el) return;

    const handleTouchStart = (e: TouchEvent) => {
      onKeyframeStartDrag(
        e as unknown as React.TouchEvent,
        keyframeId,
        channel
      );
    };

    el.addEventListener("touchstart", handleTouchStart, { passive: false });

    return () => {
      el.removeEventListener("touchstart", handleTouchStart);
    };
  }, [onKeyframeStartDrag, keyframeId, channel]);

  const handleClick = (e: React.MouseEvent | React.TouchEvent) => {
    e.stopPropagation();
    onKeyframeClick(keyframeId);
  };

  return (
    <div
      ref={keyframeRef}
      className={`timeline-keyframe ${isSelected ? "selected" : ""}`}
      style={{ left: `${x}px` }}
      onClick={handleClick}
      onTouchEnd={handleClick as React.TouchEventHandler<HTMLDivElement>}
      onMouseDown={(e) => onKeyframeStartDrag(e, keyframeId, channel)}
      title={`時間: ${(keyframe.time / 1000).toFixed(2)}s, 角度: ${angle.toFixed(1)}°`}
    >
      <div className="timeline-keyframe-handle" />
    </div>
  );
}
