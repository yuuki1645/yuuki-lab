import TimelineKeyframe from './TimelineKeyframe';
import './Timeline.css';

export default function TimelineTrack({
  channel,
  keyframes,
  currentTime,
  selectedKeyframeIndex,
  timeToX,
  onTimeClick,
  onKeyframeClick,
  onKeyframeStartDrag,
  getClientX,
  xToTime,
  scrollableRef,
  isDragging,
}) {
  const handleTrackClick = (e) => {
    if (isDragging) return;
    
    if (
      e.target.closest('.timeline-keyframe') ||
      e.target.closest('.timeline-track-label')
    ) {
      return;
    }
    
    const trackContent = e.target.closest('.timeline-track-content');
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
        {/* 再生位置インジケーター */}
        <div 
          className="timeline-playhead"
          style={{ left: `${timeToX(currentTime)}px` }}
        />
        
        {/* キーフレーム */}
        {keyframes.map((keyframe, index) => {
          // このチャンネルにキーフレームが存在するかチェック
          if (keyframe.angles[channel] === undefined) {
            return null;
          }
          
          const x = timeToX(keyframe.time);
          const isSelected = selectedKeyframeIndex === index;
          const angle = keyframe.angles[channel] ?? 90;
          
          return (
            <TimelineKeyframe
              key={`${channel}-${index}`}
              keyframe={keyframe}
              keyframeIndex={index}
              channel={channel}
              x={x}
              isSelected={isSelected}
              angle={angle}
              onClick={(e) => {
                e.stopPropagation();
                onKeyframeClick(index);
              }}
              onStartDrag={onKeyframeStartDrag}
            />
          );
        })}
      </div>
    </div>
  );
}