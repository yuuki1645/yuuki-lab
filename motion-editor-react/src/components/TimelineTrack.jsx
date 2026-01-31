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
  isPlayheadDragging,
}) {
  // console.log("keyframes", keyframes);
  console.log("TimelineTrack rendered");
  console.log(`selectedKeyframeIndex=${selectedKeyframeIndex}, selectedChannel=${selectedChannel}`);

  const handleTrackClick = (e) => {
    if (isDragging || isPlayheadDragging) return;
    if (
      e.target.closest('.timeline-keyframe') ||
      e.target.closest('.timeline-track-label') ||
      e.target.closest('.timeline-playhead')
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
        <div
          className={`timeline-playhead ${isPlayheadDragging ? 'dragging' : ''}`}
          style={{ left: `${timeToX(currentTime)}px` }}
        />
        {keyframes.map((kf, index) => {
          if (kf.channel !== channel) return null;
          const x = timeToX(kf.time);
          const isSelected = selectedKeyframeIndex === index && selectedChannel === channel;
          return (
            <TimelineKeyframe
              key={`${channel}-${index}`}
              keyframe={kf}
              keyframeIndex={index}
              channel={channel}
              x={x}
              isSelected={isSelected}
              angle={kf.angle ?? 90}
              onClick={onKeyframeClick}
              onStartDrag={onKeyframeStartDrag}
            />
          );
        })}
      </div>
    </div>
  );
}