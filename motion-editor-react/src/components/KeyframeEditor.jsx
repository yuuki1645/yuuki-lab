import { useState, useEffect } from 'react';
import { SERVO_CHANNELS, CH_TO_SERVO_NAME } from '../constants';
import './KeyframeEditor.css';

export default function KeyframeEditor({ 
  keyframe, 
  keyframeIndex, 
  onUpdateAngle, 
  onDelete 
}) {
  const [angles, setAngles] = useState({});
  
  useEffect(() => {
    if (keyframe) {
      setAngles({ ...keyframe.angles });
    }
  }, [keyframe]);
  
  if (!keyframe) {
    return (
      <div className="keyframe-editor">
        <p className="keyframe-editor-empty">キーフレームを選択してください</p>
      </div>
    );
  }
  
  const handleAngleChange = (channel, value) => {
    const newAngles = { ...angles, [channel]: parseFloat(value) };
    setAngles(newAngles);
    onUpdateAngle(keyframeIndex, newAngles);
  };
  
  return (
    <div className="keyframe-editor">
      <div className="keyframe-editor-header">
        <h3>キーフレーム #{keyframeIndex + 1}</h3>
        <div className="keyframe-editor-info">
          <span>時間: {(keyframe.time / 1000).toFixed(2)}s</span>
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
      
      <div className="keyframe-editor-content">
        {SERVO_CHANNELS.map(channel => {
          const angle = angles[channel] ?? 90;
          return (
            <div key={channel} className="keyframe-editor-row">
              <label className="keyframe-editor-label">
                {CH_TO_SERVO_NAME[channel]}
              </label>
              <div className="keyframe-editor-controls">
                <input
                  type="range"
                  min="0"
                  max="180"
                  value={angle}
                  onChange={(e) => handleAngleChange(channel, e.target.value)}
                  onTouchMove={(e) => {
                    // タッチ操作でもリアルタイム更新
                    handleAngleChange(channel, e.target.value);
                  }}
                  className="keyframe-editor-slider"
                />
                <input
                  type="number"
                  min="0"
                  max="180"
                  value={Math.round(angle)}
                  onChange={(e) => handleAngleChange(channel, e.target.value)}
                  className="keyframe-editor-input"
                />
                <span className="keyframe-editor-unit">°</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}