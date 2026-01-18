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
    duration: 5000, // デフォルト5秒
    keyframes: [
      {
        time: 0,
        angles: {
          0: 90, 1: 90, 2: 90, 3: 90,
          8: 90, 9: 90, 10: 90, 11: 90
        }
      }
    ]
  };
}