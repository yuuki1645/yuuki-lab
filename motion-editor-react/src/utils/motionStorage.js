import { DEFAULT_MOTION_DURATION, SERVO_CHANNELS } from '../constants';

const STORAGE_KEY = 'motion-editor-motions';
const CURRENT_MOTION_ID_KEY = 'motion-editor-current-motion-id';

/**
 * 旧形式キーフレーム { time, angles } を新形式 { time, channel, angle } に変換
 */
function migrateKeyframes(keyframes) {
  if (!keyframes || keyframes.length === 0) return [];
  const first = keyframes[0];
  if (first.angles !== undefined) {
    const result = [];
    keyframes.forEach(kf => {
      if (kf.angles && typeof kf.angles === 'object') {
        Object.entries(kf.angles).forEach(([ch, angle]) => {
          if (angle !== undefined && angle !== null) {
            result.push({ time: kf.time, channel: parseInt(ch, 10), angle });
          }
        });
      }
    });
    return result.sort((a, b) => a.time - b.time || a.channel - b.channel);
  }
  return keyframes;
}

/**
 * ローカルストレージからモーション一覧を読み込む（旧形式は新形式に変換）
 */
export function loadMotions() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return [];
    }
    const loaded = JSON.parse(stored);
    return loaded.map(m => ({
      ...m,
      keyframes: migrateKeyframes(m.keyframes || []),
    }));
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
  0: 0, 1: 70, 2: 30, 3: -30,
  8: 0, 9: 70, 10: 30, 11: -30,
};

/**
 * 新しいモーションを作成（キーフレームは ch ごとに 1 個ずつ）
 */
export function createMotion(name = '新規モーション') {
  return {
    id: `motion-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    name: name,
    duration: DEFAULT_MOTION_DURATION,
    keyframes: SERVO_CHANNELS.map(ch => ({
      time: 0,
      channel: ch,
      angle: INITIAL_ANGLES[ch] ?? 90,
    })),
  };
}