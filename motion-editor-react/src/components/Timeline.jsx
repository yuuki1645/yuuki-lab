import { useRef, useState, useMemo, useCallback, useEffect } from 'react';
import { SERVO_CHANNELS } from '../constants';
import { timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION } from '../utils/timelineCoordinates';
import { useTimelineDrag } from '../hooks/useTimelineDrag';
import { useMotionContext } from '../contexts/MotionContext';
import { usePlaybackContext } from '../contexts/PlaybackContext';
import TimelineContext from '../contexts/TimelineContext';
import TimelineLabels from './TimelineLabels';
import TimelineRuler from './TimelineRuler';
import TimelineTrack from './TimelineTrack';
import TimelinePlayheadHandle from './TimelinePlayheadHandle';
import './Timeline.css';

export default function Timeline() {
  const {
    keyframes,
    handleTimeClick,
    handleKeyframeClick,
    handleKeyframeDrag,
    selectedKeyframeId,
    endKeyframeDragRef,
  } = useMotionContext();

  const { currentTime, seekToTime } = usePlaybackContext();

  const timelineRef = useRef(null);
  const scrollableRef = useRef(null);
  const [isPlayheadDragging, setIsPlayheadDragging] = useState(false);

  const { isDragging, handleKeyframeStart, getClientX, endKeyframeDrag, dragEndedRef } =
    useTimelineDrag(scrollableRef, keyframes, handleKeyframeDrag, handleKeyframeClick);

  useEffect(() => {
    if (endKeyframeDragRef) {
      endKeyframeDragRef.current = endKeyframeDrag;
      return () => {
        endKeyframeDragRef.current = null;
      };
    }
  }, [endKeyframeDragRef, endKeyframeDrag]);

  const onKeyframeClick = useCallback(
    (id) => {
      const allowByDragEnded = dragEndedRef.current;
      if (allowByDragEnded) {
        dragEndedRef.current = false;
      }
      if ((!isDragging && !isPlayheadDragging) || allowByDragEnded) {
        handleKeyframeClick(id);
      }
    },
    [isDragging, isPlayheadDragging, handleKeyframeClick]
  );

  const handlePlayheadDrag = useCallback(
    (time) => {
      setIsPlayheadDragging(true);
      seekToTime(time);
    },
    [seekToTime]
  );

  const handlePlayheadDragEnd = useCallback(() => {
    setIsPlayheadDragging(false);
  }, []);

  const onKeyframeStartDrag = useCallback(
    (e, id, ch) => {
      handleKeyframeStart(e, id, ch, timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION);
    },
    [handleKeyframeStart, timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION]
  );

  const contextValue = useMemo(
    () => ({
      keyframes,
      currentTime,
      timeToX,
      xToTime,
      TIMELINE_WIDTH,
      DISPLAY_DURATION,
      scrollableRef,
      getClientX,
      isDragging,
      isPlayheadDragging,
      selectedKeyframeId,
      onTimeClick: handleTimeClick,
      endKeyframeDrag,
      onKeyframeClick,
      onKeyframeStartDrag,
      onPlayheadDrag: handlePlayheadDrag,
      onPlayheadDragEnd: handlePlayheadDragEnd,
    }),
    [
      keyframes,
      currentTime,
      timeToX,
      xToTime,
      TIMELINE_WIDTH,
      DISPLAY_DURATION,
      scrollableRef,
      getClientX,
      isDragging,
      isPlayheadDragging,
      selectedKeyframeId,
      handleTimeClick,
      endKeyframeDrag,
      onKeyframeClick,
      onKeyframeStartDrag,
      handlePlayheadDrag,
      handlePlayheadDragEnd,
    ]
  );

  return (
    <TimelineContext.Provider value={contextValue}>
      <div className="timeline-container" ref={timelineRef}>
        <TimelineLabels />
        <div className="timeline-scrollable" ref={scrollableRef}>
          <TimelineRuler />
          <div className="timeline-tracks">
            {SERVO_CHANNELS.map((channel) => (
              <TimelineTrack key={channel} channel={channel} />
            ))}
          </div>
          <TimelinePlayheadHandle />
        </div>
      </div>
    </TimelineContext.Provider>
  );
}