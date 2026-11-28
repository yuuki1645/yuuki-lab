/**
 * Analysis workbench for one take.
 *
 * Layout, top to bottom:
 *   take header + automatic verdict
 *   health map (whole take, every joint and subsystem)
 *   findings list | stacked synchronized plots
 *   sample inspector | recorded rows
 *   statistics of the visible range
 *   per-joint health, link / timing, event log
 *
 * One shared state drives everything: the visible range (view), the
 * hover time, the picked row (cursor) and the focused joint. View, joint,
 * layout and cursor are mirrored into the URL (?j=&from=&to=&i=) so a
 * particular moment can be bookmarked or shared.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { labApi } from "../api";
import { errorText, isAbort } from "../errors";
import { HELP_LINES, KIND_LABEL, L, SEVERITY_LABEL } from "../labels";
import type { LabAnalysis, LabFinding, LabHealthLane, LabInterval } from "../types";
import { SEV_COLOR, useElementWidth } from "./canvas";
import { DataTable, RangeStats } from "./DataViews";
import { FindingsPanel, laneName } from "./FindingsPanel";
import { HealthMap } from "./HealthMap";
import {
  COMPARE_METRICS,
  JOINT_PANEL_CHOICES,
  comparePanels,
  jointPanels,
  padPanels,
  panelChannels,
  policyPanels,
  tableChannels,
  type CompareMetric,
  type PanelId,
  type PanelSpec,
} from "./panels";
import {
  clampView,
  focusView,
  formatClock,
  formatNumber,
  formatOffset,
  formatPct,
  panView,
  revealTime,
  zoomView,
  type View,
} from "./plotMath";
import { SampleInspector } from "./SampleInspector";
import { uprightDegOf } from "./screenAngle";
import { EventLog, JointTable, SystemCard } from "./Summaries";
import { TimePlot, type PlotBand, type PlotMarker } from "./TimePlot";
import { useRangeStats, useRows, useSample, useWindowData, type SampleRequest } from "./useLabData";

const PANELS_KEY = "lab.workbench.panels";
/** Set once so a preference saved before pad panels existed still shows them. */
const PAD_SEEN_KEY = "lab.workbench.panels.pad";
const PAD_PANEL_IDS: PanelId[] = ["padStick", "padState", "padHeel"];
/** Rows in the data table: 30 before the cursor, the cursor, 30 after. */
const TABLE_ROWS = 61;
const TABLE_BEFORE = 30;

/** Panel that shows a finding kind best; switched on when that finding is picked. */
const KIND_PANEL: Record<string, PanelId> = {
  dropout: "status",
  servo_fb: "status",
  magnet: "agc",
  no_map: "status",
  jump: "angle",
  tracking: "err",
  track_offset: "err",
  overcurrent: "amp",
  undervolt: "volt",
  seq_drop: "counters",
  seq_reset: "link",
  rx_gap: "link",
  overrun: "link",
  jitter: "link",
  i2c: "counters",
  foot_lost: "foot",
  corner_missing: "foot",
  foot_saturated: "foot",
  policy_safety: "polState",
  policy_reason: "polState",
  policy_flag: "polJoint",
  policy_stale: "polAge",
  policy_clip: "polClip",
  policy_diverge: "polJoint",
  sim_envelope: "polJoint",
  sim_tilt: "polGrav",
};

type BenchMode = "joint" | "compare" | "policy";

/** "code label" pairs from context.json, for the line under the policy plots. */
function enumLine(title: string, table: Record<string, string> | undefined): string {
  if (!table) return "";
  const body = Object.entries(table)
    .map(([code, label]) => `${code} ${label}`)
    .join(" \u00b7 ");
  return body ? `${title} ${body}` : "";
}

function countLine(counts: Record<string, number> | undefined, table: Record<string, string> | undefined): string {
  if (!counts) return "";
  return Object.entries(counts)
    .filter(([, count]) => count > 0)
    .map(([code, count]) => `${table?.[code] ?? code} ${count.toLocaleString()}`)
    .join(" \u00b7 ");
}

/** Policy findings open the policy plots. A joint finding opens that axis. */
function modeForFinding(finding: LabFinding, side: string | null): BenchMode | null {
  // A playback has no sensor charts. Every finding opens the policy view.
  if (side === "sim") return "policy";
  if (finding.kind.startsWith("policy_") || finding.kind.startsWith("sim_") || finding.lane === "policy") return "policy";
  if (finding.joint != null) return "joint";
  return null;
}

function loadPanels(): Set<PanelId> {
  const defaults = new Set(JOINT_PANEL_CHOICES.filter((item) => item.on).map((item) => item.id));
  try {
    const saved = JSON.parse(localStorage.getItem(PANELS_KEY) || "null") as PanelId[] | null;
    if (!Array.isArray(saved) || saved.length === 0) return defaults;
    const set = new Set(saved);
    if (localStorage.getItem(PAD_SEEN_KEY) !== "1") {
      for (const id of PAD_PANEL_IDS) set.add(id);
      localStorage.setItem(PAD_SEEN_KEY, "1");
    }
    return set;
  } catch {
    /* Corrupt preference: fall back to defaults. */
    return defaults;
  }
}

function numParam(params: URLSearchParams, key: string): number | null {
  const raw = params.get(key);
  if (raw == null || raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function formatWhen(iso: string | null): string {
  if (!iso) return L.dash;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("ja-JP", { hour12: false });
}

/** Joint with the worst findings, so the page opens on the problem. */
function worstJoint(analysis: LabAnalysis): number {
  let best = 0;
  let score = -1;
  for (const item of analysis.joint_stats) {
    const value = item.crit * 1000 + item.warn;
    if (value > score) {
      score = value;
      best = item.index;
    }
  }
  return best;
}

// ---------------------------------------------------------------------------

export default function LabWorkbench({ day, takeId }: { day: string; takeId: string }) {
  const [params] = useSearchParams();
  const side = params.get("side");
  const [analysis, setAnalysis] = useState<LabAnalysis | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const ctrl = new AbortController();
    setAnalysis(null);
    setError("");
    labApi
      .getAnalysis(day, takeId, 800, ctrl.signal, side)
      .then((body) => setAnalysis(body))
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(errorText(err));
      });
    return () => ctrl.abort();
  }, [day, takeId, side]);

  if (error) return <p className="lab-error">{error}</p>;
  if (!analysis) {
    return (
      <section className="card lab-analyzing">
        <p>{L.analyzing}</p>
        <div className="lab-progress" aria-hidden />
      </section>
    );
  }
  // Keyed so switching takes starts from a clean state.
  return <Workbench key={`${day}/${takeId}/${side ?? ""}`} day={day} takeId={takeId} analysis={analysis} />;
}

// ---------------------------------------------------------------------------

function Workbench({ day, takeId, analysis }: { day: string; takeId: string; analysis: LabAnalysis }) {
  const [params, setParams] = useSearchParams();
  const duration = Math.max(analysis.duration_sec, 0.001);
  const th = analysis.thresholds;
  const meta = analysis.meta;
  const side = meta.side === "sim" || meta.side === "robot" ? meta.side : null;

  // ----- state (initial values come from the URL once) ----------------
  const [view, setViewState] = useState<View>(() => {
    const from = numParam(params, "from");
    const to = numParam(params, "to");
    return clampView(from != null && to != null ? { from, to } : { from: 0, to: duration }, duration);
  });
  const [joint, setJoint] = useState<number>(() => {
    const value = numParam(params, "j");
    return value != null && value >= 0 && value <= 9 ? Math.round(value) : worstJoint(analysis);
  });
  const [mode, setMode] = useState<BenchMode>(() => {
    const value = params.get("m");
    if (value === "compare" || value === "policy" || value === "joint") return value;
    // A playback has no encoder trace. Open on the policy charts.
    return analysis.meta.side === "sim" ? "policy" : "joint";
  });
  const [metric, setMetric] = useState<CompareMetric>(() => {
    const value = params.get("cm");
    return (COMPARE_METRICS.find((item) => item.id === value)?.id ?? "err") as CompareMetric;
  });
  const [sampleReq, setSampleReq] = useState<SampleRequest | null>(() => {
    const index = numParam(params, "i");
    return index != null ? { index: Math.round(index), nonce: 0 } : null;
  });
  const [hoverT, setHoverT] = useState<number | null>(null);
  const [cursorT, setCursorT] = useState<number | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [panelsOn, setPanelsOn] = useState<Set<PanelId>>(loadPanels);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeInterval, setActiveInterval] = useState<{ id: string; index: number } | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [toast, setToast] = useState("");
  const [tableStart, setTableStart] = useState<number | null>(null);

  const plotsRef = useRef<HTMLDivElement>(null);
  const inspectorRef = useRef<HTMLDivElement>(null);
  const plotsWidth = useElementWidth(plotsRef);

  const setView = useCallback((next: View) => setViewState(clampView(next, duration)), [duration]);
  const resetView = useCallback(() => setViewState({ from: 0, to: duration }), [duration]);

  useEffect(() => {
    localStorage.setItem(PANELS_KEY, JSON.stringify([...panelsOn]));
  }, [panelsOn]);

  const flashToast = useCallback((text: string) => {
    setToast(text);
    window.setTimeout(() => setToast(""), 1800);
  }, []);

  // ----- cursor --------------------------------------------------------
  const { sample, loading: sampleLoading } = useSample(day, takeId, sampleReq, side);

  const pickTime = useCallback((t: number) => {
    setCursorT(t);
    setSampleReq({ t, nonce: Math.random() });
  }, []);
  const pickIndex = useCallback((index: number) => {
    setSampleReq({ index, nonce: Math.random() });
  }, []);

  // When the row arrives: snap the cursor to it, keep it on screen, and
  // centre the data table on it.
  useEffect(() => {
    if (!sample) return;
    setCursorT(sample.t_offset);
    setTableStart(Math.max(0, sample.index - TABLE_BEFORE));
    setViewState((current) => revealTime(current, sample.t_offset, duration));
  }, [sample, duration]);

  // ----- panels and data ----------------------------------------------
  // A bookmarked policy view on a v1 take falls back to the joint plots.
  const modeEff: BenchMode = mode === "policy" && !analysis.policy ? "joint" : mode;
  const medianErr = analysis.joint_stats[joint]?.tracking.median_deg ?? null;
  const panels = useMemo<PanelSpec[]>(() => {
    if (modeEff === "policy") {
      return policyPanels(joint, analysis.context?.envelope_rad ?? 0.35, side !== "sim");
    }
    const base =
      modeEff === "compare"
        ? comparePanels(metric, th, analysis.joint_names)
        : jointPanels(joint, th, medianErr, showRaw, (analysis.context?.servos?.[joint] ?? "") === "SM105BL").filter((panel) =>
            panelsOn.has(panel.id)
          );
    if (!analysis.gamepad) return base;
    const pads = padPanels(showRaw).filter((panel) => panelsOn.has(panel.id));
    // Sit under the angle (or the compare chart) so a flat command can be
    // read against the stick that was actually held.
    const anchor = base.findIndex((panel) => panel.id === "angle" || panel.id === "compare");
    if (anchor < 0) return [...base, ...pads];
    return [...base.slice(0, anchor + 1), ...pads, ...base.slice(anchor + 1)];
  }, [modeEff, metric, th, analysis.joint_names, analysis.gamepad, analysis.context, joint, medianErr, showRaw, panelsOn, side]);

  const channels = useMemo(() => panelChannels(panels), [panels]);
  const { data, loading: windowLoading } = useWindowData(day, takeId, channels, view, Math.max(0, plotsWidth - 76), side);

  // One sample spacing, so a single-row band still has width.
  const rowSec = (analysis.system_stats.dt_median_ms ?? 50) / 1000;

  const bandsByPanel = useMemo(() => {
    const out: Record<string, PlotBand[]> = {};
    for (const panel of panels) {
      const list: PlotBand[] = [];
      for (const finding of analysis.findings) {
        if (finding.kind === "track_offset" || !panel.bandLanes.includes(finding.lane)) continue;
        if (panel.bandKinds !== "all" && !panel.bandKinds.includes(finding.kind)) continue;
        for (const interval of finding.intervals) {
          list.push({ from: interval.start_offset, to: interval.end_offset + rowSec, severity: interval.severity });
        }
      }
      // Paint quiet bands first so a red one is never covered by grey.
      out[panel.id] = list.sort((a, b) => a.severity - b.severity);
    }
    return out;
  }, [panels, analysis.findings, rowSec]);

  const markersByPanel = useMemo(() => {
    const errors: PlotMarker[] = [];
    const warnJoint: PlotMarker[] = [];
    const warnSystem: PlotMarker[] = [];
    for (const event of analysis.events) {
      if (event.offset == null) continue;
      if (event.level === "error") errors.push({ t: event.offset, kind: "error" });
      else if (event.level === "warn" && event.joint === joint) warnJoint.push({ t: event.offset, kind: "warn" });
      else if (event.level === "warn" && event.joint == null) warnSystem.push({ t: event.offset, kind: "warn" });
    }
    const commands: PlotMarker[] = analysis.commands
      .filter((command) => (command.text === "CMD" || command.text === "OUT") && command.ch === joint)
      .map((command) => ({ t: command.offset, kind: "cmd" as const }));
    // POLICY rows have no channel. They mark when the network was switched.
    const policyMarks: PlotMarker[] = analysis.commands
      .filter((command) => command.text === "POLICY")
      .map((command) => ({ t: command.offset, kind: "cmd" as const }));
    const out: Record<string, PlotMarker[]> = {};
    for (const panel of panels) {
      if (panel.id === "status") out[panel.id] = [...errors, ...warnJoint];
      else if (panel.id === "angle") out[panel.id] = [...errors, ...commands];
      else if (panel.id === "polState" || panel.id === "polJoint") out[panel.id] = [...errors, ...policyMarks];
      else if (panel.id === "link") out[panel.id] = [...errors, ...warnSystem];
      else out[panel.id] = errors;
    }
    return out;
  }, [analysis.events, analysis.commands, joint, panels]);

  const uprightDeg = uprightDegOf(joint, analysis.context);
  const statsChannels = useMemo(
    () =>
      panels.flatMap((panel) =>
        panel.lines.map((line) => ({
          key: line.key,
          label: `${line.label}${panel.unit ? ` (${panel.unit})` : ""}`,
          digits: panel.digits,
          angle: panel.angle,
          uprightDeg: panel.angle === "screen" ? uprightDeg : 0,
        }))
      ),
    [panels, uprightDeg]
  );
  const statsKeys = useMemo(() => statsChannels.map((item) => item.key), [statsChannels]);
  const { stats, loading: statsLoading } = useRangeStats(day, takeId, statsKeys, view, side);

  const tableKeys = useMemo(() => tableChannels(modeEff, joint, metric), [modeEff, joint, metric]);
  // Without a cursor the table starts at the first row of the view.
  const viewStartIndex = useMemo(() => {
    if (!data) return null;
    for (let i = 0; i < data.t.length; i += 1) {
      const index = data.index[i];
      if (data.t[i] >= view.from && index != null) return index;
    }
    return null;
  }, [data, view.from]);
  const { rows, loading: rowsLoading } = useRows(day, takeId, tableKeys, tableStart ?? viewStartIndex, TABLE_ROWS, side);

  // ----- navigation ----------------------------------------------------
  const sampleRef = useRef(sample);
  sampleRef.current = sample;
  const dataRef = useRef(data);
  dataRef.current = data;

  /** Move the cursor by whole rows. Uses loaded plot data for instant feedback. */
  const step = useCallback(
    (delta: number) => {
      const current = sampleRef.current;
      if (!current) {
        pickTime((view.from + view.to) / 2);
        return;
      }
      const target = Math.max(0, Math.min(current.total - 1, current.index + delta));
      const loaded = dataRef.current;
      if (loaded?.mode === "raw") {
        const position = loaded.index.indexOf(target);
        if (position >= 0) setCursorT(loaded.t[position]);
      }
      pickIndex(target);
    },
    [pickIndex, pickTime, view.from, view.to]
  );

  const focusJoint = useCallback((next: number) => {
    setJoint(((next % 10) + 10) % 10);
    setHidden(new Set());
  }, []);

  /** Make sure the panel that explains a finding is visible. */
  const showPanelFor = useCallback((finding: LabFinding) => {
    let panel = KIND_PANEL[finding.kind];
    // Policy mode has its own foot chart. The joint-mode "foot" panel is not mounted.
    if (side === "sim" && panel === "foot") panel = "polFoot";
    if (panel) setPanelsOn((prev) => (prev.has(panel) ? prev : new Set([...prev, panel])));
  }, [side]);

  const selectFinding = useCallback(
    (finding: LabFinding) => {
      setSelectedId(finding.id);
      setActiveInterval(null);
      const nextMode = modeForFinding(finding, side);
      if (finding.joint != null) focusJoint(finding.joint);
      if (nextMode) setMode(nextMode);
      showPanelFor(finding);
      // Short findings are shown whole; long ones zoom to their worst interval.
      const worst = finding.intervals.find((item) => item.peak_index === finding.peak_index) ?? finding.intervals[0];
      const span = finding.last_offset - finding.first_offset;
      const range =
        span <= Math.max(60, duration * 0.3) || !worst
          ? [finding.first_offset, finding.last_offset]
          : [worst.start_offset, worst.end_offset];
      setView(focusView(range[0], range[1], duration));
      setCursorT(finding.peak_offset);
      pickIndex(finding.peak_index);
    },
    [duration, focusJoint, pickIndex, setView, showPanelFor, side]
  );

  const selectInterval = useCallback(
    (finding: LabFinding, interval: LabInterval, index: number) => {
      setSelectedId(finding.id);
      setActiveInterval({ id: finding.id, index });
      const nextMode = modeForFinding(finding, side);
      if (finding.joint != null) focusJoint(finding.joint);
      if (nextMode) setMode(nextMode);
      showPanelFor(finding);
      setView(focusView(interval.start_offset, interval.end_offset, duration));
      setCursorT(interval.peak_offset);
      pickIndex(interval.peak_index);
    },
    [duration, focusJoint, pickIndex, setView, showPanelFor, side]
  );

  /** Every interval of the listed findings in time order, for the . / , keys. */
  const navIntervals = useMemo(() => {
    const list: Array<{ finding: LabFinding; interval: LabInterval; index: number }> = [];
    for (const finding of analysis.findings) {
      if (finding.severity < 2 && !showInfo) continue;
      finding.intervals.forEach((interval, index) => list.push({ finding, interval, index }));
    }
    return list.sort(
      (a, b) => a.interval.start_offset - b.interval.start_offset || b.finding.severity - a.finding.severity
    );
  }, [analysis.findings, showInfo]);

  const gotoInterval = useCallback(
    (direction: 1 | -1) => {
      if (!navIntervals.length) return;
      let position = activeInterval
        ? navIntervals.findIndex((item) => item.finding.id === activeInterval.id && item.index === activeInterval.index)
        : -1;
      if (position >= 0) position += direction;
      else {
        const ref = cursorT ?? view.from;
        position =
          direction > 0
            ? navIntervals.findIndex((item) => item.interval.start_offset > ref + 1e-3)
            : navIntervals.map((item) => item.interval.start_offset < ref - 1e-3).lastIndexOf(true);
      }
      const target = navIntervals[position];
      if (target) selectInterval(target.finding, target.interval, target.index);
    },
    [navIntervals, activeInterval, cursorT, view.from, selectInterval]
  );

  const onMapPick = useCallback(
    (t: number, lane: LabHealthLane | null) => {
      if (side === "sim") {
        if (lane?.joint != null) focusJoint(lane.joint);
        setMode("policy");
      } else if (lane?.id === "policy") setMode("policy");
      else if (lane?.joint != null) {
        focusJoint(lane.joint);
        setMode("joint");
      }
      // From an overview, a click means "show me this moment up close".
      setViewState((current) =>
        current.to - current.from > 40 ? clampView({ from: t - 10, to: t + 10 }, duration) : revealTime(current, t, duration)
      );
      pickTime(t);
    },
    [duration, focusJoint, pickTime, side]
  );

  const zoomBy = useCallback(
    (factor: number) => {
      const centre = cursorT != null && cursorT >= view.from && cursorT <= view.to ? cursorT : (view.from + view.to) / 2;
      setView(zoomView(view, centre, factor, duration));
    },
    [cursorT, view, duration, setView]
  );

  const toggleLine = useCallback((key: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // ----- URL mirror ----------------------------------------------------
  const buildParams = useCallback(() => {
    const next = new URLSearchParams();
    next.set("j", String(joint));
    if (mode === "compare") {
      next.set("m", "compare");
      next.set("cm", metric);
    } else if (mode === "policy") {
      next.set("m", "policy");
    }
    const whole = view.from <= 0.001 && view.to >= duration - 0.001;
    if (!whole) {
      next.set("from", view.from.toFixed(2));
      next.set("to", view.to.toFixed(2));
    }
    if (sample) next.set("i", String(sample.index));
    return next;
  }, [joint, mode, metric, view, duration, sample]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = buildParams();
      if (next.toString() !== params.toString()) setParams(next, { replace: true });
    }, 400);
    return () => window.clearTimeout(timer);
    // params is read, not watched: watching it would loop with setParams.
  }, [buildParams, setParams]);

  const copyLink = useCallback(async () => {
    const url = `${window.location.origin}${window.location.pathname}?${buildParams().toString()}`;
    try {
      await navigator.clipboard.writeText(url);
      flashToast(L.linkCopied);
    } catch {
      flashToast(url);
    }
  }, [buildParams, flashToast]);

  const downloadCsv = useCallback(
    async (whole: boolean) => {
      try {
        await labApi.downloadCsv(day, takeId, [], whole ? null : view.from, whole ? null : view.to, side);
      } catch (err) {
        flashToast(errorText(err));
      }
    },
    [day, takeId, view, flashToast, side]
  );

  // ----- keyboard ------------------------------------------------------
  // Arrows, digits and punctuation move the workbench.
  // Single letters are not shortcuts on this screen.
  const keyRef = useRef<(event: KeyboardEvent) => void>(() => undefined);
  keyRef.current = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement | null;
    if (target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    switch (event.key) {
      case "ArrowLeft":
        event.preventDefault();
        step(event.shiftKey ? -10 : -1);
        break;
      case "ArrowRight":
        event.preventDefault();
        step(event.shiftKey ? 10 : 1);
        break;
      case "+":
      case "=":
        zoomBy(0.5);
        break;
      case "-":
      case "_":
        zoomBy(2);
        break;
      case "0":
      case "Home":
        resetView();
        break;
      case ".":
        gotoInterval(1);
        break;
      case ",":
        gotoInterval(-1);
        break;
      case "[":
        focusJoint(joint - 1);
        break;
      case "]":
        focusJoint(joint + 1);
        break;
      case "5":
        if (cursorT != null) setView({ from: cursorT - 5, to: cursorT + 5 });
        break;
      case "?":
        setShowHelp((value) => !value);
        break;
      case "Escape":
        setShowHelp(false);
        break;
      default:
        break;
    }
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => keyRef.current(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  // ----- derived header numbers ---------------------------------------
  const counts = useMemo(() => {
    const result: Record<number, number> = { 1: 0, 2: 0, 3: 0 };
    for (const finding of analysis.findings) result[finding.severity] = (result[finding.severity] ?? 0) + 1;
    return result;
  }, [analysis.findings]);
  const topFindings = useMemo(() => analysis.findings.filter((item) => item.severity >= 2).slice(0, 6), [analysis.findings]);
  const system = analysis.system_stats;
  const span = view.to - view.from;

  return (
    <div className="lab-bench">
      <section className="card lab-take-head">
        <div>
          <h3 className="lab-section-title">
            {meta.take_id}
            {meta.recording ? <span className="lab-badge">{L.recording}</span> : null}
            {meta.format_id === "core_take_v2" ? <span className="lab-badge">{L.formatV2}</span> : null}
            {meta.side === "sim" ? <span className="lab-badge">{L.formatSim}</span> : null}
          </h3>
          <p className="lab-meta-line">
            {formatWhen(meta.started_at)} {L.dash} {formatWhen(meta.ended_at)}
            {" \u00b7 "}
            {formatOffset(analysis.duration_sec)}
            {meta.side === "sim" ? ` (${L.simClock})` : ""}
            {" \u00b7 "}
            {meta.stop_reason || L.dash}
          </p>
          {meta.hello ? <p className="lab-hello">{meta.hello}</p> : null}
          {analysis.context?.experiment ? (
            <p className="lab-meta-line">
              {L.experiment} {analysis.context.experiment}
              {analysis.context.task ? ` \u00b7 ${analysis.context.task}` : ""}
            </p>
          ) : null}
          {analysis.context && (analysis.context.learn_run || analysis.context.checkpoint) ? (
            <p className="lab-meta-line">
              {L.policyLearn} {analysis.context.learn_run || L.dash}
              {" \u00b7 "}
              {analysis.context.checkpoint || L.dash}
            </p>
          ) : null}
          {analysis.policy ? (
            <p className="lab-meta-line">
              {L.policyTitle} {analysis.policy.samples.toLocaleString()}
              {L.policyRows}
              {" \u00b7 "}
              {analysis.policy.rate_hz == null ? L.dash : `${formatNumber(analysis.policy.rate_hz, 1)} Hz`}
              {" \u00b7 "}
              {L.policyActions} {analysis.policy.action_rows.toLocaleString()}
              {analysis.context ? ` \u00b7 ${countLine(analysis.policy.reason_counts, analysis.context.enums.reason)}` : ""}
            </p>
          ) : null}
          {analysis.gamepad ? (
            <p className="lab-meta-line">
              {L.padTitle} {analysis.gamepad.samples.toLocaleString()}
              {L.padRows}
              {" \u00b7 "}
              {analysis.gamepad.rate_hz == null ? L.dash : `${formatNumber(analysis.gamepad.rate_hz, 2)} Hz`}
              {" \u00b7 "}
              {L.padFrom} +{formatOffset(analysis.gamepad.start_offset ?? 0)}
              {" \u00b7 "}
              {L.padStick} {analysis.gamepad.stick_rows.toLocaleString()}
              {" \u00b7 "}
              {L.padAccepted} {L.padLeft} {analysis.gamepad.accepted_left.toLocaleString()} (
              {analysis.gamepad.accepted_left_runs}
              {L.padBursts}) / {L.padRight} {analysis.gamepad.accepted_right.toLocaleString()} (
              {analysis.gamepad.accepted_right_runs}
              {L.padBursts})
            </p>
          ) : null}
          {meta.notes ? (
            <p>
              {L.notes}: {meta.notes}
            </p>
          ) : null}
          {analysis.tail_pending ? <p className="lab-warn">{L.tailPending}</p> : null}
        </div>
        <div className="lab-take-actions">
          <button type="button" className="btn btn-sm" onClick={copyLink}>
            {L.copyLink}
          </button>
          <button type="button" className="btn btn-sm" onClick={() => downloadCsv(true)}>
            {L.csvAll}
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => setShowHelp(true)}>
            {L.help} (?)
          </button>
        </div>
      </section>

      <section className="card lab-verdict">
        <div className="lab-verdict-main">
          <p className="lab-muted lab-small">{L.verdictLead}</p>
          {counts[3] || counts[2] ? (
            <p className="lab-verdict-counts">
              <span style={{ color: SEV_COLOR[3] }}>
                {L.verdictCrit} {counts[3]}
              </span>
              <span style={{ color: SEV_COLOR[2] }}>
                {L.verdictWarn} {counts[2]}
              </span>
              <span className="lab-muted">
                {L.verdictInfo} {counts[1]}
              </span>
            </p>
          ) : (
            <p className="lab-verdict-ok">{L.verdictOk}</p>
          )}
          <div className="lab-verdict-chips">
            {topFindings.map((finding) => (
              <button
                key={finding.id}
                type="button"
                className="lab-flag-chip lab-chip-button"
                style={{ borderColor: SEV_COLOR[finding.severity] }}
                onClick={() => selectFinding(finding)}
              >
                <span className="lab-sev-dot" style={{ background: SEV_COLOR[finding.severity] }} />
                {KIND_LABEL[finding.kind] ?? finding.kind}
                <span className="lab-muted">{laneName(finding.lane, finding.joint, analysis.joint_names)}</span>
              </button>
            ))}
          </div>
        </div>
        <dl className="lab-kpis">
          <div>
            <dt>{L.samples}</dt>
            <dd>{analysis.sample_count.toLocaleString()}</dd>
          </div>
          <div>
            <dt>{L.kpiRate}</dt>
            <dd>{system.rate_hz == null ? L.dash : `${formatNumber(system.rate_hz, 2)} Hz`}</dd>
          </div>
          <div>
            <dt>{L.kpiDrops}</dt>
            <dd className={system.seq_dropped_total ? "lab-cell-warn" : undefined}>{system.seq_dropped_total}</dd>
          </div>
          <div>
            <dt>{L.kpiI2c}</dt>
            <dd className={system.i2c_delta ? "lab-cell-warn" : undefined}>{system.i2c_delta ?? L.dash}</dd>
          </div>
          <div>
            <dt>{L.kpiOverrun}</dt>
            <dd className={system.overrun_count ? "lab-cell-warn" : undefined}>{system.overrun_count}</dd>
          </div>
          <div>
            <dt>{L.kpiServo}</dt>
            <dd>{formatPct(system.servo_ok_ratio, 1)}</dd>
          </div>
          <div>
            <dt>{L.kpiFeet}</dt>
            <dd>
              {formatPct(system.foot_ok_ratio)} / {formatPct(system.foot_left_ok_ratio)}
            </dd>
          </div>
        </dl>
      </section>

      <section className="card">
        <header className="lab-health-head">
          <h3 className="lab-section-title">{L.healthTitle}</h3>
          <p className="lab-muted lab-small">{L.healthHint}</p>
        </header>
        <HealthMap
          analysis={analysis}
          view={view}
          hoverT={hoverT}
          cursorT={cursorT}
          focusJoint={joint}
          onHover={setHoverT}
          onPick={onMapPick}
          onView={setView}
          onReset={resetView}
          onFocusJoint={focusJoint}
        />
      </section>

      <div className="lab-main">
        <aside className="card lab-side">
          <FindingsPanel
            findings={analysis.findings}
            jointNames={analysis.joint_names}
            thresholds={th}
            selectedId={selectedId}
            activeInterval={activeInterval}
            showInfo={showInfo}
            onShowInfo={setShowInfo}
            onSelect={selectFinding}
            onInterval={selectInterval}
          />
        </aside>

        <section className="card lab-plots-card">
          <div className="lab-toolbar">
            <div className="lab-seg" role="group">
              <button type="button" className={modeEff === "joint" ? "is-on" : undefined} onClick={() => setMode("joint")}>
                {L.modeJoint}
              </button>
              <button type="button" className={modeEff === "compare" ? "is-on" : undefined} onClick={() => setMode("compare")}>
                {L.modeCompare}
              </button>
              {analysis.policy ? (
                <button type="button" className={modeEff === "policy" ? "is-on" : undefined} onClick={() => setMode("policy")}>
                  {L.modePolicy}
                </button>
              ) : null}
            </div>
            <div className="lab-zoom">
              <button type="button" className="btn btn-sm" onClick={() => setView(panView(view, -span * 0.5, duration))} title={L.panLeft}>
                {"\u25c0"}
              </button>
              <button type="button" className="btn btn-sm" onClick={() => zoomBy(2)} title={L.zoomOut}>
                {"\u2212"}
              </button>
              <button type="button" className="btn btn-sm" onClick={() => zoomBy(0.5)} title={L.zoomIn}>
                +
              </button>
              <button type="button" className="btn btn-sm" onClick={() => setView(panView(view, span * 0.5, duration))} title={L.panRight}>
                {"\u25b6"}
              </button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={resetView}>
                {L.zoomAll}
              </button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => downloadCsv(false)}>
                {L.csvView}
              </button>
            </div>
          </div>

          {modeEff === "compare" ? (
            <div className="lab-joint-chips">
              <span className="lab-muted lab-small">{L.metric}</span>
              {COMPARE_METRICS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={item.id === metric ? "lab-joint-chip is-on" : "lab-joint-chip"}
                  onClick={() => setMetric(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="lab-joint-chips" role="tablist" aria-label={L.jointPick}>
              {analysis.joint_stats.map((item) => {
                const worst = item.crit ? 3 : item.warn ? 2 : 0;
                return (
                  <button
                    key={item.index}
                    type="button"
                    role="tab"
                    aria-selected={item.index === joint}
                    className={item.index === joint ? "lab-joint-chip is-on" : "lab-joint-chip"}
                    onClick={() => focusJoint(item.index)}
                    title={item.name}
                  >
                    <span className="lab-sev-dot" style={{ background: worst ? SEV_COLOR[worst] : "rgba(61, 220, 132, 0.7)" }} />
                    {item.index} {item.name}
                  </button>
                );
              })}
            </div>
          )}

          {modeEff === "policy" && analysis.context ? (
            <p className="lab-muted lab-small">
              {enumLine(L.policyReason, analysis.context.enums.reason)}
              {" \u00b7 "}
              {enumLine(L.policySafety, analysis.context.enums.safety)}
            </p>
          ) : null}

          {modeEff === "joint" ? (
            <div className="lab-panel-chips">
              <span className="lab-muted lab-small">{L.panels}</span>
              {JOINT_PANEL_CHOICES.filter((choice) => analysis.gamepad || !choice.id.startsWith("pad")).map((choice) => (
                <label key={choice.id} className="lab-check">
                  <input
                    type="checkbox"
                    checked={panelsOn.has(choice.id)}
                    onChange={(event) =>
                      setPanelsOn((prev) => {
                        const next = new Set(prev);
                        if (event.target.checked) next.add(choice.id);
                        else next.delete(choice.id);
                        return next;
                      })
                    }
                  />
                  {choice.label}
                </label>
              ))}
              <label className="lab-check">
                <input type="checkbox" checked={showRaw} onChange={(event) => setShowRaw(event.target.checked)} />
                {L.showRawAngle}
              </label>
            </div>
          ) : null}

          <div className="lab-range-line">
            <span>
              {L.rangeLabel} <strong>{formatOffset(view.from, 0.1)}</strong> {"\u2013"} <strong>{formatOffset(view.to, 0.1)}</strong> (
              {span.toFixed(span < 10 ? 2 : 1)} {L.sec}) {formatClock(analysis.t0, view.from)}
            </span>
            <span className="lab-muted">
              {data ? `${data.mode === "raw" ? L.rawNote : L.envelopeNote} \u00b7 ${data.sample_count.toLocaleString()} ${L.samplesUnit}` : L.loading}
            </span>
            {sample ? (
              <span className="lab-cursor-readout">
                {L.cursorLabel} #{sample.index} +{formatOffset(sample.t_offset, 0.001)} {sample.part}:{sample.line}
                <button
                  type="button"
                  className="lab-link-button"
                  onClick={() => inspectorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                >
                  {L.toInspector}
                </button>
              </span>
            ) : null}
          </div>

          <div className="lab-plots" ref={plotsRef}>
            {panels.map((panel, index) => (
              <TimePlot
                key={panel.id}
                title={panel.title}
                unit={panel.unit}
                lines={panel.lines}
                states={panel.states}
                refs={panel.refs}
                yFixed={panel.yFixed}
                digits={panel.digits}
                angle={panel.angle}
                uprightDeg={uprightDeg}
                height={panel.height}
                data={data}
                view={view}
                duration={duration}
                hoverT={hoverT}
                cursorT={cursorT}
                bands={bandsByPanel[panel.id] ?? []}
                markers={markersByPanel[panel.id] ?? []}
                activeSpans={panel.dimWhenOutOff != null ? analysis.out_spans[panel.dimWhenOutOff] : undefined}
                hidden={hidden}
                showAxis={index === panels.length - 1}
                loading={windowLoading}
                onHover={setHoverT}
                onPick={pickTime}
                onView={setView}
                onReset={resetView}
                onToggleLine={toggleLine}
              />
            ))}
          </div>
        </section>
      </div>

      <div className="lab-lower" ref={inspectorRef}>
        <section className="card">
          <SampleInspector
            sample={sample}
            loading={sampleLoading}
            analysis={analysis}
            focusJoint={joint}
            onStep={step}
            onCenter={() => {
              if (cursorT != null) setView({ from: cursorT - span / 2, to: cursorT + span / 2 });
            }}
            onFocusJoint={focusJoint}
          />
        </section>
        <section className="card">
          <DataTable
            rows={rows}
            loading={rowsLoading}
            cursorIndex={sample?.index ?? null}
            thresholds={th}
            uprightDeg={uprightDeg}
            onPickIndex={pickIndex}
            onPage={(delta) => setTableStart((current) => Math.max(0, (current ?? rows?.start ?? 0) + delta * (TABLE_ROWS - 1)))}
          />
        </section>
      </div>

      <section className="card">
        <RangeStats stats={stats} loading={statsLoading} channels={statsChannels} onPickIndex={pickIndex} />
      </section>

      <section className="card">
        <JointTable
          stats={analysis.joint_stats}
          thresholds={th}
          focusJoint={joint}
          servos={analysis.context?.servos}
          onFocusJoint={(next) => {
            focusJoint(next);
            setMode("joint");
          }}
          onPickIndex={pickIndex}
        />
      </section>

      <div className="lab-lower">
        <section className="card">
          <SystemCard analysis={analysis} />
        </section>
        <section className="card">
          <EventLog
            events={analysis.events}
            eventsTotal={analysis.events_total}
            commands={analysis.commands}
            commandsTotal={analysis.commands_total}
            view={view}
            cursorT={cursorT}
            onPickTime={(t) => {
              setViewState((current) => revealTime(current, t, duration));
              pickTime(t);
            }}
          />
        </section>
      </div>

      {showHelp ? (
        <div className="lab-modal" role="dialog" aria-modal="true" onClick={() => setShowHelp(false)}>
          <div className="lab-modal-body card" onClick={(event) => event.stopPropagation()}>
            <h3 className="lab-section-title">{L.helpTitle}</h3>
            <ul className="lab-help">
              {HELP_LINES.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p className="lab-muted lab-small">
              {SEVERITY_LABEL[3]} / {SEVERITY_LABEL[2]} / {SEVERITY_LABEL[1]}
            </p>
            <button type="button" className="btn btn-primary" onClick={() => setShowHelp(false)}>
              {L.close}
            </button>
          </div>
        </div>
      ) : null}
      {toast ? <div className="lab-toast">{toast}</div> : null}
    </div>
  );
}
