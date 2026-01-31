import { useCallback } from 'react';
import { MAX_MOTION_DURATION, MIN_KEYFRAME_INTERVAL } from '../constants';
import { getAngleAtTime } from '../utils/interpolation';

export function useKeyframes(motion, updateMotion) {
  const sortedKeyframes = [...(motion?.keyframes || [])].sort(
    (a, b) => a.time - b.time || a.channel - b.channel
  );

  const getAngleAtTimeForChannel = useCallback((time, channel, keyframes) => {
    const result = getAngleAtTime(keyframes, time, [channel]);
    return result[channel] ?? 90;
  }, []);

  const findNonOverlappingTime = useCallback((desiredTime, sameChannelKeyframes, excludeIndex) => {
    let adjustedTime = Math.max(0, Math.min(MAX_MOTION_DURATION, desiredTime));

    for (let i = 0; i < sameChannelKeyframes.length; i++) {
      if (i === excludeIndex) continue;
      const existingTime = sameChannelKeyframes[i].time;
      const timeDiff = Math.abs(adjustedTime - existingTime);

      if (timeDiff < MIN_KEYFRAME_INTERVAL) {
        adjustedTime = existingTime + MIN_KEYFRAME_INTERVAL;
        if (adjustedTime > MAX_MOTION_DURATION) {
          adjustedTime = Math.max(0, existingTime - MIN_KEYFRAME_INTERVAL);
        }
      }
    }

    return Math.max(0, Math.min(MAX_MOTION_DURATION, adjustedTime));
  }, []);

  const addKeyframe = useCallback((time, channel) => {
    if (!motion || channel == null) return;

    const clampedTime = Math.max(0, Math.min(MAX_MOTION_DURATION, time));
    const angle = getAngleAtTimeForChannel(clampedTime, channel, sortedKeyframes);
    const newKeyframe = { time: clampedTime, channel, angle };
    const newKeyframes = [...sortedKeyframes, newKeyframe].sort(
      (a, b) => a.time - b.time || a.channel - b.channel
    );
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion, getAngleAtTimeForChannel]);

  const deleteKeyframe = useCallback((index) => {
    if (!motion || sortedKeyframes.length <= 1) return;
    const newKeyframes = sortedKeyframes.filter((_, i) => i !== index);
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion]);

  const updateKeyframeTime = useCallback((index, newTime) => {
    if (!motion) return;

    const clampedTime = Math.max(0, Math.min(MAX_MOTION_DURATION, newTime));
    const kf = sortedKeyframes[index];
    const sameChannel = sortedKeyframes.filter(item => item.channel === kf.channel);
    const excludeIndex = sameChannel.findIndex(item => item === kf);
    const adjustedTime = findNonOverlappingTime(clampedTime, sameChannel, excludeIndex);

    const newKeyframes = [...sortedKeyframes];
    newKeyframes[index] = { ...newKeyframes[index], time: adjustedTime };
    newKeyframes.sort((a, b) => a.time - b.time || a.channel - b.channel);
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion, findNonOverlappingTime]);

  const updateKeyframeAngle = useCallback((index, angle) => {
    if (!motion) return;
    const newKeyframes = [...sortedKeyframes];
    newKeyframes[index] = { ...newKeyframes[index], angle };
    updateMotion(motion.id, { keyframes: newKeyframes });
  }, [motion, sortedKeyframes, updateMotion]);

  return {
    keyframes: sortedKeyframes,
    addKeyframe,
    deleteKeyframe,
    updateKeyframeTime,
    updateKeyframeAngle,
  };
}