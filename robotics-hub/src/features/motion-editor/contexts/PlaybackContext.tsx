import { createContext, useContext } from "react";

export interface PlaybackContextValue {
  isPlaying: boolean;
  isPaused: boolean;
  currentTime: number;
  duration: number;
  loop: boolean;
  playbackSpeed: number;
  setLoop: (value: boolean) => void;
  setPlaybackSpeed: (value: number) => void;
  play: () => void;
  pause: () => void;
  stop: () => void;
  seekToTime: (time: number) => void;
}

const PlaybackContext = createContext<PlaybackContextValue | null>(null);

export function usePlaybackContext(): PlaybackContextValue {
  const ctx = useContext(PlaybackContext);
  if (ctx == null) {
    throw new Error("usePlaybackContext must be used within PlaybackContext.Provider");
  }
  return ctx;
}

export default PlaybackContext;
