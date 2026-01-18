import './Timeline.css';

export default function TimelineKeyframe({
  keyframe,
  keyframeIndex,
  channel,
  x,
  isSelected,
  angle,
  onClick,
  onStartDrag,
}) {
  return (
    <div
      className={`timeline-keyframe ${isSelected ? 'selected' : ''}`}
      style={{ left: `${x}px` }}
      onClick={onClick}
      onTouchEnd={onClick}
      onMouseDown={(e) => onStartDrag(e, keyframeIndex, channel)}
      onTouchStart={(e) => onStartDrag(e, keyframeIndex, channel)}
      title={`時間: ${(keyframe.time / 1000).toFixed(2)}s, 角度: ${angle.toFixed(1)}°`}
    >
      <div className="timeline-keyframe-handle" />
    </div>
  );
}