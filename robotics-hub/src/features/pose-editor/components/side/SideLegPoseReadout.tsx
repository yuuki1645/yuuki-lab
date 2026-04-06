import type { LegPose } from "../../types";

export interface SideLegPoseReadoutProps {
  pose: LegPose;
}

/** 側面ビューで選択中の脚の論理角（度）一覧 */
export function SideLegPoseReadout({ pose }: SideLegPoseReadoutProps) {
  return (
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
  );
}
