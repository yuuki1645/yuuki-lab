import { useRef, useState } from "react";
import { MAX_MOTION_DURATION } from "@/shared/constants";
import type { Keyframe } from "@/shared/types";

const DRAG_THRESHOLD_PX = 5;

function getClientXNative(e: MouseEvent | TouchEvent): number {
  const ev = e as TouchEvent & MouseEvent;
  if (ev.touches && ev.touches.length > 0) {
    return ev.touches[0]!.clientX;
  }
  if (ev.changedTouches && ev.changedTouches.length > 0) {
    return ev.changedTouches[0]!.clientX;
  }
  return ev.clientX;
}

function getClientX(
  e: MouseEvent | TouchEvent | React.MouseEvent | React.TouchEvent
): number {
  const ev =
    "nativeEvent" in e
      ? (e as React.MouseEvent | React.TouchEvent).nativeEvent
      : (e as MouseEvent | TouchEvent);
  return getClientXNative(ev);
}

interface DragListeners {
  handleMove: (e: MouseEvent | TouchEvent) => void;
  handleEnd: () => void;
}

export function useTimelineDrag(
  scrollableRef: React.RefObject<HTMLDivElement | null>,
  keyframes: Keyframe[],
  onKeyframeDrag: (id: string, newTime: number) => void,
  onKeyframeClick: (id: string) => void
) {
  const dragStateRef = useRef<{
    keyframeId: string;
    channel: number;
    startX: number;
    startTime: number;
    rectLeft: number;
    dragCommitted: boolean;
  } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragEndedRef = useRef(false);

  const onKeyframeDragRef = useRef(onKeyframeDrag);
  onKeyframeDragRef.current = onKeyframeDrag;

  const onKeyframeClickRef = useRef(onKeyframeClick);
  onKeyframeClickRef.current = onKeyframeClick;

  const listenersRef = useRef<DragListeners | null>(null);

  const removeListeners = (
    handleMove: (e: MouseEvent | TouchEvent) => void,
    handleEnd: () => void
  ) => {
    document.removeEventListener("mousemove", handleMove as EventListener);
    document.removeEventListener("mouseup", handleEnd);
    document.removeEventListener("touchmove", handleMove as EventListener);
    document.removeEventListener("touchend", handleEnd);
    document.removeEventListener("touchcancel", handleEnd);
    listenersRef.current = null;
  };

  const handleKeyframeStart = (
    e: React.MouseEvent | React.TouchEvent,
    keyframeId: string,
    channel: number,
    _timeToX: (time: number) => number,
    _xToTime: (x: number) => number,
    timelineWidth: number,
    displayDuration: number
  ) => {
    e.stopPropagation();
    e.preventDefault();

    if (listenersRef.current) {
      const { handleMove: oldMove, handleEnd: oldEnd } = listenersRef.current;
      removeListeners(oldMove, oldEnd);
      dragStateRef.current = null;
      setIsDragging(false);
    }

    if (!scrollableRef.current) return;
    const kf = keyframes.find((k) => k.id === keyframeId);
    if (!kf) return;

    const rect = scrollableRef.current.getBoundingClientRect();
    const clientX = getClientX(e);
    const startX = clientX - rect.left;
    const startTime = kf.time;

    dragStateRef.current = {
      keyframeId,
      channel,
      startX,
      startTime,
      rectLeft: rect.left,
      dragCommitted: false,
    };

    const handleMove = (ev: MouseEvent | TouchEvent) => {
      if (!dragStateRef.current || !scrollableRef.current) return;

      (ev as Event).preventDefault();

      const currentClientX = getClientXNative(ev);
      const rect2 = scrollableRef.current.getBoundingClientRect();
      const currentX = currentClientX - rect2.left;
      const deltaX = currentX - dragStateRef.current.startX;

      if (!dragStateRef.current.dragCommitted) {
        if (Math.abs(deltaX) >= DRAG_THRESHOLD_PX) {
          dragStateRef.current.dragCommitted = true;
          setIsDragging(true);
        } else {
          return;
        }
      }

      const deltaTime = (deltaX / timelineWidth) * displayDuration;
      const newTime = Math.max(
        0,
        Math.min(
          MAX_MOTION_DURATION,
          dragStateRef.current.startTime + deltaTime
        )
      );

      onKeyframeDragRef.current(dragStateRef.current.keyframeId, newTime);
    };

    const handleEnd = () => {
      const keyframeId = dragStateRef.current?.keyframeId;
      const committed = dragStateRef.current?.dragCommitted;

      dragStateRef.current = null;
      setIsDragging(false);
      removeListeners(handleMove, handleEnd);

      if (committed) {
        dragEndedRef.current = true;
        setTimeout(() => {
          dragEndedRef.current = false;
        }, 0);
      }

      if (!committed && keyframeId != null) {
        const idToSelect = keyframeId;
        setTimeout(() => {
          onKeyframeClickRef.current?.(idToSelect);
        }, 0);
      }
    };

    listenersRef.current = { handleMove, handleEnd };

    document.addEventListener("mousemove", handleMove as EventListener);
    document.addEventListener("mouseup", handleEnd);
    document.addEventListener("touchmove", handleMove as EventListener, {
      passive: false,
    });
    document.addEventListener("touchend", handleEnd);
    document.addEventListener("touchcancel", handleEnd);
  };

  const endKeyframeDrag = () => {
    if (!listenersRef.current) return;
    const { handleMove, handleEnd } = listenersRef.current;
    dragStateRef.current = null;
    setIsDragging(false);
    removeListeners(handleMove, handleEnd);
  };

  return {
    isDragging,
    handleKeyframeStart,
    getClientX,
    endKeyframeDrag,
    dragEndedRef,
  };
}
