import { DEFAULT_MOTION_DURATION, SERVO_CHANNELS } from '../constants';

const STORAGE_KEY = 'motion-editor-motions';
const CURRENT_MOTION_ID_KEY = 'motion-editor-current-motion-id';

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
 * ローカルストレージから前回選択していたモーションIDを読み込む
 */
export function loadCurrentMotionId() {
  try {
    return localStorage.getItem(CURRENT_MOTION_ID_KEY);
  } catch {
    return null;
  }
}

/**
 * 選択中のモーションIDをローカルストレージに保存（再読込時に復元するため）
 */
export function saveCurrentMotionId(id) {
  try {
    if (id != null) {
      localStorage.setItem(CURRENT_MOTION_ID_KEY, id);
    } else {
      localStorage.removeItem(CURRENT_MOTION_ID_KEY);
    }
    return true;
  } catch (error) {
    console.error('Failed to save current motion id:', error);
    return false;
  }
}

/** 初期ポーズ（1ch 1キーフレーム） */
const INITIAL_ANGLES = {
  0: 0, 1: 70, 2: 30, 3: -30, 4: 0,
  8: 0, 9: 70, 10: 30, 11: -30, 12: 0,
};

/**
 * キーフレーム用の一意な id を生成
 */
export function generateKeyframeId() {
  return `kf-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

/**
 * 既存のモーションにキーフレーム id が無い場合に付与（マイグレーション用）
 */
export function ensureKeyframeIds(motions) {
  if (!Array.isArray(motions)) return motions;
  return motions.map((m) => {
    if (!m.keyframes || !m.keyframes.length) return m;
    const keyframes = m.keyframes.map((kf) =>
      kf.id ? kf : { ...kf, id: generateKeyframeId() }
    );
    return { ...m, keyframes };
  });
}

/**
 * 新しいモーションを作成（キーフレームは ch ごとに 1 個ずつ、各キーフレームに id 付与）
 */
export function createMotion(name = '新規モーション') {
  return {
    id: `motion-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    name: name,
    duration: DEFAULT_MOTION_DURATION,
    keyframes: SERVO_CHANNELS.map((ch) => ({
      id: generateKeyframeId(),
      time: 0,
      channel: ch,
      angle: INITIAL_ANGLES[ch] ?? 90,
    })),
  };
}