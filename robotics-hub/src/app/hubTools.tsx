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
const DaemonSocketTestPage = lazy(
  () => import("@/features/daemon-socket-test/DaemonSocketTestPage")
);
const DeviceTelemetryPage = lazy(() => import("@/features/telemetry/DeviceTelemetryPage"));
const TrainingTelemetryPage = lazy(
  () => import("@/features/telemetry/TrainingTelemetryPage")
);
const DataViewerPage = lazy(() => import("@/features/data-viewer/DataViewerPage"));
const MujocoViewerAuxPage = lazy(() => import("@/features/mujoco-viewer-aux/MujocoViewerAuxPage"));
const IsaacRlLogPage = lazy(() => import("@/features/isaac-rl-log/IsaacRlLogPage"));

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
  {
    id: "daemon-socket-test",
    path: "/daemon-socket-test",
    label: "Daemon Socket Test",
    description: "robot-daemon との Socket.IO 通信を確認します。",
    LazyPage: DaemonSocketTestPage,
  },
  {
    id: "device-telemetry",
    path: "/device-telemetry",
    label: "実機テレメトリ",
    description: "robot-daemon の実機 IMU をリアルタイム表示し、CSV ログを操作します。",
    LazyPage: DeviceTelemetryPage,
  },
  {
    id: "training-telemetry",
    path: "/training-telemetry",
    label: "学習テレメトリ",
    description:
      "強化学習（mujoco_rl_sim）の観測・行動・報酬を Socket.IO（rl_telemetry/*）で表示します。",
    LazyPage: TrainingTelemetryPage,
  },
  {
    id: "data-viewer",
    path: "/data-viewer",
    label: "データビュワー",
    description:
      "IMU / サーボの CSV と動画を wall_unix で突き合わせ、シーク位置のログを確認します。",
    LazyPage: DataViewerPage,
  },
  {
    id: "mujoco-viewer-aux",
    path: "/mujoco-viewer-aux",
    label: "MuJoCo ビュワー補助",
    description:
      "mujoco_test_009 と連携し、パッシブ viewer の状態をリアルタイム表示し、再生・リセット・表示オプションを操作します。",
    LazyPage: MujocoViewerAuxPage,
  },
  {
    id: "isaac-rl-log",
    path: "/isaac-rl-log",
    label: "Isaac 学習進捗",
    description:
      "test-isaac-project の TensorBoard ログを読み取り、平均報酬・エピソード長などの学習曲線を PC / スマホで表示します。",
    LazyPage: IsaacRlLogPage,
  },
];
