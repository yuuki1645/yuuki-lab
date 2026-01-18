import { MAX_MOTION_DURATION } from '../constants';

const TIMELINE_WIDTH = 6000; // タイムラインの実際の幅（1秒=300px、20秒=6000px）
const DISPLAY_DURATION = MAX_MOTION_DURATION;

export function useTimelineCoordinates() {
  // 時間をピクセル位置に変換
  const timeToX = (time) => {
    if (DISPLAY_DURATION === 0) return 0;
    return (time / DISPLAY_DURATION) * TIMELINE_WIDTH;
  };
  
  // ピクセル位置を時間に変換
  const xToTime = (x) => {
    if (DISPLAY_DURATION === 0) return 0;
    return Math.max(0, Math.min(MAX_MOTION_DURATION, (x / TIMELINE_WIDTH) * DISPLAY_DURATION));
  };
  
  return {
    timeToX,
    xToTime,
    TIMELINE_WIDTH,
    DISPLAY_DURATION,
  };
}