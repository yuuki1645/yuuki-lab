import { hip1SpreadPx, type Vec2 } from "./poseKinematics";
import type { ActiveDrag, JointKey, LegId, LegPose } from "./poseEditorTypes";

/** オーバービュー用：太い軸＋台形矢印のブロック矢印（右向きが 0°） */
function BlockArrowHandle(props: {
  cx: number;
  cy: number;
  r: number;
  rotDeg: number;
  color: string;
  active: boolean;
  onPointerDown: (e: React.PointerEvent) => void;
}) {
  const { cx, cy, r, rotDeg, color, active, onPointerDown } = props;
  const d =
    "M -26 -7 L 10 -7 L 10 -13 L 30 0 L 10 13 L 10 7 L -26 7 Z";
  return (
    <g
      className={`pose-arrow-handle pose-arrow-handle--block${active ? " pose-arrow-handle--active" : ""}`}
      transform={`translate(${cx} ${cy}) rotate(${rotDeg})`}
      onPointerDown={onPointerDown}
    >
      <circle r={r} className="pose-arrow-hit" />
      <path
        d={d}
        fill={color}
        stroke="#1a1a1a"
        strokeWidth="1.1"
        strokeLinejoin="round"
        opacity="0.95"
        style={{ filter: "url(#pose-wobble)" }}
      />
    </g>
  );
}

export interface MiniLegProps {
  hipPos: Vec2;
  cx: number;
  leg: LegId;
  pose: LegPose;
  /** 股関節の Y（SVG 座標） */
  hipY: number;
  /** 股関節の Y（SVG 座標） */
  hipY: number;
  legLen: number;
  /** 正面/背面の左右反転（1 または -1） */
  dir: 1 | -1;
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: React.PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
}

/**
 * オーバービュー用の簡略脚（縦1本＋股・足先のマーク）
 */
export function MiniLeg({
  hipPos,
  leg,
  pose,
  legLen,
  dir,
  activeDrag,
  onArrowDown,
}: MiniLegProps) {
  const stroke = leg === "R" ? "red" : "blue";
  const spread = hip1SpreadPx(pose.hip1);

  const isActive = (key: JointKey, axis: "x" | "y") =>
    activeDrag != null &&
    activeDrag.leg === leg &&
    activeDrag.key === key &&
    activeDrag.axis === axis;

  return (
    <g>
      <line
        x1={hipPos.x} y1={hipPos.y}
        x2={hipPos.x} y2={hipPos.y + 200}
        stroke={stroke}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle
        cx={hipPos.x}
        cy={hipPos.y}
        r={6}
        fill="#fefcf6"
        stroke={stroke}
        strokeWidth="2"
      />
      {/* <circle cx={fx} cy={fy} r={6} fill="#fefcf6" stroke={stroke} strokeWidth="2" />

      <text x={hipX} y={hipY - 10} textAnchor="middle" className="pose-joint-label">
        HIP① {Math.round(pose.hip1)}°
      </text>
      <text x={fx} y={fy + 22} textAnchor="middle" className="pose-joint-label">
        かかと {Math.round(pose.heel)}°
      </text> */}

      <BlockArrowHandle
        cx={hipPos.x - 34}
        cy={hipPos.y + 10}
        r={30}
        rotDeg={90}
        color="#1d4ed8"
        active={isActive("hip1", "x")}
        onPointerDown={(e) =>
          onArrowDown(e, {
            leg,
            key: "hip1",
            axis: "x",
            sign: leg === "L" ? -1 : 1,
          })
        }
      />
      {/*
      <BlockArrowHandle
        cx={hipX + 36}
        cy={hipY + 10}
        rotDeg={90}
        r={30}
        color="#b91c1c"
        active={isActive("hip2", "y")}
        onPointerDown={(e) =>
          onArrowDown(e, { leg, key: "hip2", axis: "y", sign: -1 })
        }
      />
      <BlockArrowHandle
        cx={fx - 28}
        cy={fy - 4}
        rotDeg={90}
        r={30}
        color="#b91c1c"
        active={isActive("heel", "y")}
        onPointerDown={(e) =>
          onArrowDown(e, { leg, key: "heel", axis: "y", sign: -1 })
        }
      /> */}
    </g>
  );
}
