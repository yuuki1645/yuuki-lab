import type { ComponentType } from "react";
import type { RecorderTakeDescription } from "@/shared/recorderApi";

/**
 * format_id 別サブビュワーの props。
 * recorderBaseUrl は相対パス（/data/...）の先頭に付ける。
 */
export type LabFormatViewerProps = {
  take: RecorderTakeDescription;
  recorderBaseUrl: string;
};

export type LabFormatEntry = {
  format_id: string;
  Viewer: ComponentType<LabFormatViewerProps>;
};
