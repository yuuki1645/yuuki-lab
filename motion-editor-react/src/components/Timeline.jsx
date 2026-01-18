import { useRef, useEffect, useState } from 'react';
import { SERVO_CHANNELS, CH_TO_SERVO_NAME, MAX_MOTION_DURATION } from '../constants';
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
  const scrollableRef = useRef(null);
  const keyframeRefs = useRef({});
  const dragStateRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  
  // タイムラインの表示範囲は常に20秒（MAX_MOTION_DURATION）に固定
  const displayDuration = MAX_MOTION_DURATION;
  const TIMELINE_WIDTH = 6000; // タイムラインの実際の幅（1秒=300px、20秒=6000px）
  const LABEL_WIDTH = 100; // ラベルの幅
  
  // 時間をピクセル位置に変換（ラベルを除いたトラック部分での位置）
  const timeToX = (time) => {
    if (displayDuration === 0) return 0;
    const width = TIMELINE_WIDTH; // ラベルを除いた幅
    return (time / displayDuration) * width;
  };
  
  // ピクセル位置を時間に変換（トラック部分の相対位置）
  const xToTime = (x) => {
    if (displayDuration === 0) return 0;
    const width = TIMELINE_WIDTH;
    return Math.max(0, Math.min(MAX_MOTION_DURATION, (x / width) * displayDuration));
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
      e.target.closest('.timeline-label') ||
      e.target.closest('.timeline-track-label')
    ) {
      return;
    }
    
    // スクロール可能なトラック部分をクリックした場合
    const trackContent = e.target.closest('.timeline-track-content');
    const ruler = e.target.closest('.timeline-ruler');
    if (trackContent || ruler) {
      if (!scrollableRef.current) return;
      const rect = scrollableRef.current.getBoundingClientRect();
      const clientX = getClientX(e);
      const x = clientX - rect.left; // スクロール可能エリア内の相対位置
      const time = xToTime(x);
      onTimeClick(time);
    }
  };
  
  // キーフレームのドラッグ開始（マウスとタッチの両方）
  const handleKeyframeStart = (e, keyframeIndex, channel) => {
    e.stopPropagation();
    e.preventDefault();
    
    if (!scrollableRef.current) return;
    const rect = scrollableRef.current.getBoundingClientRect();
    const clientX = getClientX(e);
    const startX = clientX - rect.left; // スクロール可能エリア内の相対位置
    const startTime = keyframes[keyframeIndex].time;
    
    dragStateRef.current = {
      keyframeIndex,
      channel,
      startX: startX,
      startTime,
      rectLeft: rect.left,
    };
    
    setIsDragging(true);
    
    const handleMove = (e) => {
      if (!dragStateRef.current || !scrollableRef.current) return;
      
      e.preventDefault();
      
      const currentClientX = getClientX(e);
      const rect = scrollableRef.current.getBoundingClientRect();
      const currentX = currentClientX - rect.left;
      
      const deltaX = currentX - dragStateRef.current.startX;
      const deltaTime = (deltaX / TIMELINE_WIDTH) * displayDuration;
      const newTime = Math.max(0, Math.min(MAX_MOTION_DURATION, dragStateRef.current.startTime + deltaTime));
      
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
    
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleEnd);
    document.addEventListener('touchmove', handleMove, { passive: false });
    document.addEventListener('touchend', handleEnd);
  };
  
  // キーフレームのクリック/タップ（ドラッグでない場合）
  const handleKeyframeClick = (e, index) => {
    if (!isDragging && dragStateRef.current === null) {
      e.stopPropagation();
      onKeyframeClick(index);
    }
  };
  
  // 時間マーカーの生成（20秒まで）
  const timeMarkers = [];
  const markerCount = 20;
  for (let i = 0; i <= markerCount; i++) {
    const time = (displayDuration / markerCount) * i;
    timeMarkers.push(time);
  }
  
  return (
    <div className="timeline-container" ref={timelineRef}>
      {/* 左側：固定ラベルエリア */}
      <div className="timeline-labels">
        <div className="timeline-label">時間</div>
        {SERVO_CHANNELS.map(channel => (
          <div key={channel} className="timeline-track-label">
            {CH_TO_SERVO_NAME[channel]}
          </div>
        ))}
      </div>
      
      {/* 右側：スクロール可能なタイムラインエリア */}
      <div className="timeline-scrollable" ref={scrollableRef}>
        {/* ヘッダー：時間ルーラー */}
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
        
        {/* トラック：キーフレーム */}
        <div className="timeline-tracks">
          {SERVO_CHANNELS.map(channel => (
            <div 
              key={channel} 
              className="timeline-track"
              onClick={handleTimelineClick}
              onTouchEnd={handleTimelineClick}
            >
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
    </div>
  );
}