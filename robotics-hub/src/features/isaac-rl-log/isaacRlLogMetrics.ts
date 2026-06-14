/** TensorBoard scalar tag → 表示用ラベル・説明・チャート色 */

export interface IsaacRlMetricDef {
  tag: string;
  label: string;
  /** サマリーカード用の短いラベル（未指定時は label） */
  labelShort?: string;
  description?: string;
  color: string;
  /** サマリーカードに出すか */
  summary?: boolean;
  /** 値の小数桁 */
  decimals?: number;
  /** primary=大きいチャート、secondary=折りたたみ可能 */
  tier: "primary" | "secondary";
}

export const ISAAC_RL_METRICS: IsaacRlMetricDef[] = [
  {
    tag: "Train/mean_reward",
    label: "平均報酬",
    description: "1 エピソードあたりの合計報酬（iter 内に終了した ep の平均）",
    color: "#6ea8ff",
    summary: true,
    decimals: 1,
    tier: "primary",
  },
  {
    tag: "Train/mean_episode_length",
    label: "エピソード長",
    description: "平均エピソード step 数（長いほど転倒せずに立てている）",
    color: "#7ee787",
    summary: true,
    decimals: 0,
    tier: "primary",
  },
  {
    tag: "Reward/mean_forward",
    label: "前進報酬 (step)",
    labelShort: "前進報酬",
    description: "1 制御 step あたりの forward 報酬（rollout 平均）",
    color: "#ffa657",
    summary: true,
    decimals: 3,
    tier: "primary",
  },
  {
    tag: "Policy/mean_noise_std",
    label: "探索ノイズ σ",
    description: "Actor の action std 平均（大きすぎると方策がランダム化）",
    color: "#d2a8ff",
    summary: true,
    decimals: 3,
    tier: "primary",
  },
  {
    tag: "Reward/mean_effort",
    label: "effort 報酬",
    description: "effort ペナルティ項（enable_effort=False なら 0 付近）",
    color: "#8b949e",
    decimals: 4,
    tier: "secondary",
  },
  {
    tag: "Loss/surrogate",
    label: "PPO surrogate loss",
    color: "#f85149",
    decimals: 4,
    tier: "secondary",
  },
  {
    tag: "Loss/value_function",
    label: "Value loss",
    color: "#79c0ff",
    decimals: 4,
    tier: "secondary",
  },
  {
    tag: "Loss/entropy",
    label: "Entropy",
    color: "#a5d6ff",
    decimals: 4,
    tier: "secondary",
  },
  {
    tag: "Perf/total_fps",
    label: "総 FPS",
    description: "学習スループット",
    color: "#3fb950",
    decimals: 0,
    tier: "secondary",
  },
];

export const ISAAC_RL_METRIC_BY_TAG: Record<string, IsaacRlMetricDef> = Object.fromEntries(
  ISAAC_RL_METRICS.map((m) => [m.tag, m])
);

export const ISAAC_RL_PRIMARY_TAGS = ISAAC_RL_METRICS.filter((m) => m.tier === "primary").map((m) => m.tag);

/** 20 秒ごとに Hub 画面を更新（要件） */
export const ISAAC_RL_LOG_POLL_MS = 20_000;

export const LS_ISAAC_RL_LOG_API = "rh.isaacRlLogApiUrl";
