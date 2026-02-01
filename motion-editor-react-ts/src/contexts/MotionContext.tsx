import { createContext, useContext } from "react";

const MotionContext = createContext<MotionContextValue | null>(null);

export interface MotionContextValue {
  motions: import("../types").Motion[];
  currentMotionId: string | null;
  setCurrentMotionId: (id: string | null) => void;
  addMotion: (name: string) => import("../types").Motion;
  deleteMotion: (id: string) => void;
  renameMotion: (id: string, newName: string) => void;
  handleMoveToInitialPosition: (motion: import("../types").Motion) => Promise<void>;
  keyframes: import("../types").Keyframe[];
  handleTimeClick: (time: number, channel: number | null) => void;
  handleKeyframeClick: (id: string) => void;
  handleKeyframeDrag: (id: string, newTime: number) => void;
  selectedKeyframeId: string | null;
  handleAngleUpdate: (keyframeId: string, angle: number) => void;
  handleKeyframeDelete: (keyframeId: string) => void;
  selectedKeyframe: import("../types").Keyframe | null;
  selectedChannel: number | null;
  selectedServo: import("../types").Servo | null;
  endKeyframeDragRef: React.MutableRefObject<(() => void) | null>;
  isInitialized: boolean;
  motionDuration: number;
}

export function useMotionContext(): MotionContextValue {
  const ctx = useContext(MotionContext);
  if (ctx == null) {
    throw new Error("useMotionContext must be used within MotionContext.Provider");
  }
  return ctx;
}

export default MotionContext;
