import type { Keyframe } from "@/shared/types";

/**
 * 線形補間
 */
export function lerp(start: number, end: number, t: number): number {
  return start + (end - start) * t;
}

/**
 * 指定チャンネルのキーフレームのみを時間順に取得
 */
function keyframesForChannel(keyframes: Keyframe[], channel: number): Keyframe[] {
  return keyframes
    .filter((kf) => kf.channel === channel)
    .sort((a, b) => a.time - b.time);
}

/**
 * 指定時間以前で、指定チャンネルの最後のキーフレームを探す
 */
function findPreviousKeyframe(
  keyframes: Keyframe[],
  time: number,
  channel: number
): Keyframe | null {
  const list = keyframesForChannel(keyframes, channel);
  const prev = list.filter((kf) => kf.time <= time);
  return prev.length > 0 ? prev[prev.length - 1]! : null;
}

/**
 * 指定時間以降で、指定チャンネルの最初のキーフレームを探す
 */
function findNextKeyframe(
  keyframes: Keyframe[],
  time: number,
  channel: number
): Keyframe | null {
  const list = keyframesForChannel(keyframes, channel);
  return list.find((kf) => kf.time >= time) ?? null;
}

/**
 * 指定時間の角度を計算（キーフレーム形式: { time, channel, angle }）
 */
export function getAngleAtTime(
  keyframes: Keyframe[],
  time: number,
  allChannels: number[] | null = null
): Record<number, number> {
  if (!keyframes || keyframes.length === 0) {
    return {};
  }

  const channels =
    allChannels ?? [...new Set(keyframes.map((kf) => kf.channel))];
  const result: Record<number, number> = {};

  for (const channel of channels) {
    const prevKf = findPreviousKeyframe(keyframes, time, channel);
    const nextKf = findNextKeyframe(keyframes, time, channel);

    if (prevKf && nextKf) {
      if (prevKf.time === nextKf.time) {
        result[channel] = prevKf.angle;
      } else {
        const timeDiff = nextKf.time - prevKf.time;
        const t = (time - prevKf.time) / timeDiff;
        const clampedT = Math.max(0, Math.min(1, t));
        result[channel] = lerp(prevKf.angle, nextKf.angle, clampedT);
      }
    } else if (prevKf) {
      result[channel] = prevKf.angle;
    } else if (nextKf) {
      result[channel] = nextKf.angle;
    } else {
      result[channel] = 90;
    }
  }

  return result;
}
