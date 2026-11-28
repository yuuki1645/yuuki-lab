/** Shapes returned by /api/lab. Null is a gap, not zero. */

export type LabDay = {
  day: string;
  take_count: number;
};

export type LabDaysResponse = {
  root: string;
  available: boolean;
  days: LabDay[];
};

export type LabTakeMeta = {
  day: string;
  take_id: string;
  format_id: string | null;
  /** "robot" is a real take. "sim" is an Isaac Lab playback. */
  side: string;
  /** Experiment name from context.json. Empty on a real take. */
  name: string | null;
  day_index: number | null;
  started_at: string | null;
  ended_at: string | null;
  started_unix: number | null;
  ended_unix: number | null;
  recording: boolean;
  notes: string;
  hello: string | null;
  port: string | null;
  fw_ver: number | null;
  sample_count: number | null;
  /** Policy rows in policy/. Null on core_take_v1. */
  policy_count: number | null;
  stop_reason: string | null;
  duration_sec: number | null;
  open_parts: string[];
  supported: boolean;
};

export type LabTakesResponse = {
  day: string;
  takes: LabTakeMeta[];
};

/** 0 ok, 1 info / no data, 2 warn, 3 crit. */
export type Severity = 0 | 1 | 2 | 3;

/** One merged run of flagged rows. Offsets are seconds since the first row. */
export type LabInterval = {
  start_index: number;
  end_index: number;
  start_offset: number;
  end_offset: number;
  count: number;
  severity: number;
  peak_value: number | null;
  peak_index: number;
  peak_offset: number;
};

export type LabFindingDetail = {
  /** AS5600 STATUS code -> rows. */
  mag?: Record<string, number>;
  dropped_total?: number;
  i2c_total?: number;
  corners?: Record<string, number>;
  texts?: string[];
  /** Joints that were warn/crit for this share of the finding's rows. */
  related?: Array<{ joint: number; ratio: number }>;
  /** Joints named in event lines during the finding. */
  mentioned?: Array<{ joint: number; count: number }>;
  median_deg?: number;
  samples?: number;
  stop_reason?: string;
};

/** All flags of one kind on one lane (joint or system row). */
export type LabFinding = {
  id: string;
  kind: string;
  lane: string;
  joint: number | null;
  severity: number;
  sample_count: number;
  ratio: number;
  first_offset: number;
  last_offset: number;
  peak_value: number | null;
  peak_index: number;
  peak_offset: number;
  interval_count: number;
  periodic_sec: number | null;
  detail: LabFindingDetail;
  intervals: LabInterval[];
};

/** One health map row: per equal-time bucket worst severity, its kind and bad share. */
export type LabHealthLane = {
  id: string;
  joint: number | null;
  sev: number[];
  /** Index into LabAnalysis.kinds; 0 = nothing. */
  kind: number[];
  ratio: number[];
  /** Share of rows with this axis's PWM enabled (joint lanes only). */
  out?: Array<number | null>;
};

export type LabHealth = {
  buckets: number;
  bucket_sec: number;
  /** Rows per bucket. 0 means nothing was received there. */
  samples: number[];
  lanes: LabHealthLane[];
  overview: {
    amp_total_max?: Array<number | null>;
    err_driven_max?: Array<number | null>;
  };
};

export type LabTracking = {
  samples: number;
  median_deg: number | null;
  mean_abs_deg: number | null;
  p95_abs_deg: number | null;
  max_abs_deg: number | null;
  max_index: number | null;
  off_mean_abs_deg: number | null;
};

export type LabPower = {
  amp_mean: number | null;
  amp_p99: number | null;
  amp_max: number | null;
  amp_max_index: number | null;
  volt_powered_median: number | null;
  volt_powered_min: number | null;
  volt_sag_samples: number;
  watt_max: number | null;
};

export type LabJointStats = {
  index: number;
  name: string;
  online_ratio: number | null;
  as_ok_ratio: number | null;
  dropout_samples: number;
  mag_counts: Record<string, number>;
  agc_min: number | null;
  agc_median: number | null;
  agc_max: number | null;
  out_ratio: number | null;
  jump_count: number;
  tracking: LabTracking;
  power: LabPower;
  crit: number;
  warn: number;
};

export type LabSystemStats = {
  rate_hz: number | null;
  target_period_us: number | null;
  period_mean_us: number | null;
  period_std_us: number | null;
  period_p99_us: number | null;
  period_max_us: number | null;
  loop_p99_us: number | null;
  loop_max_us: number | null;
  sense_median_us: number | null;
  sense_max_us: number | null;
  jitter_abs_p99_us: number | null;
  overrun_count: number;
  seq_drop_events: number;
  seq_dropped_total: number;
  seq_drop_periodic_sec: number | null;
  seq_resets: number;
  rx_gap_count: number;
  rx_gap_max_sec: number | null;
  dt_median_ms: number | null;
  dt_p99_ms: number | null;
  dt_max_ms: number | null;
  i2c_start: number | null;
  i2c_end: number | null;
  i2c_delta: number | null;
  i2c_max_per_sec: number | null;
  servo_ok_ratio: number | null;
  foot_ok_ratio: number | null;
  foot_left_ok_ratio: number | null;
  modes: string[];
};

export type LabEventLevel = "error" | "warn" | "info";

/** Event screen line moved onto the take time axis. */
export type LabMarkerEvent = {
  offset: number | null;
  text: string;
  level: LabEventLevel;
  joint: number | null;
};

/** PC -> board command (CMD, OUT, MODE, POLICY, PING ...). */
export type LabCommand = {
  offset: number;
  text: string;
  ch?: number;
  deg?: number;
  on?: boolean;
  mode?: string;
  /** POLICY rows: whether the network was enabled, and the forward command. */
  enable?: boolean;
  vx?: number;
};

export type LabAnalysis = {
  day: string;
  take_id: string;
  meta: LabTakeMeta;
  tail_pending: boolean;
  /** UNIX seconds of the first row; offsets are relative to this. */
  t0: number;
  duration_sec: number;
  sample_count: number;
  parts_read: number;
  thresholds: Record<string, number>;
  kinds: string[];
  lanes: string[];
  joint_names: string[];
  health: LabHealth;
  findings: LabFinding[];
  joint_stats: LabJointStats[];
  system_stats: LabSystemStats;
  /** Per joint: [start, end] offsets where its PWM output was on. */
  out_spans: number[][][];
  events: LabMarkerEvent[];
  events_total: number;
  commands: LabCommand[];
  commands_total: number;
  /**
   * Counts from gamepad/part-*.jsonl itself. Null when that folder was
   * absent. accepted_* is native rows, not the 0/1 series on the charts.
   */
  gamepad: LabGamepadSummary | null;
  /**
   * Counts from policy/part-*.jsonl itself. Null when that folder was absent
   * (every core_take_v1 take). Chart channels are folded onto sensor time.
   */
  policy: LabPolicySummary | null;
  /** Contract copied into the take. Null when there is no context.json. */
  context: LabTakeContext | null;
};

/** Native policy totals. reason_counts keys are the firmware's reason codes. */
export type LabPolicySummary = {
  samples: number;
  rate_hz: number | null;
  start_offset: number | null;
  end_offset: number | null;
  action_rows: number;
  overrun_count: number;
  reason_counts: Record<string, number>;
  safety_counts: Record<string, number>;
  /** "sim" when the chart axis is cumulative simulator steps, not wall clock. */
  clock?: string | null;
  sim_sec?: number | null;
};

/** Excerpt of context.json: learning run plus the number-to-name tables. */
export type LabTakeContext = {
  learn_run: string | null;
  checkpoint: string | null;
  robot: string | null;
  /** Playback experiment name. Null on a real take. */
  experiment: string | null;
  task: string | null;
  side: string | null;
  action_scale: number;
  envelope_rad: number;
  /** Screen degrees of straight down, per logical axis. RDS 135, SM105 0. */
  upright_deg?: number[];
  /** Logical axis -> index in the policy arrays. -1 when that axis is absent. */
  policy_of_fw: number[];
  /** Servo model per logical axis. SM105BL has no AS5600 and no INA226. */
  servos?: string[];
  enums: {
    reason?: Record<string, string>;
    safety?: Record<string, string>;
    joint_flag?: Record<string, string>;
  };
};

/** Native gamepad totals. Bursts are contiguous runs of accepted rows. */
export type LabGamepadSummary = {
  samples: number;
  rate_hz: number | null;
  start_offset: number | null;
  end_offset: number | null;
  stick_rows: number;
  accepted_left: number;
  accepted_right: number;
  accepted_left_runs: number;
  accepted_right_runs: number;
};

/** Last gamepad row at or before a sensor sample. Null before the pad starts. */
export type LabGamepadSample = {
  t: number;
  t_offset: number;
  part: string;
  line: number;
  raw_line: string | null;
  row: Record<string, unknown> | null;
};

/** raw: v per row. envelope: min/max/mean per equal-time bucket. */
export type LabWindowSeries = {
  v?: Array<number | null>;
  min?: Array<number | null>;
  max?: Array<number | null>;
  mean?: Array<number | null>;
};

export type LabWindow = {
  from: number;
  to: number;
  channels: string[];
  sample_count: number;
  mode: "raw" | "envelope";
  t: number[];
  /** Sample index per row (raw) or first index per bucket (envelope). */
  index: Array<number | null>;
  bucket_sec?: number;
  series: Record<string, LabWindowSeries>;
};

export type LabRangeStat = {
  n: number;
  missing: number;
  min?: number | null;
  min_index?: number;
  min_offset?: number;
  max?: number | null;
  max_index?: number;
  max_offset?: number;
  mean?: number | null;
  std?: number | null;
  p05?: number | null;
  p50?: number | null;
  p95?: number | null;
  first?: number | null;
  last?: number | null;
  delta?: number | null;
};

export type LabRangeStats = {
  from: number;
  to: number;
  start_index: number;
  end_index: number;
  sample_count: number;
  rate_hz: number | null;
  stats: Record<string, LabRangeStat>;
};

export type LabRows = {
  channels: string[];
  start: number;
  end: number;
  total: number;
  index: number[];
  t: number[];
  seq: Array<number | null>;
  series: Record<string, Array<number | null>>;
};

/** One sensor row exactly as stored, plus where it lives and its flags. */
export type LabSample = {
  index: number;
  total: number;
  t: number;
  t_offset: number;
  part: string;
  line: number;
  /** The row's exact text in its part file. */
  raw_line: string | null;
  row: Record<string, unknown> | null;
  flags: Record<string, { sev: number; kind: string }>;
  gamepad: LabGamepadSample | null;
  /** Nearest policy row. Null on v1, and when nothing is close to this sensor time. */
  policy: LabPolicySample | null;
};

/** One policy row, the file's own line, nearest to a sensor sample. */
export type LabPolicySample = {
  t: number;
  t_offset: number;
  part: string;
  line: number;
  raw_line: string | null;
  row: Record<string, unknown> | null;
};
