// サーボ名から部位キーを取得（R_KNEE -> KNEE）
export function partKeyFromServoName(name: string): string {
  const parts = String(name).split("_");
  return parts.length >= 2 ? parts.slice(1).join("_") : String(name);
}

// 角度を範囲内にクランプ
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
