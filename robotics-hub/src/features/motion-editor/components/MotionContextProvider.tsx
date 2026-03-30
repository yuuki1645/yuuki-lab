import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { useMotion } from "../hooks/useMotion";
import { useKeyframes } from "../hooks/useKeyframes";
import { useServos } from "@/shared/hooks/useServos";
import {
  MAX_MOTION_DURATION,
  DEFAULT_MOTION_DURATION,
  SERVO_CHANNELS,
} from "@/shared/constants";
import { getAngleAtTime } from "../utils/interpolation";
import { transitionServos } from "@/shared/api/servoApi";
import MotionContext from "../contexts/MotionContext";
import type { Motion } from "@/shared/types";

interface MotionContextProviderProps {
  children: React.ReactNode;
}

export default function MotionContextProvider({ children }: MotionContextProviderProps) {
  const {
    motions,
    currentMotion,
    currentMotionId,
    setCurrentMotionId,
    addMotion,
    deleteMotion,
    updateMotion,
    renameMotion,
    isInitialized,
  } = useMotion();

  const {
    keyframes,
    addKeyframe,
    deleteKeyframe,
    updateKeyframeTime,
    updateKeyframeAngle,
  } = useKeyframes(currentMotion, updateMotion);

  const { servos } = useServos();

  const [selectedKeyframeId, setSelectedKeyframeId] = useState<string | null>(
    null
  );
  const endKeyframeDragRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (currentMotion && selectedKeyframeId !== null) {
      const exists = keyframes.some((kf) => kf.id === selectedKeyframeId);
      if (!exists) setSelectedKeyframeId(null);
    }
  }, [currentMotion, selectedKeyframeId, keyframes]);

  const handleMoveToInitialPosition = useCallback(async (motion: Motion) => {
    if (!motion?.keyframes?.length) {
      alert("モーションにキーフレームがありません");
      return;
    }
    const angles = getAngleAtTime(motion.keyframes, 0, SERVO_CHANNELS);
    const angleEntries = Object.entries(angles).filter(
      ([, angle]) => angle !== undefined && angle !== null
    );
    if (angleEntries.length === 0) {
      alert("設定可能な角度がありません");
      return;
    }
    const anglesObj: Record<string, number> = {};
    for (const [ch, angle] of angleEntries) {
      anglesObj[String(ch)] = angle;
    }
    try {
      await transitionServos(anglesObj, "logical", 3.0);
      alert("初期位置への移動を開始しました");
    } catch (error) {
      console.error("Failed to move to initial position:", error);
      alert(`エラー: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, []);

  const handleTimeClick = useCallback(
    (time: number, channel: number | null) => {
      if (currentMotion && channel !== null) addKeyframe(time, channel);
    },
    [currentMotion, addKeyframe]
  );

  const handleKeyframeClick = useCallback((id: string) => {
    setSelectedKeyframeId(id);
  }, []);
  const handleKeyframeDrag = useCallback(
    (id: string, newTime: number) => updateKeyframeTime(id, newTime),
    [updateKeyframeTime]
  );
  const handleAngleUpdate = useCallback(
    (keyframeId: string, angle: number) =>
      updateKeyframeAngle(keyframeId, angle),
    [updateKeyframeAngle]
  );
  const handleKeyframeDelete = useCallback(
    (keyframeId: string) => {
      deleteKeyframe(keyframeId);
      setSelectedKeyframeId(null);
    },
    [deleteKeyframe]
  );

  const selectedKeyframe =
    selectedKeyframeId !== null
      ? keyframes.find((kf) => kf.id === selectedKeyframeId) ?? null
      : null;
  const selectedChannel = selectedKeyframe?.channel ?? null;
  const selectedServo =
    selectedChannel !== null
      ? servos.find((s) => s.ch === selectedChannel) ?? null
      : null;

  const value = useMemo(
    () => ({
      motions,
      currentMotionId,
      setCurrentMotionId,
      addMotion,
      deleteMotion,
      renameMotion,
      handleMoveToInitialPosition,
      keyframes,
      handleTimeClick,
      handleKeyframeClick,
      handleKeyframeDrag,
      selectedKeyframeId,
      handleAngleUpdate,
      handleKeyframeDelete,
      selectedKeyframe,
      selectedChannel,
      selectedServo: selectedServo ?? null,
      endKeyframeDragRef,
      isInitialized,
      motionDuration: currentMotion
        ? Math.min(currentMotion.duration, MAX_MOTION_DURATION)
        : DEFAULT_MOTION_DURATION,
    }),
    [
      motions,
      currentMotionId,
      addMotion,
      deleteMotion,
      renameMotion,
      handleMoveToInitialPosition,
      keyframes,
      handleTimeClick,
      handleKeyframeClick,
      handleKeyframeDrag,
      selectedKeyframeId,
      handleAngleUpdate,
      handleKeyframeDelete,
      selectedKeyframe,
      selectedChannel,
      selectedServo,
      currentMotion,
      isInitialized,
    ]
  );

  return (
    <MotionContext.Provider value={value}>{children}</MotionContext.Provider>
  );
}
