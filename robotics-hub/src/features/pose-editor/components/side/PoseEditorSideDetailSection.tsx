import { useState, type PointerEvent } from "react";
import type { Servo } from "@/shared/types";
import type { ActiveDrag, LegId, LegPose } from "../../types";
import { LeftSideLegPanel } from "./LeftSideLegPanel";
import { RightSideLegPanel } from "./RightSideLegPanel";
import { SideLegPoseReadout } from "./SideLegPoseReadout";

export interface PoseEditorSideDetailSectionProps {
  readout: { L: LegPose; R: LegPose };
  servos: Servo[];
  activeDrag: ActiveDrag | null;
  onArrowDown: (
    e: PointerEvent,
    partial: Omit<ActiveDrag, "startClient" | "startAngle">
  ) => void;
}

/** 詳細（横ビュー）カード：足タブ・側面 SVG・数値リードアウト */
export function PoseEditorSideDetailSection({
  readout,
  servos,
  activeDrag,
  onArrowDown,
}: PoseEditorSideDetailSectionProps) {
  const [sideTab, setSideTab] = useState<LegId>("L");
  const pose = sideTab === "L" ? readout.L : readout.R;

  return (
    <section className="pose-card" aria-labelledby="pose-side-heading">
      <div className="pose-side-head">
        <h2 id="pose-side-heading" className="pose-card-title">
          詳細（横から）
        </h2>
        <div className="pose-tabs" role="tablist" aria-label="足の選択">
          <button
            type="button"
            role="tab"
            aria-selected={sideTab === "L"}
            className={`pose-tab${sideTab === "L" ? " pose-tab--on" : ""}`}
            onClick={() => setSideTab("L")}
          >
            左足（青）
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={sideTab === "R"}
            className={`pose-tab${sideTab === "R" ? " pose-tab--on" : ""}`}
            onClick={() => setSideTab("R")}
          >
            右足（赤）
          </button>
        </div>
      </div>

      {sideTab === "L" ? (
        <LeftSideLegPanel
          pose={readout.L}
          servos={servos}
          activeDrag={activeDrag}
          onArrowDown={onArrowDown}
        />
      ) : (
        <RightSideLegPanel
          pose={readout.R}
          servos={servos}
          activeDrag={activeDrag}
          onArrowDown={onArrowDown}
        />
      )}

      <SideLegPoseReadout pose={pose} />
    </section>
  );
}
