import { createContext, useContext } from 'react';

const PlaybackContext = createContext(null);

export function usePlaybackContext() {
  const ctx = useContext(PlaybackContext);
  if (ctx == null) {
    throw new Error('usePlaybackContext must be used within PlaybackContext.Provider');
  }
  return ctx;
}

export default PlaybackContext;