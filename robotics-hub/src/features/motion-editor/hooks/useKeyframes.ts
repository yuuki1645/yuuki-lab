import { useCallback } from "react";
import { MAX_MOTION_DURATION } from "@/shared/constants";
import { getAngleAtTime } from "../utils/interpolation";
import { generateKeyframeId } from "../utils/motionStorage";
import type { Motion, Keyframe } from "@/shared/types";

export function useKeyframes(
  motion: Motion | null,
  updateMotion: (id: string, updates: Partial<Motion>) => void
) {
  const sortedKeyframes = [...(motion?.keyframes ?? [])].sort(
    (a, b) => a.time - b.time || a.channel - b.channel
  );

  const getAngleAtTimeForChannel = useCallback(
    (time: number, channel: number, keyframes: Keyframe[]): number => {
      const result = getAngleAtTime(keyframes, time, [channel]);
      return result[channel] ?? 90;
    },
    []
  );

  const addKeyframe = useCallback(
    (time: number, channel: number | null) => {
      if (!motion || channel == null) return;

      const clampedTime = Math.max(
        0,
        Math.min(MAX_MOTION_DURATION, time)
      );
      const angle = getAngleAtTimeForChannel(
        clampedTime,
        channel,
        sortedKeyframes
      );
      const newKeyframe: Keyframe = {
        id: generateKeyframeId(),
        time: clampedTime,
        channel,
        angle,
      };
      const newKeyframes = [...sortedKeyframes, newKeyframe].sort(
        (a, b) => a.time - b.time || a.channel - b.channel
      );
      updateMotion(motion.id, { keyframes: newKeyframes });
    },
    [motion, sortedKeyframes, updateMotion, getAngleAtTimeForChannel]
  );

  const deleteKeyframe = useCallback(
    (id: string) => {
      if (!motion || sortedKeyframes.length <= 1) return;
      const newKeyframes = sortedKeyframes.filter((kf) => kf.id !== id);
      updateMotion(motion.id, { keyframes: newKeyframes });
    },
    [motion, sortedKeyframes, updateMotion]
  );

  const updateKeyframeTime = useCallback(
    (id: string, newTime: number) => {
      if (!motion) return;

      const clampedTime = Math.max(
        0,
        Math.min(MAX_MOTION_DURATION, newTime)
      );
      const index = sortedKeyframes.findIndex((kf) => kf.id === id);
      if (index < 0) return;

      const newKeyframes = [...sortedKeyframes];
      newKeyframes[index] = { ...newKeyframes[index]!, time: clampedTime };
      newKeyframes.sort(
        (a, b) => a.time - b.time || a.channel - b.channel
      );
      updateMotion(motion.id, { keyframes: newKeyframes });
    },
    [motion, sortedKeyframes, updateMotion]
  );

  const updateKeyframeAngle = useCallback(
    (id: string, angle: number) => {
      if (!motion) return;
      const index = sortedKeyframes.findIndex((kf) => kf.id === id);
      if (index < 0) return;
      const newKeyframes = [...sortedKeyframes];
      newKeyframes[index] = { ...newKeyframes[index]!, angle };
      updateMotion(motion.id, { keyframes: newKeyframes });
    },
    [motion, sortedKeyframes, updateMotion]
  );

  return {
    keyframes: sortedKeyframes,
    addKeyframe,
    deleteKeyframe,
    updateKeyframeTime,
    updateKeyframeAngle,
  };
}
