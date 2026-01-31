import { useRef, useState } from 'react';
import { SERVO_CHANNELS } from '../constants';
import { useTimelineCoordinates } from '../hooks/useTimelineCoordinates';
import { useTimelineDrag } from '../hooks/useTimelineDrag';
import TimelineLabels from './TimelineLabels';
import TimelineRuler from './TimelineRuler';
import TimelineTrack from './TimelineTrack';
import './Timeline.css';

export default function Timeline({ 
  keyframes, 
  currentTime, 
  onTimeClick, 
  onKeyframeClick,
  onKeyframeDrag,
  selectedKeyframeIndex,
  selectedChannel,
  onPlayheadDrag,
}) {
  const timelineRef = useRef(null);
  const scrollableRef = useRef(null);
  const [isPlayheadDragging, setIsPlayheadDragging] = useState(false);
  
  const { timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION } = useTimelineCoordinates();
  const { isDragging, handleKeyframeStart, getClientX } = useTimelineDrag(
    scrollableRef,
    keyframes,
    onKeyframeDrag
  );
  
  const handleKeyframeClick = (index, channel) => {
    if (!isDragging && !isPlayheadDragging) {
      onKeyframeClick(index, channel);
    }
  };
  
  const handlePlayheadDrag = (time) => {
    setIsPlayheadDragging(true);
    onPlayheadDrag(time);
  };
  
  const handlePlayheadDragEnd = () => {
    setIsPlayheadDragging(false);
  };
  
  return (
    <div className="timeline-container" ref={timelineRef}>
      <TimelineLabels keyframes={keyframes} currentTime={currentTime} />
      <div className="timeline-scrollable" ref={scrollableRef}>
        <div>
          <TimelineRuler
            timeToX={timeToX}
            currentTime={currentTime}
            xToTime={xToTime}
            scrollableRef={scrollableRef}
            getClientX={getClientX}
            onPlayheadDrag={handlePlayheadDrag}
            onPlayheadDragEnd={handlePlayheadDragEnd}
            isPlayheadDragging={isPlayheadDragging}
          />
        </div>
        <div className="timeline-tracks">
          {SERVO_CHANNELS.map(channel => (
            <TimelineTrack
              key={channel}
              channel={channel}
              keyframes={keyframes}
              currentTime={currentTime}
              selectedKeyframeIndex={selectedKeyframeIndex}
              selectedChannel={selectedChannel}
              timeToX={timeToX}
              xToTime={xToTime}
              onTimeClick={onTimeClick}
              onKeyframeClick={handleKeyframeClick}
              onKeyframeStartDrag={(e, index, ch) => {
                console.log(`onKeyframeStartDrag: index=${index}, channel=${ch}`);
                handleKeyframeStart(e, index, ch, timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION)
              }}
              getClientX={getClientX}
              scrollableRef={scrollableRef}
              isDragging={isDragging}
              isPlayheadDragging={isPlayheadDragging}
            />
          ))}
        </div>
        {/* 下側のドラッグ用ハンドル（L_HEELの下） */}
        <div className="timeline-playhead-handle-container">
          <div
            className={`timeline-playhead-handle ${isPlayheadDragging ? 'dragging' : ''}`}
            style={{ left: `${timeToX(currentTime)}px` }}
            onMouseDown={(e) => {
              e.stopPropagation();
              e.preventDefault();
              if (!scrollableRef.current) return;
              const rect = scrollableRef.current.getBoundingClientRect();
              
              const handleMove = (e) => {
                e.preventDefault();
                const clientX = getClientX(e);
                const x = clientX - rect.left;
                const HANDLE_CENTER_OFFSET_PX = 20;
                const playheadLeft = x - HANDLE_CENTER_OFFSET_PX;
                const newTime = xToTime(Math.max(0, playheadLeft));
                handlePlayheadDrag(newTime);
              };
              
              const handleEnd = () => {
                document.removeEventListener('mousemove', handleMove);
                document.removeEventListener('mouseup', handleEnd);
                document.removeEventListener('touchmove', handleMove);
                document.removeEventListener('touchend', handleEnd);
                handlePlayheadDragEnd();
              };
              
              document.addEventListener('mousemove', handleMove);
              document.addEventListener('mouseup', handleEnd);
              document.addEventListener('touchmove', handleMove, { passive: false });
              document.addEventListener('touchend', handleEnd);
            }}
            onTouchStart={(e) => {
              e.stopPropagation();
              e.preventDefault();
              if (!scrollableRef.current) return;
              const rect = scrollableRef.current.getBoundingClientRect();
              
              const handleMove = (e) => {
                e.preventDefault();
                const clientX = getClientX(e);
                const x = clientX - rect.left;
                const HANDLE_CENTER_OFFSET_PX = 20;
                const playheadLeft = x - HANDLE_CENTER_OFFSET_PX;
                const newTime = xToTime(Math.max(0, playheadLeft));
                handlePlayheadDrag(newTime);
              };
              
              const handleEnd = () => {
                document.removeEventListener('mousemove', handleMove);
                document.removeEventListener('mouseup', handleEnd);
                document.removeEventListener('touchmove', handleMove);
                document.removeEventListener('touchend', handleEnd);
                handlePlayheadDragEnd();
              };
              
              document.addEventListener('mousemove', handleMove);
              document.addEventListener('mouseup', handleEnd);
              document.addEventListener('touchmove', handleMove, { passive: false });
              document.addEventListener('touchend', handleEnd);
            }}
          />
        </div>
      </div>
    </div>
  );
}