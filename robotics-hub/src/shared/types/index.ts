/** キーフレーム */
export interface Keyframe {
  id: string;
  time: number;
  channel: number;
  angle: number;
}

/** モーション */
export interface Motion {
  id: string;
  name: string;
  duration: number;
  keyframes: Keyframe[];
}

/** サーボ情報（API から取得した形式） */
export interface Servo {
  name: string;
  ch: number;
  logical_lo: number;
  logical_hi: number;
  physical_min: number;
  physical_max: number;
  last_logical: number;
  /** 物理角。MuJoCo 状態の変換で埋める */
  last_physical: number;
}

/** サーボ制御モード。モーション再生は logical だけを MuJoCo へ送る */
export type ServoMode = "logical" | "physical";
