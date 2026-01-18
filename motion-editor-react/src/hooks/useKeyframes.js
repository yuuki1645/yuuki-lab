import { useCallback } from 'react';

export function useKeyframes(motion, updateMotion) {
  // キーフレームを時間順にソート
  const sortedKeyframes = [...(motion?.keyframes || [])].sort((a, b) => a.time - b.time);
  
  // キーフレームを追加
  const addKeyframe = useCallback((time) => {
    if (!motion) return;
    
    // 既存のキーフレームから最も近いものをコピー
    let angles = {};
    if (sortedKeyframes.length > 0) {
      const closest = sortedKeyframes.reduce((prev, curr) => 
        Math.abs(curr.time - time) < Math.abs(prev.time - time) ? curr : prev
      );
      angles = { ...closest.angles };
    } else {
      // デフォルト角度
      angles = { 0: 90, 1: 90, 2: 90, 3: 90, 8: 90, 9: 90, 10: 90, 11: 90 };
    }
    
    const newKeyframe = { time, angles };
    const newKeyframes = [...sortedKeyframes, newKeyframe].sort((a, b) => a.time - b.time);
    
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion]);
  
  // キーフレームを削除
  const deleteKeyframe = useCallback((index) => {
    if (!motion || sortedKeyframes.length <= 1) return; // 最低1つは残す
    
    const newKeyframes = sortedKeyframes.filter((_, i) => i !== index);
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion]);
  
  // キーフレームの時間を更新
  const updateKeyframeTime = useCallback((index, newTime) => {
    if (!motion) return;
    
    const newKeyframes = [...sortedKeyframes];
    newKeyframes[index] = { ...newKeyframes[index], time: Math.max(0, newTime) };
    newKeyframes.sort((a, b) => a.time - b.time);
    
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion]);
  
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