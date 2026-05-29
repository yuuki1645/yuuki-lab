/**
 * biped_ppo_v1 観測契約の UI 定義（Python ``contract/biped_v1.py`` と同期）。
 * 表示順・telemetry_key は契約の ObservationSlice と同一にする。
 */

import { GYRO_LABELS, ZAXIS_LABELS } from "./telemetryUi";
import type { TrainingTelemetryBipedObsFields } from "@/shared/types/trainingTelemetry";

export const BIPED_PPO_V1_OBS_DIM = 42;

export type BipedObsFieldKey = keyof TrainingTelemetryBipedObsFields;

export type BipedObsUiSlice =
  | {
      id: string;
      title: string;
      description: string;
      kind: "scalar";
      field: BipedObsFieldKey;
      label: string;
      valueHeader?: string;
    }
  | {
      id: string;
      title: string;
      description: string;
      kind: "vector";
      field: BipedObsFieldKey;
      labels: string[];
      valueHeader?: string;
      /** rad/s 受信を deg/s 表示 */
      gyroRadToDeg?: boolean;
      /** 行ラベルに actuator_names を使う（10 関節） */
      useActuatorLabels?: boolean;
    };

/** 契約 ``_BIPED_OBS_SLICES`` と同順 */
export const BIPED_PPO_V1_OBS_UI_SLICES: BipedObsUiSlice[] = [
  {
    id: "obs_dx",
    title: "obs_dx",
    description: "IMU +X 移動量（正規化）",
    kind: "scalar",
    field: "obs_dx",
    label: "+X 移動量",
    valueHeader: "正規化",
  },
  {
    id: "obs_imu_gyro",
    title: "obs_imu_gyro",
    description: "IMU 角速度 rad/s（正規化）→ deg/s 表示",
    kind: "vector",
    field: "obs_imu_gyro",
    labels: [...GYRO_LABELS],
    valueHeader: "deg/s",
    gyroRadToDeg: true,
  },
  {
    id: "obs_imu_zaxis",
    title: "obs_imu_zaxis",
    description: "IMU 上向き単位ベクトル",
    kind: "vector",
    field: "obs_imu_zaxis",
    labels: [...ZAXIS_LABELS],
    valueHeader: "単位ベクトル",
  },
  {
    id: "obs_imu_z_norm",
    title: "obs_imu_z_norm",
    description: "IMU 高さ（正規化）",
    kind: "scalar",
    field: "obs_imu_z_norm",
    label: "高さ norm",
    valueHeader: "正規化",
  },
  {
    id: "obs_left_foot_contact",
    title: "obs_left_foot_contact",
    description: "左足接地 ±1",
    kind: "scalar",
    field: "obs_left_foot_contact",
    label: "左足接地",
    valueHeader: "±1",
  },
  {
    id: "obs_right_foot_contact",
    title: "obs_right_foot_contact",
    description: "右足接地 ±1",
    kind: "scalar",
    field: "obs_right_foot_contact",
    label: "右足接地",
    valueHeader: "±1",
  },
  {
    id: "obs_left_foot_dx",
    title: "obs_left_foot_dx",
    description: "左足 +X 移動量（正規化）",
    kind: "scalar",
    field: "obs_left_foot_dx",
    label: "左足 +X dx",
    valueHeader: "正規化",
  },
  {
    id: "obs_right_foot_dx",
    title: "obs_right_foot_dx",
    description: "右足 +X 移動量（正規化）",
    kind: "scalar",
    field: "obs_right_foot_dx",
    label: "右足 +X dx",
    valueHeader: "正規化",
  },
  {
    id: "obs_joint_q_norm",
    title: "obs_joint_q_norm",
    description: "関節角 q（正規化）×10",
    kind: "vector",
    field: "obs_joint_q_norm",
    labels: [],
    valueHeader: "正規化 [-1,1]",
    useActuatorLabels: true,
  },
  {
    id: "obs_joint_qvel_norm",
    title: "obs_joint_qvel_norm",
    description: "関節角速度（正規化）×10",
    kind: "vector",
    field: "obs_joint_qvel_norm",
    labels: [],
    valueHeader: "正規化",
    useActuatorLabels: true,
  },
  {
    id: "obs_prev_action_norm",
    title: "obs_prev_action_norm",
    description: "直前 action [-1,1]×10",
    kind: "vector",
    field: "obs_prev_action_norm",
    labels: [],
    valueHeader: "正規化 [-1,1]",
    useActuatorLabels: true,
  },
];

export function bipedObsSliceDim(slice: BipedObsUiSlice): number {
  if (slice.kind === "scalar") return 1;
  if (slice.useActuatorLabels) return 10;
  return slice.labels.length;
}

export const BIPED_PPO_V1_OBS_UI_DIM = BIPED_PPO_V1_OBS_UI_SLICES.reduce(
  (sum, s) => sum + bipedObsSliceDim(s),
  0
);
