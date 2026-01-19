import { useRef, useState } from 'react';
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
  selectedKeyframeIndex,
  selectedChannel,
  onPlayheadDrag,  // 追加
}) {
  const timelineRef = useRef(null);
  const scrollableRef = useRef(null);
  const [isPlayheadDragging, setIsPlayheadDragging] = useState(false);  // 追加
  
  const { timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION } = useTimelineCoordinates();
  const { isDragging, handleKeyframeStart, getClientX } = useTimelineDrag(
    scrollableRef,
    keyframes,
    onKeyframeDrag
  );
  
  const handleKeyframeClick = (index, channel) => {
    if (!isDragging && !isPlayheadDragging) {  // プレイヘッドドラッグ中も除外
      onKeyframeClick(index, channel);
    }
  };
  
  const handleRulerClick = (e) => {
    if (isDragging || isPlayheadDragging) return;  // プレイヘッドドラッグ中も除外
    
    if (e.target.closest('.timeline-marker')) return;
    
    if (!scrollableRef.current) return;
    const rect = scrollableRef.current.getBoundingClientRect();
    const clientX = getClientX(e);
    const x = clientX - rect.left;
    const time = xToTime(x);
    onTimeClick(time, null);
  };
  
  // プレイヘッドドラッグハンドラ
  const handlePlayheadDrag = (time) => {
    setIsPlayheadDragging(true);
    onPlayheadDrag(time);
  };
  
  // ドラッグ終了を検知するためのコールバック
  const handlePlayheadDragEnd = () => {
    setIsPlayheadDragging(false);
  };
  
  // ドラッグ終了を検知（マウス/タッチイベントのクリーンアップ時に呼ばれる）
  // これは少し工夫が必要。TimelineTrackから直接呼べないので、
  // グローバルイベントリスナーで検知するか、別の方法を使う
  // とりあえず、マウス/タッチイベントが終了したら自動的にfalseになるようにする
  
  return (
    <div className="timeline-container" ref={timelineRef}>
      {/* ... existing code ... */}
      <div className="timeline-scrollable" ref={scrollableRef}>
        {/* ... existing code ... */}
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
              onKeyframeStartDrag={(e, index, ch) => 
                handleKeyframeStart(e, index, ch, timeToX, xToTime, TIMELINE_WIDTH, DISPLAY_DURATION)
              }
              getClientX={getClientX}
              scrollableRef={scrollableRef}
              isDragging={isDragging}
              onPlayheadDrag={handlePlayheadDrag}
              onPlayheadDragEnd={handlePlayheadDragEnd}  // 追加
              isPlayheadDragging={isPlayheadDragging}
            />
          ))}
        </div>
      </div>
    </div>
  );
}