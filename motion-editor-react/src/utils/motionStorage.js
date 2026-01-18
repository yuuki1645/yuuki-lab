import { DEFAULT_MOTION_DURATION } from '../constants';

const STORAGE_KEY = 'motion-editor-motions';

/**
 * ローカルストレージからモーション一覧を読み込む
 */
export function loadMotions() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return [];
    }
    return JSON.parse(stored);
  } catch (error) {
    console.error('Failed to load motions:', error);
    return [];
  }
}

/**
 * ローカルストレージにモーション一覧を保存
 */
export function saveMotions(motions) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(motions));
    return true;
  } catch (error) {
    console.error('Failed to save motions:', error);
    return false;
  }
}

/**
 * 新しいモーションを作成
 */
export function createMotion(name = '新規モーション') {
  return {
    id: `motion-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    name: name,
    duration: DEFAULT_MOTION_DURATION, // デフォルト5秒
    keyframes: [
      {
        time: 0,
        angles: {
          0: 0, 1: 70, 2: 30, 3: -30,
          8: 0, 9: 70, 10: 30, 11: -30
        }
      }
    ]
  };
}