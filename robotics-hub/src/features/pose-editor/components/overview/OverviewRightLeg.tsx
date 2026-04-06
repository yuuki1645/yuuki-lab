import type { JointKey } from "../../types";
import {
  ARROW_IMAGE_BLUE,
  ARROW_IMAGE_RED,
  overviewPointerArrow,
  type OverviewLegBaseProps,
} from "./OverviewLegShared";

/**
 * オーバービュー用の右足（赤）スケッチ＋矢印ハンドル
 * （OverviewLeftLeg と対称。正面視図で X 方向とドラッグ符号を反転）
 */
export function OverviewRightLeg({
  hipPos,
  pose,
  legLen,
  dir: _dir,
  activeDrag,
  onArrowDown,
}: OverviewLegBaseProps) {
  void _dir;
  const stroke = "#b91c1c";
  const hipX = hipPos.x;
  const hipY = hipPos.y;

  const isActive = (key: JointKey, axis: "x" | "y") =>
    activeDrag != null &&
    activeDrag.leg === "R" &&
    activeDrag.key === key &&
    activeDrag.axis === axis;

  const logicalHip1 = pose.hip1;
  /** 左足は hipX - L*sin(θ)。右足は鏡映で + */
  const footX = hipX + legLen * Math.sin((logicalHip1 * Math.PI) / 180);
  const footY = hipY + legLen * Math.cos((logicalHip1 * Math.PI) / 180);

  const logicalHeelRoll = pose.heelRoll;

  const soleWidth = 50;
  const α = ((logicalHip1 + logicalHeelRoll) * Math.PI) / 180;
  /** 足裏線分：左足の ± を左右反転 */
  const soleX1 = footX - (soleWidth / 2) * Math.cos(α);
  const soleY1 = footY + (soleWidth / 2) * Math.sin(α);
  const soleX2 = footX + (soleWidth / 2) * Math.cos(α);
  const soleY2 = footY - (soleWidth / 2) * Math.sin(α);

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
        x={footX + 50}
        y={footY - 25}
        textAnchor="middle"
        className="pose-joint-label"
      >
        かかと {Math.round(pose.heelRoll)}°
      </text>

      {overviewPointerArrow({
        cx: hipX + 100,
        cy: hipY + 150,
        rotDeg: -41,
        href: ARROW_IMAGE_BLUE,
        active: isActive("heelRoll", "y"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg: "R", key: "heelRoll", axis: "y", sign: -1 }),
      })}
      {overviewPointerArrow({
        cx: footX + 10,
        cy: footY + 30,
        rotDeg: 0,
        href: ARROW_IMAGE_RED,
        active: isActive("hip1", "x"),
        onPointerDown: (e) =>
          onArrowDown(e, { leg: "R", key: "hip1", axis: "x", sign: 1 }),
      })}
    </g>
  );
}
