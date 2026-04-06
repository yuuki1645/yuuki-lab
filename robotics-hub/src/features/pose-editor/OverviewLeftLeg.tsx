import type { JointKey } from "./poseEditorTypes";
import { hip1SpreadPx } from "./poseKinematics";
import {
  ARROW_IMAGE_BLUE,
  ARROW_IMAGE_RED,
  overviewPointerArrow,
  type OverviewLegBaseProps,
} from "./OverviewLegShared";

/**
 * オーバービュー用の左足（青）スケッチ＋矢印ハンドル
 */
export function OverviewLeftLeg({
  hipPos,
  pose,
  legLen,
  dir,
  activeDrag,
  onArrowDown,
}: OverviewLegBaseProps) {
  const stroke = "#1d4ed8";
  const spread = hip1SpreadPx(pose.hip1);
  const hipX = hipPos.x;
  const hipY = hipPos.y;

  const isActive = (key: JointKey, axis: "x" | "y") =>
    activeDrag != null &&
    activeDrag.leg === "L" &&
    activeDrag.key === key &&
    activeDrag.axis === axis;

  const logicalHip1 = pose.hip1;
  const footX = hipX - legLen * Math.sin(logicalHip1 * Math.PI / 180);
  const footY = hipY + legLen * Math.cos(logicalHip1 * Math.PI / 180);

  const logicalHeelRoll = pose.heelRoll;
  console.log("logicalHeelRoll", logicalHeelRoll);
  
  const soleWidth = 50;
  const soleX1 = footX - (soleWidth / 2) * Math.cos((logicalHip1 + logicalHeelRoll) * Math.PI / 180);
  const soleY1 = footY - (soleWidth / 2) * Math.sin((logicalHip1 + logicalHeelRoll) * Math.PI / 180);
  const soleX2 = footX + (soleWidth / 2) * Math.cos((logicalHip1 + logicalHeelRoll) * Math.PI / 180);
  const soleY2 = footY + (soleWidth / 2) * Math.sin((logicalHip1 + logicalHeelRoll) * Math.PI / 180);

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
      <line
        x1={soleX1}
        y1={soleY1}
        x2={soleX2}
        y2={soleY2}
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
        x={footX - 50}
        y={footY - 25}
        textAnchor="middle"
        className="pose-joint-label"
      >
        かかと {Math.round(pose.heelRoll)}°
      </text>

      {overviewPointerArrow({
        cx: hipX - 100,
        cy: hipY + 150,
        rotDeg: 41,
        href: ARROW_IMAGE_BLUE,
        active: isActive("hip1", "x"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg: "L", key: "heelRoll", axis: "y" }),
      })}
      {/* {overviewPointerArrow({
        cx: footX - 33,
        cy: footY - 3,
        rotDeg: 0,
        href: ARROW_IMAGE_BLUE,
        active: isActive("hip2", "y"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg: "L", key: "hip2", axis: "y", sign: -1 }),
      })} */}
      {overviewPointerArrow({
        cx: footX - 10,
        cy: footY + 30,
        rotDeg: 0,
        href: ARROW_IMAGE_RED,
        active: isActive("heel", "y"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg: "L", key: "hip1", axis: "x" }),
      })}
    </g>
  );
}
