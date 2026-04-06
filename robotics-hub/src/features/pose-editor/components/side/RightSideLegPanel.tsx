import {
  SideLegPanelCore,
  type SideLegPanelBaseProps,
} from "./SideLegPanelCore";

/** 右足・側面スケッチパネル */
export function RightSideLegPanel(props: SideLegPanelBaseProps) {
  return <SideLegPanelCore leg="R" {...props} />;
}

export type { SideLegPanelBaseProps as RightSideLegPanelProps };
