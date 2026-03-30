import { useState, useEffect, useRef, useCallback } from "react";
import { getAngleAtTime } from "../utils/interpolation";
import { moveServos } from "@/shared/api/servoApi";
import { INTERPOLATION_INTERVAL, SERVO_CHANNELS } from "@/shared/constants";
import type { Keyframe } from "@/shared/types";
import type { ServoMode } from "@/shared/types";

export function useInterpolation(
  keyframes: Keyframe[],
  duration: number,
  mode: ServoMode = "logical"
) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [loop, setLoop] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);

  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const pausedTimeRef = useRef(0);

  const play = useCallback(() => {
    if (isPaused) {
      setIsPaused(false);
      setIsPlaying(true);
      startTimeRef.current = performance.now() - pausedTimeRef.current;
    } else {
      setIsPlaying(true);
      setCurrentTime(0);
      startTimeRef.current = performance.now();
      pausedTimeRef.current = 0;
    }
  }, [isPaused]);

  const stop = useCallback(() => {
    setIsPlaying(false);
    setIsPaused(false);
    setCurrentTime(0);
    pausedTimeRef.current = 0;
    if (animationFrameRef.current != null) {
      cancelAnimationFrame(animationFrameRef.current);
    }
  }, []);

  const pause = useCallback(() => {
    setIsPaused(true);
    setIsPlaying(false);
  }, []);

  useEffect(() => {
    if (!isPlaying || isPaused) {
      if (animationFrameRef.current != null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (isPaused && pausedTimeRef.current === 0 && currentTime > 0) {
        pausedTimeRef.current = currentTime;
      }
      return;
    }

    let lastUpdateTime = 0;

    const animate = (timestamp: number) => {
      if (startTimeRef.current == null) {
        startTimeRef.current = timestamp;
      }

      const elapsed =
        (timestamp - startTimeRef.current) * playbackSpeed;
      const newTime = pausedTimeRef.current + elapsed;

      if (newTime >= duration) {
        if (loop) {
          pausedTimeRef.current = 0;
          startTimeRef.current = timestamp;
          setCurrentTime(0);
        } else {
          stop();
          return;
        }
      } else {
        setCurrentTime(newTime);
      }

      if (timestamp - lastUpdateTime >= INTERPOLATION_INTERVAL) {
        const angles = getAngleAtTime(keyframes, newTime, SERVO_CHANNELS);
        if (Object.keys(angles).length > 0) {
          moveServos(angles, mode).catch((err) => {
            console.error("Failed to move servos:", err);
          });
        }
        lastUpdateTime = timestamp;
      }

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current != null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [
    isPlaying,
    isPaused,
    keyframes,
    duration,
    loop,
    playbackSpeed,
    mode,
    stop,
  ]);

  const seekToTime = useCallback(
    (time: number) => {
      const clampedTime = Math.max(0, Math.min(time, duration));

      if (isPlaying || isPaused) {
        setIsPlaying(false);
        setIsPaused(false);
        if (animationFrameRef.current != null) {
          cancelAnimationFrame(animationFrameRef.current);
        }
      }

      setCurrentTime(clampedTime);
      pausedTimeRef.current = clampedTime;

      const angles = getAngleAtTime(keyframes, clampedTime, SERVO_CHANNELS);
      if (Object.keys(angles).length > 0) {
        moveServos(angles, mode).catch((err) => {
          console.error("Failed to move servos:", err);
        });
      }
    },
    [duration, isPlaying, isPaused, keyframes, mode]
  );

  return {
    isPlaying,
    isPaused,
    currentTime,
    loop,
    playbackSpeed,
    setLoop,
    setPlaybackSpeed,
    play,
    pause,
    stop,
    seekToTime,
  };
}
