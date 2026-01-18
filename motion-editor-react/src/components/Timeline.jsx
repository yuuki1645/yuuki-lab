import { useRef } from 'react';
import { SERVO_CHANNELS, MAX_MOTION_DURATION } from '../constants';
import { useTimelineCoordinates } from '../hooks/useTimelineCoordinates';
import { useTimelineDrag } from '../hooks/useTimelineDrag';
import TimelineLabels from './TimelineLabels';
import TimelineRuler from './TimelineRuler';
import TimelineTrack from './TimelineTrack';
import './Timeline.css';

export default function Timeline({ 
  keyframes, 
  duration, 
  currentTime, 
  onTimeClick, 
  onKeyframeClick,
  onKeyframeDrag,
  selectedKeyframeIndex 
}) {
  const timelineRef = useRef(null);
  const scrollableRef = useRef(null);
  
  const { timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION } = useTimelineCoordinates();
  const { isDragging, handleKeyframeStart, getClientX } = useTimelineDrag(
    scrollableRef,
    keyframes,
    onKeyframeDrag
  );
  
  const handleKeyframeClick = (index) => {
    if (!isDragging) {
      onKeyframeClick(index);
    }
  };
  
  const handleRulerClick = (e) => {
    if (isDragging) return;
    
    if (e.target.closest('.timeline-marker')) return;
    
    if (!scrollableRef.current) return;
    const rect = scrollableRef.current.getBoundingClientRect();
    const clientX = getClientX(e);
    const x = clientX - rect.left;
    const time = xToTime(x);
    onTimeClick(time, null); // 全チャンネル
  };
  
  return (
    <div className="timeline-container" ref={timelineRef}>
      {/* 左側：固定ラベルエリア */}
      <TimelineLabels />
      
      {/* 右側：スクロール可能なタイムラインエリア */}
      <div className="timeline-scrollable" ref={scrollableRef}>
        {/* ヘッダー：時間ルーラー */}
        <div onClick={handleRulerClick} onTouchEnd={handleRulerClick}>
          <TimelineRuler timeToX={timeToX} />
        </div>
        
        {/* トラック：キーフレーム */}
        <div className="timeline-tracks">
          {SERVO_CHANNELS.map(channel => (
            <TimelineTrack
              key={channel}
              channel={channel}
              keyframes={keyframes}
              currentTime={currentTime}
              selectedKeyframeIndex={selectedKeyframeIndex}
              timeToX={timeToX}
              xToTime={xToTime}
              onTimeClick={onTimeClick}
              onKeyframeClick={handleKeyframeClick}
              onKeyframeStartDrag={(e, index, ch) => 
                handleKeyframeStart(e, index, ch, timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION)
              }
              getClientX={getClientX}
              scrollableRef={scrollableRef}
              isDragging={isDragging}
            />
          ))}
        </div>
      </div>
    </div>
  );
}