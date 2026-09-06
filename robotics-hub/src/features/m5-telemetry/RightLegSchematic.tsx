import { SERVO_NEUTRAL_DEG, type RightLegJointId } from "./rightLeg";

type Angles = Partial<Record<RightLegJointId, number | null | undefined>>;

type Props = {
  angles: Angles;
  selected: RightLegJointId | null;
  onSelect: (id: RightLegJointId) => void;
};

function vis(servo: number | null | undefined, scale: number): number {
  if (typeof servo !== "number" || !Number.isFinite(servo)) return 0;
  return ((servo - SERVO_NEUTRAL_DEG) * scale * Math.PI) / 180;
}

function bone(
  x: number,
  y: number,
  len: number,
  dir: number
): { x: number; y: number } {
  return { x: x + len * Math.sin(dir), y: y + len * Math.cos(dir) };
}

/**
 * 右脚の側面テクニカル図。アルミ C チャネルとサーボ箱、足裏プレート。
 * 角度は補正角があればそれを使い、見栄え用に中立 135° から少しだけ動かす。
 */
export function RightLegSchematic({ angles, selected, onSelect }: Props) {
  const hipShift =
    typeof angles.hipRoll === "number" && Number.isFinite(angles.hipRoll)
      ? (angles.hipRoll - SERVO_NEUTRAL_DEG) * 0.16
      : 0;
  const hipX = 108 + hipShift;
  const hipY = 108;
  const thighDir = vis(angles.hipPitch, 0.42);
  const knee = bone(hipX, hipY, 168, thighDir);
  const shinDir = thighDir + vis(angles.kneePitch, 0.55);
  const ankle = bone(knee.x, knee.y, 152, shinDir);
  const footDir = shinDir + vis(angles.anklePitch, 0.4);
  const roll = vis(angles.ankleRoll, 0.5);

  const footHalf = 46;
  const footT = 11;
  const fx = Math.cos(footDir);
  const fy = -Math.sin(footDir);
  const nx = Math.sin(footDir);
  const ny = Math.cos(footDir);
  const heel = { x: ankle.x - fx * footHalf, y: ankle.y - fy * footHalf };
  const toe = { x: ankle.x + fx * footHalf, y: ankle.y + fy * footHalf };
  // かかとロールは足裏を法線方向に少しひねる
  const twist = Math.sin(roll) * 7;
  const plate = [
    `${heel.x + nx * (footT / 2 + twist)},${heel.y + ny * (footT / 2 + twist)}`,
    `${toe.x + nx * (footT / 2 - twist)},${toe.y + ny * (footT / 2 - twist)}`,
    `${toe.x - nx * (footT / 2 - twist)},${toe.y - ny * (footT / 2 - twist)}`,
    `${heel.x - nx * (footT / 2 + twist)},${heel.y - ny * (footT / 2 + twist)}`,
  ].join(" ");

  const shinMid = {
    x: (knee.x + ankle.x) / 2,
    y: (knee.y + ankle.y) / 2,
  };

  return (
    <svg className="m5-leg-svg" viewBox="0 0 220 640" role="img" aria-label="右脚概略図">
      <defs>
        <linearGradient id="m5-metal" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#3d4a58" />
          <stop offset="45%" stopColor="#c5d0dc" />
          <stop offset="100%" stopColor="#5b6774" />
        </linearGradient>
        <linearGradient id="m5-basket" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f2f4f7" />
          <stop offset="100%" stopColor="#9aa3ad" />
        </linearGradient>
        <filter id="m5-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* 吊りカゴ */}
      <g className="m5-leg-basket">
        <rect x="48" y="10" width="124" height="52" rx="4" fill="url(#m5-basket)" stroke="#6d7782" strokeWidth="1.4" />
        <path d="M60 18 h100 M60 28 h100 M60 38 h88" stroke="#b8c0c8" strokeWidth="1.2" />
        <line x1="78" y1="62" x2={hipX - 10} y2={hipY - 18} stroke="#3ee07f" strokeWidth="3.2" strokeLinecap="round" />
        <line x1="142" y1="62" x2={hipX + 10} y2={hipY - 18} stroke="#3ee07f" strokeWidth="3.2" strokeLinecap="round" />
      </g>

      <Channel x1={hipX} y1={hipY} x2={knee.x} y2={knee.y} />
      <Channel x1={knee.x} y1={knee.y} x2={ankle.x} y2={ankle.y} />

      <polygon points={plate} fill="#8b97a6" stroke="#d7dee6" strokeWidth="1.6" />
      <line
        x1={heel.x}
        y1={heel.y}
        x2={toe.x}
        y2={toe.y}
        stroke="#e8eef4"
        strokeWidth="1.1"
        opacity="0.45"
      />

      <ServoBox x={hipX} y={hipY} dir={thighDir} />
      <ServoBox x={knee.x} y={knee.y} dir={shinDir} />
      <ServoBox x={ankle.x} y={ankle.y} dir={footDir} />

      {/* すねの ATOM */}
      <g transform={`translate(${shinMid.x - 9} ${shinMid.y - 9}) rotate(${(-shinDir * 180) / Math.PI} 9 9)`}>
        <rect width="18" height="18" rx="2" fill="#1a222c" stroke="#6ee7ff" strokeWidth="1.2" />
        <circle cx="9" cy="9" r="2.2" fill="#6ee7ff" />
      </g>

      <JointNode
        id="hipRoll"
        cx={hipX - 16}
        cy={hipY - 16}
        r={9}
        selected={selected}
        onSelect={onSelect}
      />
      <JointNode id="hipPitch" cx={hipX} cy={hipY} r={11} selected={selected} onSelect={onSelect} />
      <JointNode id="kneePitch" cx={knee.x} cy={knee.y} r={11} selected={selected} onSelect={onSelect} />
      <JointNode id="anklePitch" cx={ankle.x} cy={ankle.y} r={11} selected={selected} onSelect={onSelect} />
      <JointNode
        id="ankleRoll"
        cx={ankle.x + nx * 18}
        cy={ankle.y + ny * 18}
        r={8}
        selected={selected}
        onSelect={onSelect}
      />
    </svg>
  );
}

function Channel({ x1, y1, x2, y2 }: { x1: number; y1: number; x2: number; y2: number }) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const px = (-dy / len) * 8;
  const py = (dx / len) * 8;
  return (
    <g>
      <polygon
        points={`${x1 + px},${y1 + py} ${x2 + px},${y2 + py} ${x2 - px},${y2 - py} ${x1 - px},${y1 - py}`}
        fill="url(#m5-metal)"
        stroke="#9aa7b5"
        strokeWidth="1.1"
      />
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#1c232c" strokeWidth="1.4" opacity="0.55" />
    </g>
  );
}

function ServoBox({ x, y, dir }: { x: number; y: number; dir: number }) {
  const deg = (-dir * 180) / Math.PI;
  return (
    <g transform={`translate(${x} ${y}) rotate(${deg})`}>
      <rect x="-16" y="-11" width="32" height="22" rx="2.5" fill="#141a22" stroke="#8896a6" strokeWidth="1.2" />
      <rect x="-11" y="-7" width="14" height="14" rx="1" fill="#2a3340" />
    </g>
  );
}

function JointNode({
  id,
  cx,
  cy,
  r,
  selected,
  onSelect,
}: {
  id: RightLegJointId;
  cx: number;
  cy: number;
  r: number;
  selected: RightLegJointId | null;
  onSelect: (id: RightLegJointId) => void;
}) {
  const on = selected === id;
  return (
    <g
      className={"m5-leg-joint" + (on ? " m5-leg-joint--on" : "")}
      onClick={() => onSelect(id)}
      style={{ cursor: "pointer" }}
      filter={on ? "url(#m5-glow)" : undefined}
    >
      <circle cx={cx} cy={cy} r={r + 3} fill={on ? "rgba(247,201,72,0.22)" : "transparent"} />
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="#0e1318"
        stroke={on ? "#f7c948" : "#d5deea"}
        strokeWidth={on ? 2.6 : 1.8}
      />
      <circle cx={cx} cy={cy} r={3.1} fill={on ? "#f7c948" : "#7f8b99"} />
    </g>
  );
}
