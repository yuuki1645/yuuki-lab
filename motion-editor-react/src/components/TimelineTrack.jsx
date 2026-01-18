import TimelineKeyframe from './TimelineKeyframe';
import './Timeline.css';

export default function TimelineTrack({
  channel,
  keyframes,
  currentTime,
  selectedKeyframeIndex,
  selectedChannel,
  timeToX,
  onTimeClick,
  onKeyframeClick,
  onKeyframeStartDrag,
  getClientX,
  xToTime,
  scrollableRef,
  isDragging,
  onPlayheadDrag,  // 追加
  isPlayheadDragging,  // 追加
}) {
  const handleTrackClick = (e) => {
    if (isDragging || isPlayheadDragging) return;  // プレイヘッドドラッグ中も除外
    
    if (
      e.target.closest('.timeline-keyframe') ||
      e.target.closest('.timeline-track-label') ||
      e.target.closest('.timeline-playhead')  // プレイヘッドクリックも除外
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
  
  // プレイヘッドのドラッグ開始
  const handlePlayheadMouseDown = (e) => {
    e.stopPropagation();
    e.preventDefault();  // タッチデバイスでのスクロールを防ぐ
    if (!scrollableRef.current) return;
    
    const rect = scrollableRef.current.getBoundingClientRect();
    
    const handleMove = (e) => {
      e.preventDefault();  // タッチデバイスでのスクロールを防ぐ
      const clientX = getClientX(e);
      const x = clientX - rect.left;
      const newTime = xToTime(x);
      onPlayheadDrag(newTime);
    };
    
    const handleEnd = () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleEnd);
      document.removeEventListener('touchmove', handleMove);
      document.removeEventListener('touchend', handleEnd);
    };
    
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleEnd);
    document.addEventListener('touchmove', handleMove, { passive: false });
    document.addEventListener('touchend', handleEnd);
    
    // 最初の位置でも更新
    const startX = getClientX(e);
    const x = startX - rect.left;
    const startTime = xToTime(x);
    onPlayheadDrag(startTime);
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
          className={`timeline-playhead ${isPlayheadDragging ? 'dragging' : ''}`}
          style={{ left: `${timeToX(currentTime)}px` }}
          onMouseDown={handlePlayheadMouseDown}
          onTouchStart={handlePlayheadMouseDown}
        />
        
        {/* キーフレーム */}
        {keyframes.map((keyframe, index) => {
          // このチャンネルにキーフレームが存在するかチェック
          if (keyframe.angles[channel] === undefined) {
            return null;
          }
          
          const x = timeToX(keyframe.time);
          const isSelected = selectedKeyframeIndex === index && selectedChannel === channel;
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
              onClick={onKeyframeClick}
              onStartDrag={onKeyframeStartDrag}
            />
          );
        })}
      </div>
    </div>
  );
}