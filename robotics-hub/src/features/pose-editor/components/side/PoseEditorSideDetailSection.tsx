import { useState, type PointerEvent } from "react";
import type { Servo } from "@/shared/types";
import type { ActiveDrag, LegId, LegPose } from "../../types";
import { SideLegPanel } from "./SideLegPanel";

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

      <SideLegPanel
        leg={sideTab}
        pose={pose}
        servos={servos}
        activeDrag={activeDrag}
        onArrowDown={onArrowDown}
      />

      <dl className="pose-readout">
        <div className="pose-readout-row">
          <dt>HIP①</dt>
          <dd>{Math.round(pose.hip1)}°</dd>
        </div>
        <div className="pose-readout-row">
          <dt>HIP②</dt>
          <dd>{Math.round(pose.hip2)}°</dd>
        </div>
        <div className="pose-readout-row">
          <dt>ひざ</dt>
          <dd>{Math.round(pose.knee)}°</dd>
        </div>
        <div className="pose-readout-row">
          <dt>かかと</dt>
          <dd>{Math.round(pose.heel)}°</dd>
        </div>
        <div className="pose-readout-row">
          <dt>かかとロール</dt>
          <dd>{Math.round(pose.heelRoll)}°</dd>
        </div>
      </dl>
    </section>
  );
}
