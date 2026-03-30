import { createContext, useContext, type RefObject } from "react";
import type { Keyframe } from "@/shared/types";

export interface TimelineContextValue {
  keyframes: Keyframe[];
  currentTime: number;
  timeToX: (time: number) => number;
  xToTime: (x: number) => number;
  TIMELINE_WIDTH: number;
  DISPLAY_DURATION: number;
  scrollableRef: RefObject<HTMLDivElement | null>;
  getClientX: (e: MouseEvent | TouchEvent | React.MouseEvent | React.TouchEvent) => number;
  isDragging: boolean;
  isPlayheadDragging: boolean;
  selectedKeyframeId: string | null;
  onTimeClick: (time: number, channel: number | null) => void;
  endKeyframeDrag: () => void;
  onKeyframeClick: (id: string) => void;
  onKeyframeStartDrag: (
    e: React.MouseEvent | React.TouchEvent,
    id: string,
    ch: number
  ) => void;
  onPlayheadDrag: (time: number) => void;
  onPlayheadDragEnd: () => void;
}

const TimelineContext = createContext<TimelineContextValue | null>(null);

export function useTimelineContext(): TimelineContextValue {
  const ctx = useContext(TimelineContext);
  if (ctx == null) {
    throw new Error("useTimelineContext must be used within Timeline");
  }
  return ctx;
}

export default TimelineContext;
