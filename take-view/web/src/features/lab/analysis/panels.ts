/**
 * Which plots the workbench shows and what goes on each: channels,
 * colours, threshold lines and which findings are painted as bands.
 *
 * Two layouts:
 *  - joint mode: every signal of one axis, stacked on a shared time axis
 *  - compare mode: one metric for all ten axes on one plot, so the odd
 *    joint out stands out at a glance
 */

import { L } from "../labels";
import { JOINT_COLORS, SEV_COLOR } from "./canvas";
import type { AngleDisplay } from "./screenAngle";

export type LineStyle = "line" | "step" | "bar";

export type PlotLine = {
  key: string;
  label: string;
  color: string;
  style?: LineStyle;
  dash?: number[];
};

/**
 * One row of a state strip (categorical, e.g. sensor ok / magnet status).
 * ``worst`` picks which end of a min/max bucket represents it when zoomed
 * out: "min" for ok flags (any false wins), "max" for status codes.
 */
export type StateRow = {
  key: string;
  label: string;
  worst: "min" | "max";
  color: (value: number) => string | null;
  /**
   * Verdict channel (``j<N>.sev``). Where it says "no data" the row is
   * painted grey, so a leg that is simply not connected yet does not look
   * like a sensor failure.
   */
  gate?: string;
};

export type PlotRef = { y: number; color: string; label: string };

export type PanelId =
  | "status"
  | "angle"
  | "err"
  | "amp"
  | "volt"
  | "agc"
  | "link"
  | "counters"
  | "foot"
  | "cop"
  | "padStick"
  | "padState"
  | "padHeel"
  | "compare"
  | "compareStatus"
  | "polState"
  | "polJoint"
  | "polClip"
  | "polGrav"
  | "polGyro"
  | "polFoot"
  | "polCmd"
  | "polAge"
  | "polTime"
  | "polSense";

export type PanelSpec = {
  id: PanelId;
  title: string;
  unit: string;
  height: number;
  lines: PlotLine[];
  states?: StateRow[];
  refs?: PlotRef[];
  yFixed?: [number, number];
  digits: number;
  /**
   * Joint angles in this panel's series are still radians from upright.
   * "screen" draws the servo's own degrees (RDS 135 at straight down, SM105 0).
   * "delta" draws a difference in degrees and does not add that offset.
   * Reference lines are in the same radians and are converted with the series.
   */
  angle?: AngleDisplay;
  /** Findings painted as background bands: their lanes and kinds. */
  bandLanes: string[];
  bandKinds: string[] | "all";
  /** Draw command ticks for this joint (angle panel). */
  commandJoint?: number;
  /** Dim rows where this joint's output was off (tracking error is meaningless there). */
  dimWhenOutOff?: number;
};

export type CompareMetric = "err" | "corr" | "raw" | "amp" | "volt" | "agc";

export const COMPARE_METRICS: ReadonlyArray<{ id: CompareMetric; label: string; unit: string; digits: number }> = [
  { id: "err", label: L.mErr, unit: L.deg, digits: 2 },
  { id: "corr", label: L.mCorr, unit: L.deg, digits: 2 },
  { id: "raw", label: L.mRaw, unit: L.deg, digits: 2 },
  { id: "amp", label: L.mAmp, unit: "A", digits: 3 },
  { id: "volt", label: L.mVolt, unit: "V", digits: 3 },
  { id: "agc", label: L.mAgc, unit: "", digits: 0 },
];

/** Panels the user can toggle in joint mode, with the default visibility. */
export const JOINT_PANEL_CHOICES: ReadonlyArray<{ id: PanelId; label: string; on: boolean }> = [
  { id: "status", label: L.pStatus, on: true },
  { id: "angle", label: L.pAngle, on: true },
  { id: "err", label: L.pErr, on: true },
  { id: "amp", label: L.pAmp, on: true },
  { id: "volt", label: L.pVolt, on: false },
  { id: "agc", label: L.pAgc, on: false },
  { id: "link", label: L.pLink, on: true },
  { id: "counters", label: L.pCounters, on: true },
  { id: "foot", label: L.pFoot, on: true },
  { id: "cop", label: L.pCop, on: false },
  { id: "padStick", label: L.pPadStick, on: true },
  { id: "padState", label: L.pPadState, on: true },
  { id: "padHeel", label: L.pPadHeel, on: true },
];

const OK_FILL = "rgba(61, 220, 132, 0.45)";
const BAD_FILL = "rgba(255, 92, 92, 0.95)";
const WARN_FILL = "rgba(255, 176, 32, 0.9)";
const OUT_FILL = "rgba(77, 166, 255, 0.8)";
/** Grey for rows where the verdict is "no data" (leg offline, not started). */
export const NODATA_FILL = "rgba(127, 142, 163, 0.35)";

/** Detector verdict: 0 ok, 1 no data, 2 warn, 3 crit. */
function sevColor(value: number): string | null {
  if (value >= 3) return BAD_FILL;
  if (value >= 2) return WARN_FILL;
  if (value >= 1) return NODATA_FILL;
  return OK_FILL;
}

/** Flag rows: 1 is healthy, 0 is a failure. A gap stays unpainted. */
function flagColor(value: number): string | null {
  if (value >= 1) return OK_FILL;
  if (value <= 0) return BAD_FILL;
  return null;
}

/** AS5600 STATUS: 0 ok, 1 no magnet, 2 weak, 3 strong, 4 I2C failure. */
function magColor(value: number): string | null {
  if (value === 0) return OK_FILL;
  if (value === 2 || value === 3) return WARN_FILL;
  if (value === 1 || value === 4) return BAD_FILL;
  return null;
}

function outColor(value: number): string | null {
  return value >= 1 ? OUT_FILL : null;
}

/** Pad activity (homing, accepted, floor hold). Off stays unpainted. */
function activeColor(value: number): string | null {
  return value >= 1 ? OUT_FILL : null;
}

const WARN_REF = SEV_COLOR[2];
const CRIT_REF = SEV_COLOR[3];

/** Threshold lines for corr - cmd, centred on the joint's usual offset. */
function errRefs(th: Record<string, number>, median: number | null): PlotRef[] {
  const centre = median ?? 0;
  const refs: PlotRef[] = [
    { y: centre + th.track_warn_deg, color: WARN_REF, label: L.refWarn },
    { y: centre - th.track_warn_deg, color: WARN_REF, label: L.refWarn },
    { y: centre + th.track_crit_deg, color: CRIT_REF, label: L.refCrit },
    { y: centre - th.track_crit_deg, color: CRIT_REF, label: L.refCrit },
  ];
  if (median != null) refs.push({ y: median, color: "#9aadc4", label: L.refMedian });
  return refs;
}

/** System panels shared by both layouts. */
function systemPanels(th: Record<string, number>): PanelSpec[] {
  return [
    {
      id: "link",
      title: L.pLink,
      unit: "ms",
      height: 120,
      lines: [{ key: "sys.dt_ms", label: L.sDt, color: "#4dd0e1" }],
      refs: [
        { y: th.rx_gap_warn_sec * 1000, color: WARN_REF, label: L.refWarn },
        { y: th.rx_gap_crit_sec * 1000, color: CRIT_REF, label: L.refCrit },
      ],
      digits: 1,
      bandLanes: ["link", "timing"],
      bandKinds: "all",
    },
    {
      id: "counters",
      title: L.pCounters,
      unit: "",
      height: 110,
      lines: [
        { key: "sys.seq_gap", label: L.sSeqGap, color: "#ff6b6b", style: "bar" },
        { key: "sys.i2c_delta", label: L.sI2c, color: "#ffb020", style: "bar" },
      ],
      digits: 0,
      bandLanes: ["i2c"],
      bandKinds: "all",
    },
  ];
}

/** Every signal of one axis, plus link health and the feet. */
export function jointPanels(
  joint: number,
  th: Record<string, number>,
  medianErr: number | null,
  showRaw: boolean,
  feedback = false
): PanelSpec[] {
  const j = `j${joint}`;
  const angleLines: PlotLine[] = [
    { key: `${j}.cmd`, label: L.sCmd, color: "#4da6ff", style: "step" },
    { key: `${j}.corr`, label: L.sCorr, color: "#ffb454" },
  ];
  if (showRaw) angleLines.push({ key: `${j}.raw`, label: L.sRaw, color: "#8a99ad", dash: [4, 3] });
  const [link, counters] = systemPanels(th);
  const panels: PanelSpec[] = [
    {
      id: "status",
      title: L.pStatus,
      unit: "",
      height: 112,
      lines: [],
      states: feedback
        ? [
            { key: `${j}.sev`, label: L.stVerdict, worst: "max" as const, color: sevColor },
            { key: `${j}.as_ok`, label: L.stServo, worst: "min" as const, color: flagColor, gate: `${j}.sev` },
            { key: `${j}.out`, label: L.stOut, worst: "max" as const, color: outColor },
          ]
        : [
            { key: `${j}.sev`, label: L.stVerdict, worst: "max" as const, color: sevColor },
            { key: `${j}.as_ok`, label: L.stAsOk, worst: "min" as const, color: flagColor, gate: `${j}.sev` },
            { key: `${j}.mag`, label: L.stMag, worst: "max" as const, color: magColor, gate: `${j}.sev` },
            { key: `${j}.map_ok`, label: L.stMap, worst: "min" as const, color: flagColor, gate: `${j}.sev` },
            { key: `${j}.ina_ok`, label: L.stIna, worst: "min" as const, color: flagColor, gate: `${j}.sev` },
            { key: `${j}.out`, label: L.stOut, worst: "max" as const, color: outColor },
          ],
      digits: 0,
      bandLanes: [j],
      bandKinds: feedback ? ["servo_fb", "nodata"] : ["dropout", "magnet", "no_map", "nodata"],
    },
    {
      id: "angle",
      title: L.pAngle,
      unit: L.deg,
      height: 210,
      lines: angleLines,
      digits: 2,
      bandLanes: [j],
      bandKinds: ["dropout", "servo_fb", "jump", "tracking", "nodata"],
      commandJoint: joint,
    },
    {
      id: "err",
      title: L.pErr,
      unit: L.deg,
      height: 150,
      lines: [{ key: `${j}.err`, label: L.sErr, color: "#ff8a65" }],
      refs: errRefs(th, medianErr),
      digits: 2,
      bandLanes: [j],
      bandKinds: ["tracking"],
      dimWhenOutOff: joint,
    },
    {
      id: "amp",
      title: L.pAmp,
      unit: "A",
      height: 130,
      lines: [{ key: `${j}.amp`, label: L.sAmp, color: "#ffd166" }],
      refs: [
        { y: th.amp_warn, color: WARN_REF, label: L.refWarn },
        { y: th.amp_crit, color: CRIT_REF, label: L.refCrit },
      ],
      digits: 3,
      bandLanes: [j],
      bandKinds: ["overcurrent"],
    },
    {
      id: "volt",
      title: L.pVolt,
      unit: "V",
      height: 120,
      lines: [{ key: `${j}.volt`, label: L.sVolt, color: "#7dcea0" }],
      digits: 3,
      bandLanes: [j],
      bandKinds: ["undervolt"],
    },
    {
      id: "agc",
      title: L.pAgc,
      unit: "",
      height: 110,
      lines: [{ key: `${j}.agc`, label: L.sAgc, color: "#b48ef0", style: "step" }],
      digits: 0,
      bandLanes: [j],
      bandKinds: ["magnet"],
    },
    link,
    counters,
    {
      id: "foot",
      title: L.pFoot,
      unit: L.kg,
      height: 130,
      lines: [
        { key: "foot.force_kg", label: L.sForceR, color: "#7dcea0" },
        { key: "foot_left.force_kg", label: L.sForceL, color: "#ff7a7a" },
      ],
      digits: 3,
      bandLanes: ["foot", "foot_left"],
      bandKinds: "all",
    },
    {
      id: "cop",
      title: L.pCop,
      unit: "",
      height: 120,
      lines: [
        { key: "foot.cop_x", label: L.sCopRx, color: "#7dcea0" },
        { key: "foot.cop_y", label: L.sCopRy, color: "#5ad1d1", dash: [4, 3] },
        { key: "foot_left.cop_x", label: L.sCopLx, color: "#ff7a7a" },
        { key: "foot_left.cop_y", label: L.sCopLy, color: "#f08ac8", dash: [4, 3] },
      ],
      yFixed: [-1.05, 1.05],
      digits: 3,
      bandLanes: [],
      bandKinds: [],
    },
  ];
  // No magnet and no INA226 on this servo, so those charts would be empty on purpose.
  if (!feedback) return panels;
  return panels.filter((panel) => panel.id !== "amp" && panel.id !== "volt" && panel.id !== "agc");
}

const COMPARE_KINDS: Record<CompareMetric, string[]> = {
  err: ["tracking"],
  corr: ["dropout", "jump"],
  raw: ["dropout", "jump"],
  amp: ["overcurrent"],
  volt: ["undervolt"],
  agc: ["magnet"],
};

/** One metric across all ten axes, the encoder state of each, and link health. */
export function comparePanels(
  metric: CompareMetric,
  th: Record<string, number>,
  jointNames: readonly string[]
): PanelSpec[] {
  const info = COMPARE_METRICS.find((item) => item.id === metric) ?? COMPARE_METRICS[0];
  const lanes = Array.from({ length: 10 }, (_, joint) => `j${joint}`);
  const [link, counters] = systemPanels(th);
  return [
    {
      id: "compare",
      title: info.label,
      unit: info.unit,
      height: 280,
      lines: lanes.map((lane, joint) => ({
        key: `${lane}.${metric}`,
        label: `${joint} ${jointNames[joint] ?? ""}`,
        color: JOINT_COLORS[joint],
      })),
      digits: info.digits,
      bandLanes: lanes,
      bandKinds: COMPARE_KINDS[metric],
    },
    {
      id: "compareStatus",
      title: L.pCompareStatus,
      unit: "",
      height: 150,
      lines: [],
      states: lanes.map((lane, joint) => ({
        key: `${lane}.sev`,
        label: `${joint} ${jointNames[joint] ?? ""}`,
        worst: "max" as const,
        color: sevColor,
      })),
      digits: 0,
      bandLanes: [],
      bandKinds: [],
    },
    link,
    counters,
  ];
}

const PAD_LEFT = "#ff7a7a";
const PAD_LEFT_2 = "#f08ac8";
const PAD_LEFT_3 = "#ffb454";
const PAD_RIGHT = "#7dcea0";
const PAD_RIGHT_2 = "#5ad1d1";
const PAD_RIGHT_3 = "#9ad07d";

/**
 * Gamepad on the sensor time axis.
 *
 * Shown only when the take has a gamepad folder. Accepted rows are 1 when
 * any pad sample in that sensor interval advanced the heel. The header
 * count is the native row total, which is larger when several pad rows
 * share one sensor row.
 */
export function padPanels(showRaw: boolean): PanelSpec[] {
  const stick: PlotLine[] = [
    { key: "pad.l_forward", label: L.sPadLForward, color: PAD_LEFT },
    { key: "pad.l_lateral", label: L.sPadLLateral, color: PAD_LEFT_2, dash: [4, 3] },
    { key: "pad.l_vertical", label: L.sPadLVertical, color: PAD_LEFT_3, dash: [2, 2] },
    { key: "pad.r_forward", label: L.sPadRForward, color: PAD_RIGHT },
    { key: "pad.r_lateral", label: L.sPadRLateral, color: PAD_RIGHT_2, dash: [4, 3] },
    { key: "pad.r_vertical", label: L.sPadRVertical, color: PAD_RIGHT_3, dash: [2, 2] },
  ];
  if (showRaw) {
    stick.push(
      { key: "pad.l_raw_forward", label: L.sPadLRawForward, color: PAD_LEFT, dash: [1, 2] },
      { key: "pad.l_raw_lateral", label: L.sPadLRawLateral, color: PAD_LEFT_2, dash: [1, 2] },
      { key: "pad.r_raw_forward", label: L.sPadRRawForward, color: PAD_RIGHT, dash: [1, 2] },
      { key: "pad.r_raw_lateral", label: L.sPadRRawLateral, color: PAD_RIGHT_2, dash: [1, 2] }
    );
  }
  return [
    {
      id: "padStick",
      title: L.pPadStick,
      unit: "",
      height: 160,
      lines: stick,
      yFixed: [-1.05, 1.05],
      digits: 3,
      bandLanes: [],
      bandKinds: [],
    },
    {
      id: "padState",
      title: L.pPadState,
      unit: "",
      height: 112,
      lines: [],
      states: [
        { key: "pad.connected", label: L.stPadConnected, worst: "min", color: flagColor },
        { key: "pad.homing", label: L.stPadHoming, worst: "max", color: activeColor },
        { key: "pad.l_accepted", label: L.stPadAcceptL, worst: "max", color: activeColor },
        { key: "pad.r_accepted", label: L.stPadAcceptR, worst: "max", color: activeColor },
        { key: "pad.l_floor", label: L.stPadFloorL, worst: "max", color: activeColor },
        { key: "pad.r_floor", label: L.stPadFloorR, worst: "max", color: activeColor },
      ],
      digits: 0,
      bandLanes: [],
      bandKinds: [],
    },
    {
      id: "padHeel",
      title: L.pPadHeel,
      unit: "m",
      height: 150,
      lines: [
        { key: "pad.l_heel_x", label: L.sPadHeelLx, color: PAD_LEFT },
        { key: "pad.l_heel_y", label: L.sPadHeelLy, color: PAD_LEFT_2, dash: [4, 3] },
        { key: "pad.l_heel_z", label: L.sPadHeelLz, color: PAD_LEFT_3, dash: [2, 2] },
        { key: "pad.r_heel_x", label: L.sPadHeelRx, color: PAD_RIGHT },
        { key: "pad.r_heel_y", label: L.sPadHeelRy, color: PAD_RIGHT_2, dash: [4, 3] },
        { key: "pad.r_heel_z", label: L.sPadHeelRz, color: PAD_RIGHT_3, dash: [2, 2] },
      ],
      digits: 4,
      bandLanes: [],
      bandKinds: [],
    },
  ];
}

const POL_OK = "rgba(61, 220, 132, 0.55)";

/** reason: 1 running is healthy, 0 is simply off, anything else is a stop. */
function reasonColor(value: number): string | null {
  if (value === 1) return POL_OK;
  if (value === 0) return NODATA_FILL;
  if (value === 8) return WARN_FILL;
  if (value >= 2) return BAD_FILL;
  return null;
}

/** safety: 0 is none (unpainted). 1 and 2 are the limiter, 3 holds the target. */
function safetyColor(value: number): string | null {
  if (value <= 0) return null;
  if (value === 1 || value === 2) return WARN_FILL;
  return BAD_FILL;
}

/** joint_flag: 0 valid, 1 missing, 2 jump, 3 shake. */
function policyFlagColor(value: number): string | null {
  if (value === 0) return POL_OK;
  if (value === 1) return NODATA_FILL;
  if (value >= 2) return WARN_FILL;
  return null;
}

/** 1 paints, 0 stays empty, so a "true" stretch is visible on its own. */
function onColor(value: number): string | null {
  return value >= 1 ? POL_OK : null;
}

function badOnColor(value: number): string | null {
  return value >= 1 ? BAD_FILL : null;
}

/**
 * Policy mode. Every series is already on the sensor clock, and ``p<N>``
 * is the logical axis (not the policy file's left/right order).
 *
 * Joint series are still radians from upright in the window data.
 * polJoint and polClip set `angle` so the plot draws screen degrees.
 */
export function policyPanels(joint: number, envelope: number, sensorOverlay = true): PanelSpec[] {
  const p = `p${joint}`;
  const j = `j${joint}`;
  const footLines: PlotLine[] = [
    { key: "foot_left.force_kg", label: L.sForceL, color: PAD_LEFT },
    { key: "foot.force_kg", label: L.sForceR, color: PAD_RIGHT },
    { key: "pf.l_tl", label: L.sFootLtl, color: "#ff8a80", dash: [3, 2] },
    { key: "pf.l_tr", label: L.sFootLtr, color: "#ffab91", dash: [3, 2] },
    { key: "pf.l_bl", label: L.sFootLbl, color: "#f48fb1", dash: [1, 2] },
    { key: "pf.l_br", label: L.sFootLbr, color: "#ce93d8", dash: [1, 2] },
    { key: "pf.r_tl", label: L.sFootRtl, color: "#80cbc4", dash: [3, 2] },
    { key: "pf.r_tr", label: L.sFootRtr, color: "#a5d6a7", dash: [3, 2] },
    { key: "pf.r_bl", label: L.sFootRbl, color: "#9fa8da", dash: [1, 2] },
    { key: "pf.r_br", label: L.sFootRbr, color: "#90caf9", dash: [1, 2] },
  ];
  return [
    {
      id: "polState",
      title: L.pPolState,
      unit: "",
      height: 132,
      lines: [],
      states: [
        { key: "pol.reason", label: L.stReason, worst: "max", color: reasonColor },
        { key: "pol.safety", label: L.stSafety, worst: "max", color: safetyColor },
        { key: `${p}.flag`, label: L.stPolFlag, worst: "max", color: policyFlagColor },
        { key: "pol.bearing", label: L.stBearing, worst: "max", color: onColor },
        { key: "pol.dist", label: L.stDist, worst: "max", color: onColor },
        { key: "pol.overrun", label: L.stPolOver, worst: "max", color: badOnColor },
      ],
      digits: 0,
      bandLanes: ["policy", `j${joint}`],
      bandKinds: ["policy_safety", "policy_reason", "policy_flag"],
    },
    {
      id: "polJoint",
      title: L.pPolJoint,
      unit: L.deg,
      angle: "screen",
      height: 220,
      lines: [
        { key: `${p}.obs`, label: L.sObs, color: "#ffb454" },
        // A playback has no encoder, so the sensor overlays would be an empty legend.
        ...(sensorOverlay
          ? [{ key: `${j}.corr_rad`, label: L.sCorrRad, color: "#ffb454", dash: [4, 3] as number[] }]
          : []),
        { key: `${p}.action_rad`, label: L.sActionRad, color: "#b48ef0" },
        { key: `${p}.cmd_rad`, label: L.sPolCmd, color: "#4da6ff", style: "step" as const },
        ...(sensorOverlay
          ? [{ key: `${j}.cmd_rad`, label: L.sSensCmd, color: "#4da6ff", dash: [4, 3] as number[] }]
          : []),
      ],
      refs: [
        { y: envelope, color: WARN_REF, label: L.refWarn },
        { y: -envelope, color: WARN_REF, label: L.refWarn },
      ],
      digits: 1,
      bandLanes: [`j${joint}`],
      bandKinds: ["policy_diverge", "policy_clip", "policy_flag", "sim_envelope"],
    },
    {
      id: "polClip",
      title: L.pPolClip,
      unit: L.deg,
      angle: "delta",
      height: 120,
      lines: [{ key: `${p}.clip`, label: L.sClip, color: "#ff8a65" }],
      refs: [{ y: 0, color: "#9aadc4", label: L.refMedian }],
      digits: 1,
      bandLanes: [`j${joint}`],
      bandKinds: ["policy_clip"],
    },
    {
      id: "polGrav",
      title: L.pPolGrav,
      unit: "",
      height: 140,
      lines: [
        { key: "imu.gx", label: L.sGx, color: "#ef9a9a" },
        { key: "imu.gy", label: L.sGy, color: "#a5d6a7" },
        { key: "imu.gz", label: L.sGz, color: "#90caf9" },
        { key: "imu.gmag", label: L.sGmag, color: "#b0bec5", dash: [3, 2] },
      ],
      refs: [{ y: -1, color: "#9aadc4", label: L.refUprightG }],
      yFixed: [-1.35, 1.35],
      digits: 3,
      bandLanes: ["policy"],
      bandKinds: ["policy_reason", "sim_tilt"],
    },
    {
      id: "polGyro",
      title: L.pPolGyro,
      unit: L.rad,
      height: 120,
      lines: [
        { key: "imu.wx", label: L.sWx, color: "#ef9a9a" },
        { key: "imu.wy", label: L.sWy, color: "#a5d6a7" },
        { key: "imu.wz", label: L.sWz, color: "#90caf9" },
      ],
      digits: 3,
      bandLanes: ["policy"],
      bandKinds: ["sim_tilt"],
    },
    {
      id: "polFoot",
      title: L.pPolFoot,
      unit: L.kg,
      height: 150,
      lines: sensorOverlay ? footLines : footLines.slice(2),
      digits: 3,
      bandLanes: ["foot", "foot_left"],
      bandKinds: ["foot_saturated"],
    },
    {
      id: "polCmd",
      title: L.pPolCmd,
      unit: "",
      height: 130,
      lines: [
        { key: "pol.phase_sin", label: L.sPhaseSin, color: "#4dd0e1" },
        { key: "pol.phase_cos", label: L.sPhaseCos, color: "#4da6ff", dash: [4, 3] },
        { key: "pol.vx", label: L.sVx, color: "#ffb454" },
        { key: "pol.yaw", label: L.sYaw, color: "#b48ef0", dash: [4, 3] },
      ],
      yFixed: [-1.2, 1.2],
      digits: 3,
      bandLanes: [],
      bandKinds: [],
    },
    {
      id: "polAge",
      title: L.pPolAge,
      unit: "ms",
      height: 110,
      lines: [
        { key: `${p}.age`, label: L.stPolFlag, color: "#ffb454" },
        { key: "pol.age_imu", label: L.sAgeImu, color: "#4da6ff" },
        { key: "pol.age_foot", label: L.sAgeFoot, color: "#7dcea0" },
      ],
      refs: [{ y: 100, color: WARN_REF, label: L.refWarn }],
      digits: 0,
      bandLanes: [`j${joint}`, "policy"],
      bandKinds: ["policy_stale"],
    },
    {
      id: "polTime",
      title: L.pPolTime,
      unit: "\u00b5s",
      height: 120,
      lines: [
        { key: "pol.period_us", label: L.sPolPeriod, color: "#4dd0e1" },
        { key: "pol.policy_us", label: L.sPolInfer, color: "#b48ef0" },
      ],
      digits: 0,
      bandLanes: ["policy"],
      bandKinds: ["policy_safety"],
    },
    {
      // Sensor-read time is often longer than the loop, so it gets its own scale.
      id: "polSense",
      title: L.sPolSense,
      unit: "\u00b5s",
      height: 100,
      lines: [{ key: "pol.sense_us", label: L.sPolSense, color: "#ffb454" }],
      digits: 0,
      bandLanes: [],
      bandKinds: [],
    },
  ];
}

/** Channels for the data table in policy mode, one logical axis plus the body. */
export function policyTableChannels(joint: number): string[] {
  const p = `p${joint}`;
  const j = `j${joint}`;
  return [
    "pol.reason",
    "pol.safety",
    "pol.bearing",
    "pol.dist",
    `${p}.obs`,
    `${p}.action_rad`,
    `${p}.cmd_rad`,
    `${p}.clip`,
    `${p}.flag`,
    `${p}.age`,
    `${j}.corr_rad`,
    `${j}.cmd_rad`,
    "imu.gx",
    "imu.gy",
    "imu.gz",
    "imu.wx",
    "imu.wy",
    "imu.wz",
    "pol.vx",
    "pol.phase_sin",
    "pol.phase_cos",
    "foot.force_kg",
    "foot_left.force_kg",
  ];
}

/** Channel ids a set of panels needs from /window. */
export function panelChannels(panels: PanelSpec[]): string[] {
  const out = new Set<string>();
  for (const panel of panels) {
    for (const line of panel.lines) out.add(line.key);
    for (const row of panel.states ?? []) out.add(row.key);
  }
  return [...out];
}

/** Channels for the data table next to the inspector. */
export function tableChannels(mode: "joint" | "compare" | "policy", joint: number, metric: CompareMetric): string[] {
  if (mode === "policy") return policyTableChannels(joint);
  if (mode === "compare") {
    return [...Array.from({ length: 10 }, (_, index) => `j${index}.${metric}`), "sys.dt_ms", "sys.seq_gap"];
  }
  const j = `j${joint}`;
  return [
    `${j}.sev`,
    `${j}.cmd`,
    `${j}.corr`,
    `${j}.err`,
    `${j}.raw`,
    `${j}.unwrap`,
    `${j}.as_ok`,
    `${j}.mag`,
    `${j}.agc`,
    `${j}.amp`,
    `${j}.volt`,
    `${j}.out`,
    "sys.dt_ms",
    "sys.seq_gap",
    "sys.i2c_delta",
    "foot.force_kg",
    "foot_left.force_kg",
  ];
}

/** Short column / legend label for a channel id, e.g. "j3.corr" -> "3 corr". */
export function channelLabel(channel: string): string {
  const [scope, field] = channel.split(".");
  // pol / pf / pad also start with "p", so they have to be named before the axis prefix.
  if (scope === "foot") return `R ${field}`;
  if (scope === "foot_left") return `L ${field}`;
  if (scope === "pad") return PAD_CHANNEL_LABEL[field] ?? field;
  if (scope === "imu" || scope === "pol" || scope === "pf") return POLICY_CHANNEL_LABEL[channel] ?? field;
  if (scope.startsWith("j") || scope.startsWith("p")) return `${scope.slice(1)} ${field}`;
  return field;
}

/** Short names for pad channels in the stats table. */
const PAD_CHANNEL_LABEL: Record<string, string> = {
  l_forward: L.sPadLForward,
  l_lateral: L.sPadLLateral,
  l_vertical: L.sPadLVertical,
  l_raw_forward: L.sPadLRawForward,
  l_raw_lateral: L.sPadLRawLateral,
  r_forward: L.sPadRForward,
  r_lateral: L.sPadRLateral,
  r_vertical: L.sPadRVertical,
  r_raw_forward: L.sPadRRawForward,
  r_raw_lateral: L.sPadRRawLateral,
  l_heel_x: L.sPadHeelLx,
  l_heel_y: L.sPadHeelLy,
  l_heel_z: L.sPadHeelLz,
  r_heel_x: L.sPadHeelRx,
  r_heel_y: L.sPadHeelRy,
  r_heel_z: L.sPadHeelRz,
  connected: L.stPadConnected,
  homing: L.stPadHoming,
  l_accepted: L.stPadAcceptL,
  r_accepted: L.stPadAcceptR,
  l_floor: L.stPadFloorL,
  r_floor: L.stPadFloorR,
};

/** Short names for policy channels in the stats table. */
const POLICY_CHANNEL_LABEL: Record<string, string> = {
  "imu.gx": L.sGx,
  "imu.gy": L.sGy,
  "imu.gz": L.sGz,
  "imu.gmag": L.sGmag,
  "imu.wx": L.sWx,
  "imu.wy": L.sWy,
  "imu.wz": L.sWz,
  "pol.reason": L.stReason,
  "pol.safety": L.stSafety,
  "pol.bearing": L.stBearing,
  "pol.dist": L.stDist,
  "pol.overrun": L.stPolOver,
  "pol.phase_sin": L.sPhaseSin,
  "pol.phase_cos": L.sPhaseCos,
  "pol.vx": L.sVx,
  "pol.yaw": L.sYaw,
  "pol.age_imu": L.sAgeImu,
  "pol.age_foot": L.sAgeFoot,
  "pol.period_us": L.sPolPeriod,
  "pol.sense_us": L.sPolSense,
  "pol.policy_us": L.sPolInfer,
  "pol.dt_ms": L.sPolDt,
  "pf.l_tl": L.sFootLtl,
  "pf.l_tr": L.sFootLtr,
  "pf.l_bl": L.sFootLbl,
  "pf.l_br": L.sFootLbr,
  "pf.r_tl": L.sFootRtl,
  "pf.r_tr": L.sFootRtr,
  "pf.r_bl": L.sFootRbl,
  "pf.r_br": L.sFootRbr,
};
