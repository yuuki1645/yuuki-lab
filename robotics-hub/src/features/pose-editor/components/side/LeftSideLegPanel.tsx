import {
  SideLegPanelCore,
  type SideLegPanelBaseProps,
} from "./SideLegPanelCore";

/** 左足・側面スケッチパネル */
export function LeftSideLegPanel(props: SideLegPanelBaseProps) {
  return <SideLegPanelCore leg="L" {...props} />;
}

export type { SideLegPanelBaseProps as LeftSideLegPanelProps };
