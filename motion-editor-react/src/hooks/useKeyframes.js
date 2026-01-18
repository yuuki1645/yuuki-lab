import { useCallback } from 'react';
import { MAX_MOTION_DURATION, MIN_KEYFRAME_INTERVAL } from '../constants';

export function useKeyframes(motion, updateMotion) {
  // キーフレームを時間順にソート
  const sortedKeyframes = [...(motion?.keyframes || [])].sort((a, b) => a.time - b.time);
  
  // 重複しない時間を見つける
  const findNonOverlappingTime = useCallback((desiredTime, existingKeyframes, excludeIndex = -1) => {
    let adjustedTime = Math.max(0, Math.min(MAX_MOTION_DURATION, desiredTime));
    
    // 既存のキーフレームと重複しない時間を探す
    for (let i = 0; i < existingKeyframes.length; i++) {
      if (i === excludeIndex) continue; // 自分自身は除外
      
      const existingTime = existingKeyframes[i].time;
      const timeDiff = Math.abs(adjustedTime - existingTime);
      
      // 最小間隔より近い場合は時間を調整
      if (timeDiff < MIN_KEYFRAME_INTERVAL) {
        // 既存のキーフレームより後ろに配置
        adjustedTime = existingTime + MIN_KEYFRAME_INTERVAL;
        
        // 最大時間を超えないようにする
        if (adjustedTime > MAX_MOTION_DURATION) {
          // 既存のキーフレームより前に配置を試みる
          adjustedTime = existingTime - MIN_KEYFRAME_INTERVAL;
          if (adjustedTime < 0) {
            // 前に配置できない場合は、次のキーフレームの前を探す
            if (i + 1 < existingKeyframes.length) {
              const nextTime = existingKeyframes[i + 1].time;
              if (nextTime - existingTime > MIN_KEYFRAME_INTERVAL * 2) {
                adjustedTime = existingTime + MIN_KEYFRAME_INTERVAL;
              } else {
                // 適切な位置が見つからない場合は、既存の時間から少しずらす
                adjustedTime = existingTime + MIN_KEYFRAME_INTERVAL;
              }
            } else {
              adjustedTime = existingTime + MIN_KEYFRAME_INTERVAL;
            }
          }
        }
      }
    }
    
    return Math.max(0, Math.min(MAX_MOTION_DURATION, adjustedTime));
  }, []);
  
  // キーフレームを追加
  const addKeyframe = useCallback((time) => {
    if (!motion) return;
    
    // 最大時間を制限
    const clampedTime = Math.max(0, Math.min(MAX_MOTION_DURATION, time));
    
    // 重複しない時間を見つける
    const adjustedTime = findNonOverlappingTime(clampedTime, sortedKeyframes);
    
    // 既存のキーフレームから最も近いものをコピー
    let angles = {};
    if (sortedKeyframes.length > 0) {
      const closest = sortedKeyframes.reduce((prev, curr) => 
        Math.abs(curr.time - adjustedTime) < Math.abs(prev.time - adjustedTime) ? curr : prev
      );
      angles = { ...closest.angles };
    } else {
      // デフォルト角度
      angles = { 0: 90, 1: 90, 2: 90, 3: 90, 8: 90, 9: 90, 10: 90, 11: 90 };
    }
    
    const newKeyframe = { time: adjustedTime, angles };
    const newKeyframes = [...sortedKeyframes, newKeyframe].sort((a, b) => a.time - b.time);
    
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion, findNonOverlappingTime]);
  
  // キーフレームを削除
  const deleteKeyframe = useCallback((index) => {
    if (!motion || sortedKeyframes.length <= 1) return; // 最低1つは残す
    
    const newKeyframes = sortedKeyframes.filter((_, i) => i !== index);
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion]);
  
  // キーフレームの時間を更新
  const updateKeyframeTime = useCallback((index, newTime) => {
    if (!motion) return;
    
    // 最大時間を制限
    const clampedTime = Math.max(0, Math.min(MAX_MOTION_DURATION, newTime));
    
    // 重複しない時間を見つける（自分自身を除外）
    const adjustedTime = findNonOverlappingTime(clampedTime, sortedKeyframes, index);
    
    const newKeyframes = [...sortedKeyframes];
    newKeyframes[index] = { ...newKeyframes[index], time: adjustedTime };
    newKeyframes.sort((a, b) => a.time - b.time);
    
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion, findNonOverlappingTime]);
  
  // キーフレームの角度を更新
  const updateKeyframeAngles = useCallback((index, angles) => {
    if (!motion) return;
    
    const newKeyframes = [...sortedKeyframes];
    newKeyframes[index] = { ...newKeyframes[index], angles: { ...angles } };
    
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion]);
  
  // 特定チャンネルの角度を更新
  const updateKeyframeAngle = useCallback((index, channel, angle) => {
    if (!motion) return;
    
    const newKeyframes = [...sortedKeyframes];
    newKeyframes[index] = {
      ...newKeyframes[index],
      angles: {
        ...newKeyframes[index].angles,
        [channel]: angle
      }
    };
    
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion]);
  
  return {
    keyframes: sortedKeyframes,
    addKeyframe,
    deleteKeyframe,
    updateKeyframeTime,
    updateKeyframeAngles,
    updateKeyframeAngle,
  };
}