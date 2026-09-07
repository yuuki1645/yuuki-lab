import RobotTakeV0Viewer from "@/features/lab-data-viewer/formats/robot_take_v0/RobotTakeV0Viewer";
import type { LabFormatEntry } from "@/features/lab-data-viewer/types";

/** format_id → サブビュワー。未登録なら resolveLabFormat は null。 */
const LAB_FORMAT_REGISTRY: Record<string, LabFormatEntry> = {
  robot_take_v0: {
    format_id: "robot_take_v0",
    Viewer: RobotTakeV0Viewer,
  },
};

export function resolveLabFormat(formatId: string | null | undefined): LabFormatEntry | null {
  if (!formatId) return null;
  return LAB_FORMAT_REGISTRY[formatId] ?? null;
}
