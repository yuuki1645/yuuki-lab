import { useState, useEffect, useRef, useCallback } from 'react';
import { getAngleAtTime } from '../utils/interpolation';
import { moveServos } from '../api/servoApi';
import { INTERPOLATION_INTERVAL } from '../constants';

export function useInterpolation(keyframes, duration, mode = 'logical') {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [loop, setLoop] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  
  const animationFrameRef = useRef(null);
  const startTimeRef = useRef(null);
  const pausedTimeRef = useRef(0);
  
  // 再生
  const play = useCallback(() => {
    if (isPaused) {
      // 一時停止から再開
      setIsPaused(false);
      startTimeRef.current = performance.now() - pausedTimeRef.current;
    } else {
      // 最初から再生
      setIsPlaying(true);
      setCurrentTime(0);
      startTimeRef.current = performance.now();
      pausedTimeRef.current = 0;
    }
  }, [isPaused]);
  
  // 停止
  const stop = useCallback(() => {
    setIsPlaying(false);
    setIsPaused(false);
    setCurrentTime(0);
    pausedTimeRef.current = 0;
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
  }, []);
  
  // 一時停止
  const pause = useCallback(() => {
    setIsPaused(true);
    setIsPlaying(false);
  }, []);
  
  // アニメーションループ
  useEffect(() => {
    if (!isPlaying || isPaused) {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      return;
    }
    
    let lastUpdateTime = 0;
    
    const animate = (timestamp) => {
      if (!startTimeRef.current) {
        startTimeRef.current = timestamp;
      }
      
      const elapsed = (timestamp - startTimeRef.current) * playbackSpeed;
      const newTime = pausedTimeRef.current + elapsed;
      
      // ループ処理
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
        pausedTimeRef.current = newTime;
      }
      
      // 一定間隔でサーボを更新
      if (timestamp - lastUpdateTime >= INTERPOLATION_INTERVAL) {
        const angles = getAngleAtTime(keyframes, newTime);
        if (Object.keys(angles).length > 0) {
          moveServos(angles, mode).catch(err => {
            console.error('Failed to move servos:', err);
          });
        }
        lastUpdateTime = timestamp;
      }
      
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    
    animationFrameRef.current = requestAnimationFrame(animate);
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, isPaused, keyframes, duration, loop, playbackSpeed, mode, stop]);
  
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
  };
}