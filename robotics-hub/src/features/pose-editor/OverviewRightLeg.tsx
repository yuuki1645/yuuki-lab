import type { JointKey } from "./poseEditorTypes";
import { hip1SpreadPx } from "./poseKinematics";
import {
  ARROW_IMAGE_BLUE,
  ARROW_IMAGE_RED,
  overviewPointerArrow,
  type OverviewLegBaseProps,
} from "./OverviewLegShared";

/**
 * オーバービュー用の右足（赤）スケッチ＋矢印ハンドル
 */
export function OverviewRightLeg({
  hipPos,
  pose,
  legLen,
  dir,
  activeDrag,
  onArrowDown,
}: OverviewLegBaseProps) {
  const stroke = "#b91c1c";
  const spread = hip1SpreadPx(pose.hip1);
  const hipX = hipPos.x + dir * spread;
  const hipY = hipPos.y;
  const footX = hipX;
  const footY = hipY + legLen;

  const isActive = (key: JointKey, axis: "x" | "y") =>
    activeDrag != null &&
    activeDrag.leg === "R" &&
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
        x={footX - 50}
        y={footY - 25}
        textAnchor="middle"
        className="pose-joint-label"
      >
        かかと {Math.round(pose.heel)}°
      </text>

      {overviewPointerArrow({
        cx: hipX - 100,
        cy: hipY + 10,
        rotDeg: 90,
        href: ARROW_IMAGE_BLUE,
        active: isActive("hip1", "x"),
        onPointerDown: (e) =>
          onArrowDown(e, {
            leg: "R",
            key: "hip1",
            axis: "x",
            sign: 1,
          }),
      })}
      {overviewPointerArrow({
        cx: footX - 33,
        cy: footY - 3,
        rotDeg: 0,
        href: ARROW_IMAGE_BLUE,
        active: isActive("hip2", "y"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg: "R", key: "hip2", axis: "y", sign: -1 }),
      })}
      {overviewPointerArrow({
        cx: footX - 10,
        cy: footY + 30,
        rotDeg: 0,
        href: ARROW_IMAGE_RED,
        active: isActive("heel", "y"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg: "R", key: "heel", axis: "y", sign: -1 }),
      })}
    </g>
  );
}
