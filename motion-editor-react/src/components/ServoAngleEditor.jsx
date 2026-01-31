import { useState, useEffect } from 'react';
import { CH_TO_SERVO_NAME } from '../constants';
import GuideImage from './GuideImage';
import './ServoAngleEditor.css';

export default function ServoAngleEditor({
  keyframe,
  keyframeIndex,
  channel,
  servo,
  onUpdateAngle,
  onDelete
}) {
  const [angle, setAngle] = useState(90);

  useEffect(() => {
    if (keyframe && channel !== null && keyframe.angle !== undefined) {
      setAngle(keyframe.angle);
    } else {
      setAngle(90);
    }
  }, [keyframe, channel]);

  if (!keyframe || channel === null) {
    return (
      <div className="servo-angle-editor">
        <p className="servo-angle-editor-empty">キーフレームを選択してください</p>
      </div>
    );
  }

  const servoName = CH_TO_SERVO_NAME[channel];

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

  const generateTicks = (min, max, divisions = 5) => {
    const ticks = [];
    for (let i = 0; i <= divisions; i++) {
      const value = min + (max - min) * (i / divisions);
      ticks.push(Math.round(value));
    }
    return ticks;
  };

  const ticks = generateTicks(range.min, range.max, 5);

  const handleAngleChange = (value) => {
    const newAngle = parseFloat(value);
    const clampedAngle = Math.max(range.min, Math.min(range.max, newAngle));
    setAngle(clampedAngle);
    onUpdateAngle(keyframeIndex, clampedAngle);
  };

  return (
    <div className="servo-angle-editor">
      <div className="servo-angle-editor-header">
        <h3>{servoName}</h3>
        <div className="servo-angle-editor-info">
          <span>キーフレーム #{keyframeIndex + 1}</span>
          <span>時間: {(keyframe.time / 1000).toFixed(2)}s</span>
          {servo && (
            <span className="servo-range-info">
              範囲: {range.min}° ～ {range.max}°
            </span>
          )}
          <button
            onClick={() => {
              if (confirm('このキーフレームを削除しますか？')) {
                onDelete(keyframeIndex);
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
            handleAngleChange(e.target.value);
          }}
          className="servo-angle-slider"
        />

        <div className="slider-ticks">
          {ticks.map((tick, index) => (
            <span key={index}>{tick}</span>
          ))}
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