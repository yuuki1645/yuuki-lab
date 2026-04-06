/** SVG 上の脚スティック図用の簡易 2D 幾何（見た目用。実機の運動学とは一致しない場合あり） */

export interface Vec2 {
  x: number;
  y: number;
}

export interface LegGeometry {
  hip: Vec2;
  knee: Vec2;
  ankle: Vec2;
  foot: Vec2;
  /** 膝から足先方向（単位ベクトル） */
  shinDir: Vec2;
}

const D2R = Math.PI / 180;

/**
 * 横から見た脚：HIP②・膝・かかとの論理角から関節位置を求める
 */
export function computeSideViewLeg(
  hip: Vec2,
  upperLen: number,
  lowerLen: number,
  footLen: number,
  hip2Deg: number,
  kneeDeg: number,
  heelDeg: number
): LegGeometry {
  const th = hip2Deg * D2R;
  const thighDir: Vec2 = { x: Math.sin(th), y: Math.cos(th) };
  const knee: Vec2 = {
    x: hip.x + thighDir.x * upperLen,
    y: hip.y + thighDir.y * upperLen,
  };

  const bend = Math.max(0.15, Math.min(3.0, (kneeDeg / 90) * 1.35 + 0.25));
  const shinDir: Vec2 = {
    x: Math.sin(th + Math.PI - bend),
    y: Math.cos(th + Math.PI - bend),
  };
  const ankle: Vec2 = {
    x: knee.x + shinDir.x * lowerLen,
    y: knee.y + shinDir.y * lowerLen,
  };

  const heelRad = heelDeg * D2R * 0.5;
  const footDir: Vec2 = {
    x: shinDir.x * Math.cos(heelRad) - shinDir.y * Math.sin(heelRad),
    y: shinDir.x * Math.sin(heelRad) + shinDir.y * Math.cos(heelRad),
  };
  const foot: Vec2 = {
    x: ankle.x + footDir.x * footLen,
    y: ankle.y + footDir.y * footLen,
  };

  return { hip, knee, ankle, foot, shinDir };
}

/**
 * 正面から見た脚：HIP① で左右に開く量（px）
 */
export function hip1SpreadPx(hip1Deg: number, scale = 1.2): number {
  return hip1Deg * scale;
}
