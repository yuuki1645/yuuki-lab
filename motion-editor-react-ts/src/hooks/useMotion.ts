import { useState, useEffect, useCallback, useRef } from "react";
import {
  loadMotions,
  saveMotions,
  createMotion,
  loadCurrentMotionId,
  saveCurrentMotionId,
  ensureKeyframeIds,
} from "../utils/motionStorage";
import type { Motion } from "../types";

export function useMotion() {
  const [motions, setMotions] = useState<Motion[]>([]);
  const [currentMotionId, setCurrentMotionId] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const isInitialLoadRef = useRef(true);

  useEffect(() => {
    const loaded = loadMotions();
    const savedMotionId = loadCurrentMotionId();

    if (loaded.length > 0) {
      setMotions(ensureKeyframeIds(loaded));
      const validId =
        savedMotionId && loaded.some((m) => m.id === savedMotionId)
          ? savedMotionId
          : loaded[0]!.id;
      setCurrentMotionId(validId);
    } else {
      const defaultMotion = createMotion("デフォルトモーション");
      setMotions([defaultMotion]);
      setCurrentMotionId(defaultMotion.id);
    }

    setIsInitialized(true);
    isInitialLoadRef.current = false;
  }, []);

  useEffect(() => {
    if (isInitialized && !isInitialLoadRef.current && motions.length > 0) {
      saveMotions(motions);
    }
  }, [motions, isInitialized]);

  useEffect(() => {
    if (isInitialized && !isInitialLoadRef.current && currentMotionId) {
      saveCurrentMotionId(currentMotionId);
    }
  }, [isInitialized, currentMotionId]);

  const currentMotion =
    motions.find((m) => m.id === currentMotionId) ?? null;

  const addMotion = useCallback((name: string) => {
    const newMotion = createMotion(name);
    setMotions((prev) => [...prev, newMotion]);
    setCurrentMotionId(newMotion.id);
    return newMotion;
  }, []);

  const deleteMotion = useCallback(
    (id: string) => {
      setMotions((prev) => {
        const filtered = prev.filter((m) => m.id !== id);
        if (filtered.length > 0 && currentMotionId === id) {
          setCurrentMotionId(filtered[0]!.id);
        } else if (filtered.length === 0) {
          const defaultMotion = createMotion("デフォルトモーション");
          setCurrentMotionId(defaultMotion.id);
          return [defaultMotion];
        }
        return filtered;
      });
    },
    [currentMotionId]
  );

  const updateMotion = useCallback(
    (id: string, updates: Partial<Motion>) => {
      setMotions((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...updates } : m))
      );
    },
    []
  );

  const renameMotion = useCallback(
    (id: string, newName: string) => {
      updateMotion(id, { name: newName });
    },
    [updateMotion]
  );

  return {
    motions,
    currentMotion,
    currentMotionId,
    setCurrentMotionId,
    addMotion,
    deleteMotion,
    updateMotion,
    renameMotion,
    isInitialized,
  };
}
