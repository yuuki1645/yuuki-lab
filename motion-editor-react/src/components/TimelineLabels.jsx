import { SERVO_CHANNELS, CH_TO_SERVO_NAME } from '../constants';
import './Timeline.css';

export default function TimelineLabels() {
  return (
    <div className="timeline-labels">
      <div className="timeline-label">時間</div>
      {SERVO_CHANNELS.map(channel => (
        <div key={channel} className="timeline-track-label">
          {CH_TO_SERVO_NAME[channel]}
        </div>
      ))}
    </div>
  );
}