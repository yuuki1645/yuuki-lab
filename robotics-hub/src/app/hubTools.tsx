import { lazy, type ComponentType, type LazyExoticComponent } from "react";

export interface HubTool {
  id: string;
  /** URL パス（先頭スラッシュ付き・一意） */
  path: string;
  /** ナビ表示名 */
  label: string;
  /** 一覧やヘルプ用の短い説明 */
  description: string;
  /** 遅延読み込みするページコンポーネント */
  LazyPage: LazyExoticComponent<ComponentType>;
}

/**
 * ハブに載せるツール一覧。
 * 新規ツールは `src/features/<名前>/` に実装し、ここに 1 行追加する。
 */
const MotionEditorPage = lazy(() => import("@/features/motion-editor/MotionEditorPage"));
const LegServoTunerPage = lazy(() => import("@/features/leg-servo-tuner/LegServoTunerPage"));
const PoseEditorPage = lazy(() => import("@/features/pose-editor/PoseEditorPage"));

export const hubTools: HubTool[] = [
  {
    id: "motion-editor",
    path: "/motion",
    label: "モーションエディタ",
    description: "タイムラインでキーフレームを編集し、モーションを再生します。",
    LazyPage: MotionEditorPage,
  },
  {
    id: "leg-servo-tuner",
    path: "/leg-tuner",
    label: "レッグサーボ調整",
    description: "脚サーボを1本ずつ、論理角／物理角で動かして調整します。",
    LazyPage: LegServoTunerPage,
  },
  {
    id: "pose-editor",
    path: "/pose",
    label: "ポーズエディタ",
    description: "メモ風スケッチで脚の関節をドラッグし、論理角を編集します。",
    LazyPage: PoseEditorPage,
  },
];
