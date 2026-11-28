/**
 * 実機画面の右下スティック。
 * シミュの左スティックと同じく、奥だけを 0〜0.2 m/s にする。
 * 遊びの内側、手前、左右は方策へ 0。倒し切りが 0.2。
 * 0.02 m/s を超えると、腰は前進 0 の包絡を外す（walk_policy.cpp の kVxStand）。
 */

export const POLICY_STICK_DEAD_ZONE = 0.15;
export const POLICY_STICK_MAX_VX = 0.2;
export const POLICY_ENVELOPE_VX = 0.02;

export type PolicyStickCommand = {
  /** 右が +1。方策へは渡さない。点の位置だけ。 */
  x: number;
  /** 奥が +1、手前が −1。 */
  y: number;
  /** 腰へ出す前進。0〜0.2 m/s。 */
  vx: number;
  /** この速度では包絡の停止と頭打ちが外れる。 */
  envelopeOff: boolean;
};

function clampUnit(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(-1, value));
}

/** 円の中の指から、方策へ出す前進を決める。x は点の左右だけ。 */
export function policyStickCommand(x: number, y: number): PolicyStickCommand {
  const xx = clampUnit(x);
  const yy = clampUnit(y);
  // 遊びは軸ごと。境界の内側は中央とみなす。
  const yLive = Math.abs(yy) < POLICY_STICK_DEAD_ZONE ? 0 : yy;
  // 手前は負なので、ここで 0 になる。奥の倒し切りが 0.2。
  const vx = Math.min(POLICY_STICK_MAX_VX, Math.max(0, yLive * POLICY_STICK_MAX_VX));
  return {
    x: xx,
    y: yy,
    vx,
    envelopeOff: vx > POLICY_ENVELOPE_VX,
  };
}

/** USB へ出す桁。0.01 m/s 未満の揺れでは送り直さない。 */
export function quantizePolicyVx(vx: number): number {
  if (!Number.isFinite(vx) || vx <= 0) return 0;
  const stepped = Math.round(vx * 100) / 100;
  return Math.min(POLICY_STICK_MAX_VX, Math.max(0, stepped));
}
