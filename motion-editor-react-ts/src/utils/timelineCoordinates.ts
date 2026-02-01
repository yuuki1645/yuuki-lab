import { MAX_MOTION_DURATION } from "../constants";

/** タイムラインの表示幅（px）。1秒=300px、20秒=6000px */
export const TIMELINE_WIDTH = 6000;

/** タイムラインで表示する時間範囲（ms） */
export const DISPLAY_DURATION: number = MAX_MOTION_DURATION;

/**
 * 時間（ms）を X 座標（px）に変換
 */
export function timeToX(time: number): number {
  if (DISPLAY_DURATION === 0) return 0;
  return (time / DISPLAY_DURATION) * TIMELINE_WIDTH;
}

/**
 * X 座標（px）を時間（ms）に変換（0 ～ MAX_MOTION_DURATION にクランプ）
 */
export function xToTime(x: number): number {
  if (DISPLAY_DURATION === 0) return 0;
  return Math.max(
    0,
    Math.min(MAX_MOTION_DURATION, (x / TIMELINE_WIDTH) * DISPLAY_DURATION)
  );
}
