import type { PointerEvent } from "react";
import { BlockArrowHandle } from "./BlockArrowHandle";
import { hip1SpreadPx, type Vec2 } from "./poseKinematics";
import type { ActiveDrag, JointKey, LegId, LegPose } from "./poseEditorTypes";

export interface MiniLegProps {
  hipPos: Vec2;
  leg: LegId;
  pose: LegPose;
  legLen: number;
  /** 正面/背面の左右反転（1 または -1） */
  dir: 1 | -1;
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
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
  const stroke = leg === "L" ? "#1d4ed8" : "#b91c1c";
  const spread = hip1SpreadPx(pose.hip1);
  const hipX = hipPos.x + dir * (leg === "L" ? -spread : spread);
  const hipY = hipPos.y;
  const footX = hipX;
  const footY = hipY + legLen;

  const isActive = (key: JointKey, axis: "x" | "y") =>
    activeDrag != null &&
    activeDrag.leg === leg &&
    activeDrag.key === key &&
    activeDrag.axis === axis;

  return (
    <g>
      <line
        x1={hipX}
        y1={hipY}
        x2={footX}
        y2={footY}
        stroke={stroke}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle
        cx={hipX}
        cy={hipY}
        r={6}
        fill="#fefcf6"
        stroke={stroke}
        strokeWidth="2"
      />
      <circle
        cx={footX}
        cy={footY}
        r={6}
        fill="#fefcf6"
        stroke={stroke}
        strokeWidth="2"
      />

      <text
        x={hipX}
        y={hipY - 10}
        textAnchor="middle"
        className="pose-joint-label"
      >
        HIP① {Math.round(pose.hip1)}°
      </text>
      <text
        x={footX}
        y={footY + 22}
        textAnchor="middle"
        className="pose-joint-label"
      >
        かかと {Math.round(pose.heel)}°
      </text>

      <BlockArrowHandle
        cx={hipX - 34}
        cy={hipY + 10}
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
      <BlockArrowHandle
        cx={hipX + 36}
        cy={hipY + 10}
        r={30}
        rotDeg={90}
        color="#b91c1c"
        active={isActive("hip2", "y")}
        onPointerDown={(e) =>
          onArrowDown(e, { leg, key: "hip2", axis: "y", sign: -1 })
        }
      />
      <BlockArrowHandle
        cx={footX - 28}
        cy={footY - 4}
        r={30}
        rotDeg={90}
        color="#b91c1c"
        active={isActive("heel", "y")}
        onPointerDown={(e) =>
          onArrowDown(e, { leg, key: "heel", axis: "y", sign: -1 })
        }
      />
    </g>
  );
}
