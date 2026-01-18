import { MAX_MOTION_DURATION } from '../constants';
import './Timeline.css';

export default function TimelineRuler({ timeToX }) {
  const displayDuration = MAX_MOTION_DURATION;
  const markerCount = 20;
  
  // 時間マーカーの生成
  const timeMarkers = [];
  for (let i = 0; i <= markerCount; i++) {
    const time = (displayDuration / markerCount) * i;
    timeMarkers.push(time);
  }
  
  return (
    <div className="timeline-header">
      <div className="timeline-ruler">
        {timeMarkers.map((time, i) => (
          <div 
            key={i} 
            className="timeline-marker"
            style={{ left: `${timeToX(time)}px` }}
          >
            <div className="timeline-marker-line" />
            <div className="timeline-marker-label">
              {(time / 1000).toFixed(1)}s
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}