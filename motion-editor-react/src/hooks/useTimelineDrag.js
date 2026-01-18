import { useRef, useState } from 'react';
import { MAX_MOTION_DURATION } from '../constants';

export function useTimelineDrag(scrollableRef, keyframes, onKeyframeDrag) {
  const dragStateRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  
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
  
  // キーフレームのドラッグ開始
  const handleKeyframeStart = (e, keyframeIndex, channel, timeToX, xToTime, timelineWidth, displayDuration) => {
    e.stopPropagation();
    e.preventDefault();
    
    if (!scrollableRef.current) return;
    const rect = scrollableRef.current.getBoundingClientRect();
    const clientX = getClientX(e);
    const startX = clientX - rect.left;
    const startTime = keyframes[keyframeIndex].time;
    
    dragStateRef.current = {
      keyframeIndex,
      channel,
      startX,
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
      const deltaTime = (deltaX / timelineWidth) * displayDuration;
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
  
  return {
    isDragging,
    handleKeyframeStart,
    getClientX,
  };
}