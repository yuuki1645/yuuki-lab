/**
 * 線形補間
 * @param {number} start - 開始値
 * @param {number} end - 終了値
 * @param {number} t - 補間係数 (0-1)
 * @returns {number} 補間された値
 */
export function lerp(start, end, t) {
  return start + (end - start) * t;
}

/**
 * 2つのキーフレーム間の補間値を計算
 * @param {Object} keyframe1 - 開始キーフレーム { time, angles }
 * @param {Object} keyframe2 - 終了キーフレーム { time, angles }
 * @param {number} currentTime - 現在の時間（ミリ秒）
 * @returns {Object} 補間された角度 { [ch]: angle }
 */
export function interpolateKeyframes(keyframe1, keyframe2, currentTime) {
  const timeDiff = keyframe2.time - keyframe1.time;
  if (timeDiff <= 0) {
    return { ...keyframe2.angles };
  }
  
  const t = (currentTime - keyframe1.time) / timeDiff;
  const clampedT = Math.max(0, Math.min(1, t));
  
  const interpolatedAngles = {};
  const allChannels = new Set([
    ...Object.keys(keyframe1.angles),
    ...Object.keys(keyframe2.angles)
  ]);
  
  for (const ch of allChannels) {
    const startAngle = keyframe1.angles[ch] ?? keyframe2.angles[ch] ?? 90;
    const endAngle = keyframe2.angles[ch] ?? keyframe1.angles[ch] ?? 90;
    interpolatedAngles[ch] = lerp(startAngle, endAngle, clampedT);
  }
  
  return interpolatedAngles;
}

/**
 * 指定時間の角度を計算（キーフレーム配列から）
 * @param {Array} keyframes - キーフレーム配列（時間順にソート済み）
 * @param {number} time - 現在の時間（ミリ秒）
 * @returns {Object} 補間された角度 { [ch]: angle }
 */
export function getAngleAtTime(keyframes, time) {
  if (keyframes.length === 0) {
    return {};
  }
  
  if (keyframes.length === 1) {
    return { ...keyframes[0].angles };
  }
  
  // 時間が最初のキーフレームより前
  if (time <= keyframes[0].time) {
    return { ...keyframes[0].angles };
  }
  
  // 時間が最後のキーフレームより後
  if (time >= keyframes[keyframes.length - 1].time) {
    return { ...keyframes[keyframes.length - 1].angles };
  }
  
  // 2つのキーフレーム間を見つける
  for (let i = 0; i < keyframes.length - 1; i++) {
    const kf1 = keyframes[i];
    const kf2 = keyframes[i + 1];
    
    if (time >= kf1.time && time <= kf2.time) {
      return interpolateKeyframes(kf1, kf2, time);
    }
  }
  
  return {};
}