import { useMemo } from "react";
import { useMotionContext } from "../contexts/MotionContext";
import { useInterpolation } from "../hooks/useInterpolation";
import PlaybackContext from "../contexts/PlaybackContext";

interface PlaybackContextProviderProps {
  children: React.ReactNode;
}

export default function PlaybackContextProvider({
  children,
}: PlaybackContextProviderProps) {
  const { keyframes, motionDuration } = useMotionContext();

  const {
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
  } = useInterpolation(keyframes, motionDuration, "logical");

  const value = useMemo(
    () => ({
      isPlaying,
      isPaused,
      currentTime,
      duration: motionDuration,
      loop,
      playbackSpeed,
      setLoop,
      setPlaybackSpeed,
      play,
      pause,
      stop,
      seekToTime,
    }),
    [
      isPlaying,
      isPaused,
      currentTime,
      motionDuration,
      loop,
      playbackSpeed,
      setLoop,
      setPlaybackSpeed,
      play,
      pause,
      stop,
      seekToTime,
    ]
  );

  return (
    <PlaybackContext.Provider value={value}>{children}</PlaybackContext.Provider>
  );
}
