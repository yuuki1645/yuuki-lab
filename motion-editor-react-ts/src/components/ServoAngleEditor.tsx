import { useState, useEffect } from "react";
import { CH_TO_SERVO_NAME, SERVO_TICK_VALUES } from "../constants";
import { useMotionContext } from "../contexts/MotionContext";
import GuideImage from "./GuideImage";
import "./ServoAngleEditor.css";

export default function ServoAngleEditor() {
  const {
    selectedKeyframe: keyframe,
    selectedKeyframeId: keyframeId,
    selectedChannel: channel,
    selectedServo: servo,
    handleAngleUpdate: onUpdateAngle,
    handleKeyframeDelete: onDelete,
    endKeyframeDragRef,
  } = useMotionContext();

  const [angle, setAngle] = useState(90);

  useEffect(() => {
    if (keyframe && channel !== null && keyframe.angle !== undefined) {
      setAngle(keyframe.angle);
    } else {
      setAngle(90);
    }
  }, [keyframe, channel]);

  const handlePointerDown = () => {
    endKeyframeDragRef?.current?.();
  };

  if (!keyframe || channel === null || keyframeId === null) {
    return (
      <div className="servo-angle-editor">
        <p className="servo-angle-editor-empty">キーフレームを選択してください</p>
      </div>
    );
  }

  const servoName = CH_TO_SERVO_NAME[channel] ?? "";

  const getLogicalRange = () => {
    if (servo) {
      return {
        min: servo.logical_lo,
        max: servo.logical_hi,
      };
    }
    return {
      min: -90,
      max: 90,
    };
  };

  const range = getLogicalRange();

  const getTicksForServo = (): number[] => {
    const servoType = servoName.replace(/^[RL]_/, "");
    const preferred = SERVO_TICK_VALUES[servoType];
    const min = range.min;
    const max = range.max;
    const inRange = (v: number) => v >= min && v <= max;
    const base = preferred ? preferred.filter(inRange) : [];
    const withBounds = new Set<number>([min, ...base, max]);
    return [...withBounds].sort((a, b) => a - b);
  };

  const ticks = getTicksForServo();

  const handleAngleChange = (value: string | number) => {
    const newAngle = parseFloat(String(value));
    const clampedAngle = Math.max(
      range.min,
      Math.min(range.max, newAngle)
    );
    setAngle(clampedAngle);
    onUpdateAngle(keyframe.id, clampedAngle);
  };

  return (
    <div
      className="servo-angle-editor"
      onMouseDown={handlePointerDown}
      onTouchStart={handlePointerDown}
    >
      <div className="servo-angle-editor-header">
        <h3>{servoName}</h3>
        <div className="servo-angle-editor-info">
          <span className="servo-angle-editor-keyframe-id" title={keyframeId}>
            ID: {keyframeId}
          </span>
          <span>時間: {(keyframe.time / 1000).toFixed(2)}s</span>
          {servo && (
            <span className="servo-range-info">
              範囲: {range.min}° ～ {range.max}°
            </span>
          )}
          <button
            onClick={() => {
              if (confirm("このキーフレームを削除しますか？")) {
                onDelete(keyframe.id);
              }
            }}
            className="btn-delete-keyframe"
          >
            削除
          </button>
        </div>
      </div>

      <GuideImage servoName={servoName} />

      <div className="servo-angle-editor-content">
        <label className="servo-angle-label">
          論理角: <span className="servo-angle-value">{Math.round(angle)}</span>°
        </label>

        <input
          type="range"
          min={range.min}
          max={range.max}
          step={1}
          value={angle}
          onChange={(e) => handleAngleChange(e.target.value)}
          onTouchMove={(e) => {
            handleAngleChange((e.target as HTMLInputElement).value);
          }}
          className="servo-angle-slider"
        />

        <div className="slider-ticks">
          {ticks.map((tick, index) => {
            const pct =
              range.min === range.max
                ? 0
                : ((tick - range.min) / (range.max - range.min)) * 100;
            return (
              <span
                key={index}
                className="slider-tick"
                style={{ left: `${pct}%` }}
              >
                {tick}
              </span>
            );
          })}
        </div>

        <input
          type="number"
          min={range.min}
          max={range.max}
          value={Math.round(angle)}
          onChange={(e) => handleAngleChange(e.target.value)}
          className="servo-angle-input"
        />
      </div>
    </div>
  );
}
