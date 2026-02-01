import { createContext, useContext } from 'react';

const MotionContext = createContext(null);

export function useMotionContext() {
  const ctx = useContext(MotionContext);
  if (ctx == null) {
    throw new Error('useMotionContext must be used within MotionContext.Provider');
  }
  return ctx;
}

export default MotionContext;