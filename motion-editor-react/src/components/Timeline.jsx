import { useRef, useEffect, useState } from 'react';
import { SERVO_CHANNELS, CH_TO_SERVO_NAME } from '../constants';
import './Timeline.css';

export default function Timeline({ 
  keyframes, 
  duration, 
  currentTime, 
  onTimeClick, 
  onKeyframeClick,
  onKeyframeDrag,
  selectedKeyframeIndex 
}) {
  const timelineRef = useRef(null);
  const keyframeRefs = useRef({});
  const dragStateRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  
  // 時間をピクセル位置に変換
  const timeToX = (time) => {
    if (!timelineRef.current || duration === 0) return 0;
    const width = timelineRef.current.offsetWidth - 100; // 左側のラベル分を引く
    return (time / duration) * width;
  };
  
  // ピクセル位置を時間に変換
  const xToTime = (x) => {
    if (!timelineRef.current || duration === 0) return 0;
    const width = timelineRef.current.offsetWidth - 100;
    return Math.max(0, Math.min(duration, (x / width) * duration));
  };
  
  // 共通の座標取得関数（マウスとタッチの両方に対応）
  const getClientX = (e) => {
    if (e.touches && e.touches.length > 0) {
      return e.touches[0].clientX;
    }
    if (e.changedTouches && e.changedTouches.length > 0) {
      return e.changedTouches[0].clientX;
    }
    return e.clientX;
  };
  
  const handleTimelineClick = (e) => {
    // ドラッグ中は無視
    if (isDragging) {
      return;
    }
    
    // キーフレームやラベルをクリックした場合は無視
    if (
      e.target.closest('.timeline-keyframe') ||
      e.target.closest('.timeline-track-label')
    ) {
      return;
    }
    
    // timeline-track-content または timeline-track をクリックした場合
    const trackContent = e.target.closest('.timeline-track-content');
    if (trackContent || e.target.classList.contains('timeline-track')) {
      const rect = timelineRef.current.getBoundingClientRect();
      const clientX = getClientX(e);
      const x = clientX - rect.left - 100; // 左側のラベル分を引く
      const time = xToTime(x);
      onTimeClick(time);
    }
  };
  
  // キーフレームのドラッグ開始（マウスとタッチの両方）
  const handleKeyframeStart = (e, keyframeIndex, channel) => {
    e.stopPropagation();
    e.preventDefault();
    
    const rect = timelineRef.current.getBoundingClientRect();
    const clientX = getClientX(e);
    const startX = clientX - rect.left - 100; // タイムライン内の相対位置
    const startTime = keyframes[keyframeIndex].time;
    
    dragStateRef.current = {
      keyframeIndex,
      channel,
      startX: startX, // タイムライン内の相対位置を保存
      startTime,
      rectLeft: rect.left, // タイムラインの左端位置を保存
    };
    
    setIsDragging(true);
    
    const handleMove = (e) => {
      if (!dragStateRef.current) return;
      
      e.preventDefault(); // スクロールを防ぐ
      
      const currentClientX = getClientX(e);
      const currentX = currentClientX - dragStateRef.current.rectLeft - 100; // タイムライン内の相対位置
      
      // ピクセル移動量を時間に変換
      const width = timelineRef.current.offsetWidth - 100;
      if (width === 0 || duration === 0) return;
      
      const deltaX = currentX - dragStateRef.current.startX;
      const deltaTime = (deltaX / width) * duration;
      const newTime = Math.max(0, Math.min(duration, dragStateRef.current.startTime + deltaTime));
      
      onKeyframeDrag(dragStateRef.current.keyframeIndex, newTime);
    };
    
    const handleEnd = () => {
      dragStateRef.current = null;
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleEnd);
      document.removeEventListener('touchmove', handleMove);
      document.removeEventListener('touchend', handleEnd);
    };
    
    // マウスイベント
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleEnd);
    
    // タッチイベント
    document.addEventListener('touchmove', handleMove, { passive: false });
    document.addEventListener('touchend', handleEnd);
  };
  
  // キーフレームのクリック/タップ（ドラッグでない場合）
  const handleKeyframeClick = (e, index) => {
    // ドラッグが発生していない場合のみ選択
    if (!isDragging && dragStateRef.current === null) {
      e.stopPropagation();
      onKeyframeClick(index);
    }
  };
  
  // 時間マーカーの生成
  const timeMarkers = [];
  const markerCount = 10;
  for (let i = 0; i <= markerCount; i++) {
    const time = (duration / markerCount) * i;
    timeMarkers.push(time);
  }
  
  return (
    <div className="timeline-container" ref={timelineRef}>
      <div className="timeline-header">
        <div className="timeline-label">時間</div>
        <div className="timeline-ruler">
          {timeMarkers.map((time, i) => (
            <div 
              key={i} 
              className="timeline-marker"
              style={{ left: `${100 + timeToX(time)}px` }}
            >
              <div className="timeline-marker-line" />
              <div className="timeline-marker-label">
                {(time / 1000).toFixed(1)}s
              </div>
            </div>
          ))}
        </div>
      </div>
      
      <div className="timeline-tracks">
        {SERVO_CHANNELS.map(channel => (
          <div 
            key={channel} 
            className="timeline-track"
            onClick={handleTimelineClick}
            onTouchEnd={handleTimelineClick}
          >
            <div className="timeline-track-label">
              {CH_TO_SERVO_NAME[channel]}
            </div>
            <div 
              className="timeline-track-content"
              onClick={handleTimelineClick}
              onTouchEnd={handleTimelineClick}
            >
              {/* 再生位置インジケーター */}
              <div 
                className="timeline-playhead"
                style={{ left: `${timeToX(currentTime)}px` }}
              />
              
              {/* キーフレーム */}
              {keyframes.map((keyframe, index) => {
                const x = timeToX(keyframe.time);
                const isSelected = selectedKeyframeIndex === index;
                const angle = keyframe.angles[channel] ?? 90;
                
                return (
                  <div
                    key={`${channel}-${index}`}
                    ref={el => {
                      if (el) {
                        keyframeRefs.current[`${channel}-${index}`] = el;
                      }
                    }}
                    className={`timeline-keyframe ${isSelected ? 'selected' : ''}`}
                    style={{ left: `${x}px` }}
                    onClick={(e) => handleKeyframeClick(e, index)}
                    onTouchEnd={(e) => handleKeyframeClick(e, index)}
                    onMouseDown={(e) => handleKeyframeStart(e, index, channel)}
                    onTouchStart={(e) => handleKeyframeStart(e, index, channel)}
                    title={`時間: ${(keyframe.time / 1000).toFixed(2)}s, 角度: ${angle.toFixed(1)}°`}
                  >
                    <div className="timeline-keyframe-handle" />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}