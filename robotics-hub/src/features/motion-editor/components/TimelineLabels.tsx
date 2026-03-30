import { SERVO_CHANNELS, CH_TO_SERVO_NAME } from "@/shared/constants";
import { getAngleAtTime } from "../utils/interpolation";
import { useTimelineContext } from "../contexts/TimelineContext";
import "./Timeline.css";

export default function TimelineLabels() {
  const { keyframes, currentTime } = useTimelineContext();

  const currentAngles = getAngleAtTime(
    keyframes ?? [],
    currentTime ?? 0,
    SERVO_CHANNELS
  );

  return (
    <div className="timeline-labels">
      <div className="timeline-label">時間</div>
      {SERVO_CHANNELS.map((channel) => {
        const servoName = CH_TO_SERVO_NAME[channel];
        const angle = currentAngles[channel];
        const displayAngle =
          angle !== undefined ? Math.round(angle) : "--";

        return (
          <div key={channel} className="timeline-track-label">
            <div className="timeline-track-label-name">{servoName}</div>
            <div className="timeline-track-label-angle">
              {displayAngle}°
            </div>
          </div>
        );
      })}
    </div>
  );
}
