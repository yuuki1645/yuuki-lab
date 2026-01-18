import { useState, useEffect, useCallback } from 'react';
import { loadMotions, saveMotions, createMotion } from '../utils/motionStorage';

export function useMotion() {
  const [motions, setMotions] = useState([]);
  const [currentMotionId, setCurrentMotionId] = useState(null);
  
  // 初期化：ローカルストレージから読み込み
  useEffect(() => {
    const loaded = loadMotions();
    setMotions(loaded);
    if (loaded.length > 0) {
      setCurrentMotionId(loaded[0].id);
    }
  }, []);
  
  // モーション変更時に保存
  useEffect(() => {
    if (motions.length > 0) {
      saveMotions(motions);
    }
  }, [motions]);
  
  // 現在のモーションを取得
  const currentMotion = motions.find(m => m.id === currentMotionId) || null;
  
  // 新しいモーションを作成
  const addMotion = useCallback((name) => {
    const newMotion = createMotion(name);
    setMotions(prev => [...prev, newMotion]);
    setCurrentMotionId(newMotion.id);
    return newMotion;
  }, []);
  
  // モーションを削除
  const deleteMotion = useCallback((id) => {
    setMotions(prev => {
      const filtered = prev.filter(m => m.id !== id);
      if (filtered.length > 0 && currentMotionId === id) {
        setCurrentMotionId(filtered[0].id);
      } else if (filtered.length === 0) {
        setCurrentMotionId(null);
      }
      return filtered;
    });
  }, [currentMotionId]);
  
  // モーションを更新
  const updateMotion = useCallback((id, updates) => {
    setMotions(prev => prev.map(m => 
      m.id === id ? { ...m, ...updates } : m
    ));
  }, []);
  
  // モーション名を変更
  const renameMotion = useCallback((id, newName) => {
    updateMotion(id, { name: newName });
  }, [updateMotion]);
  
  return {
    motions,
    currentMotion,
    currentMotionId,
    setCurrentMotionId,
    addMotion,
    deleteMotion,
    updateMotion,
    renameMotion,
  };
}