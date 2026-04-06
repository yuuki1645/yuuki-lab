import { useState, type PointerEvent } from "react";
import type { ActiveDrag, LegPose, OverviewFace } from "./poseEditorTypes";
import { OverviewPanel } from "./OverviewPanel";

export interface PoseEditorOverviewSectionProps {
  left: LegPose;
  right: LegPose;
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
}

/** オーバービューカード（見出し・正面/背面切替・両脚 SVG） */
export function PoseEditorOverviewSection({
  left,
  right,
  activeDrag,
  onArrowDown,
}: PoseEditorOverviewSectionProps) {
  const [face, setFace] = useState<OverviewFace>("front");

  return (
    <section className="pose-card" aria-labelledby="pose-overview-heading">
      <div className="pose-overview-card-head">
        <h2 id="pose-overview-heading" className="pose-card-title">
          オーバービュー
        </h2>
        <div
          className="pose-overview-toggle"
          role="group"
          aria-label="正面・背面の切り替え"
        >
          <button
            type="button"
            className={`pose-face-btn${face === "front" ? " pose-face-btn--on" : ""}`}
            aria-pressed={face === "front"}
            onClick={() => setFace("front")}
          >
            正面
          </button>
          <button
            type="button"
            className={`pose-face-btn${face === "back" ? " pose-face-btn--on" : ""}`}
            aria-pressed={face === "back"}
            onClick={() => setFace("back")}
          >
            背面
          </button>
        </div>
      </div>
      <OverviewPanel
        left={left}
        right={right}
        face={face}
        activeDrag={activeDrag}
        onArrowDown={onArrowDown}
      />
    </section>
  );
}
