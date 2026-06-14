import { useCallback, useEffect, useMemo, useState } from "react";
import { getIsaacRlLogApiUrl } from "@/shared/constants";
import {
  isaacRlLogFetchExperiments,
  isaacRlLogFetchHealth,
  isaacRlLogFetchRunMeta,
  isaacRlLogFetchRuns,
  isaacRlLogFetchScalars,
} from "@/shared/api/isaacRlLogApi";
import type { IsaacRlLogAccessUrls, IsaacRlLogRunMeta, IsaacRlLogScalarsResponse } from "@/shared/types/isaacRlLog";
import { MetricLineChart } from "./components/MetricLineChart";
import {
  ISAAC_RL_LOG_POLL_MS,
  ISAAC_RL_METRIC_BY_TAG,
  ISAAC_RL_METRICS,
  LS_ISAAC_RL_LOG_API,
} from "./isaacRlLogMetrics";
import "./IsaacRlLogPage.css";

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ja-JP");
  } catch {
    return iso;
  }
}

export default function IsaacRlLogPage() {
  const [apiBase, setApiBase] = useState(() => {
    if (typeof window !== "undefined") {
      const s = localStorage.getItem(LS_ISAAC_RL_LOG_API);
      if (s && s.length > 0) return s.replace(/\/$/, "");
    }
    return getIsaacRlLogApiUrl();
  });
  const [connected, setConnected] = useState<boolean | null>(null);
  const [logRoot, setLogRoot] = useState<string>("");
  const [accessUrls, setAccessUrls] = useState<IsaacRlLogAccessUrls | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [experiments, setExperiments] = useState<string[]>([]);
  const [experiment, setExperiment] = useState("");
  const [runId, setRunId] = useState("");
  const [runOptions, setRunOptions] = useState<{ id: string; label: string }[]>([]);
  const [scalars, setScalars] = useState<IsaacRlLogScalarsResponse | null>(null);
  const [meta, setMeta] = useState<IsaacRlLogRunMeta | null>(null);
  const [showSecondary, setShowSecondary] = useState(false);
  const [lastFetchedAt, setLastFetchedAt] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);

  const b = useMemo(() => apiBase.replace(/\/$/, ""), [apiBase]);

  const persistApiBase = () => {
    try {
      localStorage.setItem(LS_ISAAC_RL_LOG_API, b);
    } catch {
      /* ignore */
    }
  };

  const ping = useCallback(async () => {
    try {
      const h = await isaacRlLogFetchHealth(b);
      setConnected(true);
      setLogRoot(h.log_root);
      setAccessUrls(h.access_urls ?? null);
      setErr(null);
      return true;
    } catch (e) {
      setConnected(false);
      setErr(e instanceof Error ? e.message : String(e));
      return false;
    }
  }, [b]);

  const loadExperiments = useCallback(async () => {
    const ok = await ping();
    if (!ok) return;
    try {
      const exps = await isaacRlLogFetchExperiments(b);
      setExperiments(exps);
      setExperiment((prev) => {
        if (prev && exps.includes(prev)) return prev;
        return exps.includes("biped_ppo_walk") ? "biped_ppo_walk" : exps[0] ?? "";
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [b, ping]);

  const loadRuns = useCallback(async () => {
    if (!experiment) return;
    try {
      const data = await isaacRlLogFetchRuns(experiment, b);
      const opts = data.runs.map((r) => ({
        id: r.id,
        label: `${r.id}${r.latest_iteration != null ? ` (iter ${Math.round(r.latest_iteration)})` : ""}`,
      }));
      setRunOptions(opts);
      setRunId((prev) => {
        if (prev && opts.some((o) => o.id === prev)) return prev;
        return opts[0]?.id ?? "";
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [b, experiment]);

  const loadScalars = useCallback(async () => {
    if (!experiment || !runId) return;
    setLoading(true);
    try {
      const [sc, mt] = await Promise.all([
        isaacRlLogFetchScalars(experiment, runId, b),
        isaacRlLogFetchRunMeta(experiment, runId, b),
      ]);
      setScalars(sc);
      setMeta(mt);
      setLastFetchedAt(new Date());
      setErr(null);
      setConnected(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [b, experiment, runId]);

  useEffect(() => {
    void loadExperiments();
  }, [loadExperiments]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    void loadScalars();
  }, [loadScalars]);

  // 20 秒ごとにグラフ更新
  useEffect(() => {
    if (!experiment || !runId) return;
    const id = window.setInterval(() => {
      void loadScalars();
    }, ISAAC_RL_LOG_POLL_MS);
    return () => window.clearInterval(id);
  }, [experiment, runId, loadScalars]);

  const summaryMetrics = ISAAC_RL_METRICS.filter((m) => m.summary);
  const primaryMetrics = ISAAC_RL_METRICS.filter((m) => m.tier === "primary");
  const secondaryMetrics = ISAAC_RL_METRICS.filter((m) => m.tier === "secondary");

  const applyTailscaleApiUrl = () => {
    if (!accessUrls?.tailscale) return;
    setApiBase(accessUrls.tailscale.replace(/\/$/, ""));
    try {
      localStorage.setItem(LS_ISAAC_RL_LOG_API, accessUrls.tailscale.replace(/\/$/, ""));
    } catch {
      /* ignore */
    }
  };

  const maxIter = scalars?.latest_iteration;
  const latestCkpt = meta?.checkpoints?.length
    ? meta.checkpoints[meta.checkpoints.length - 1]
    : null;

  return (
    <div className="isaac-log">
      <header className="isaac-log__header">
        <div>
          <h1 className="isaac-log__title">Isaac 学習進捗</h1>
          <p className="isaac-log__lead">
            test-isaac-project の RSL-RL ログ（TensorBoard）を読み取り、学習曲線を表示します。
            画面は <strong>{ISAAC_RL_LOG_POLL_MS / 1000} 秒</strong>ごとに自動更新されます。
          </p>
        </div>
      </header>

      <section className="isaac-log__panel isaac-log__panel--status">
        <div className="isaac-log__status-row">
          <span
            className={
              "isaac-log__badge " +
              (connected === true
                ? "isaac-log__badge--ok"
                : connected === false
                  ? "isaac-log__badge--err"
                  : "")
            }
          >
            {connected === true ? "API 接続 OK" : connected === false ? "API 未接続" : "確認中…"}
          </span>
          {loading ? <span className="isaac-log__meta">更新中…</span> : null}
          {lastFetchedAt ? (
            <span className="isaac-log__meta">最終取得: {lastFetchedAt.toLocaleTimeString("ja-JP")}</span>
          ) : null}
          {scalars?.events_mtime_iso ? (
            <span className="isaac-log__meta">ログ更新: {fmtTime(scalars.events_mtime_iso)}</span>
          ) : null}
        </div>
        {logRoot ? (
          <p className="isaac-log__log-root">
            log_root: <code>{logRoot}</code>
          </p>
        ) : null}
        {accessUrls?.tailscale ? (
          <div className="isaac-log__tailscale">
            <span className="isaac-log__tailscale-label">Tailscale API</span>
            <code className="isaac-log__tailscale-url">{accessUrls.tailscale}</code>
            <button type="button" className="isaac-log__btn isaac-log__btn--sm" onClick={applyTailscaleApiUrl}>
              この URL を適用
            </button>
          </div>
        ) : null}
        {err ? <div className="isaac-log__error">{err}</div> : null}
      </section>

      <section className="isaac-log__panel">
        <h2 className="isaac-log__section-title">接続設定</h2>
        <div className="isaac-log__config">
          <label className="isaac-log__field">
            <span>ログ API URL</span>
            <input
              type="url"
              value={apiBase}
              onChange={(e) => setApiBase(e.target.value.replace(/\/$/, ""))}
              placeholder="http://192.168.x.x:8792"
            />
          </label>
          <div className="isaac-log__config-actions">
            <button type="button" className="isaac-log__btn" onClick={() => void loadExperiments()}>
              再接続
            </button>
            <button type="button" className="isaac-log__btn isaac-log__btn--ghost" onClick={persistApiBase}>
              URL を保存
            </button>
            <button type="button" className="isaac-log__btn isaac-log__btn--ghost" onClick={() => void loadScalars()}>
              今すぐ更新
            </button>
          </div>
        </div>
        <p className="isaac-log__hint">
          学習 PC で <code>.\start.ps1</code> を起動（<code>0.0.0.0:8792</code>）。外出先のスマホは Tailscale
          接続後、API URL に <code>http://100.x.x.x:8792</code>（PC の Tailscale IP）を指定してください。
        </p>
      </section>

      <section className="isaac-log__panel">
        <h2 className="isaac-log__section-title">Run 選択</h2>
        <div className="isaac-log__selectors">
          <label className="isaac-log__field">
            <span>experiment</span>
            <select value={experiment} onChange={(e) => setExperiment(e.target.value)}>
              {experiments.length === 0 ? <option value="">（なし）</option> : null}
              {experiments.map((exp) => (
                <option key={exp} value={exp}>
                  {exp}
                </option>
              ))}
            </select>
          </label>
          <label className="isaac-log__field">
            <span>run</span>
            <select value={runId} onChange={(e) => setRunId(e.target.value)}>
              {runOptions.length === 0 ? <option value="">（なし）</option> : null}
              {runOptions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {maxIter != null || latestCkpt ? (
          <div className="isaac-log__run-meta">
            {maxIter != null ? <span>最新 iter: {Math.round(maxIter)}</span> : null}
            {latestCkpt ? <span>最新 ckpt: {latestCkpt}</span> : null}
            {meta?.agent && typeof meta.agent.max_iterations === "number" ? (
              <span>max_iterations: {String(meta.agent.max_iterations)}</span>
            ) : null}
          </div>
        ) : null}
      </section>

      {scalars && (
        <>
          <section className="isaac-log__summary" aria-label="主要指標サマリー">
            {summaryMetrics.map((def) => {
              const latest = scalars.latest[def.tag];
              if (!latest) return null;
              return (
                <div key={def.tag} className="isaac-log__summary-card">
                  <span className="isaac-log__summary-label">{def.labelShort ?? def.label}</span>
                  <span className="isaac-log__summary-value" style={{ color: def.color }}>
                    {latest.value.toFixed(def.decimals ?? 2)}
                  </span>
                  <span className="isaac-log__summary-step">iter {Math.round(latest.step)}</span>
                </div>
              );
            })}
          </section>

          <section className="isaac-log__charts isaac-log__charts--primary">
            {primaryMetrics.map((def) => (
              <MetricLineChart
                key={def.tag}
                title={def.label}
                subtitle={def.description}
                color={def.color}
                data={scalars.series[def.tag] ?? []}
                valueDecimals={def.decimals ?? 2}
              />
            ))}
          </section>

          <section className="isaac-log__panel">
            <button
              type="button"
              className="isaac-log__collapse-btn"
              onClick={() => setShowSecondary((v) => !v)}
              aria-expanded={showSecondary}
            >
              {showSecondary ? "詳細指標を隠す" : "Loss / FPS など詳細指標を表示"}
            </button>
            {showSecondary ? (
              <div className="isaac-log__charts isaac-log__charts--secondary">
                {secondaryMetrics.map((def) => {
                  const data = scalars.series[def.tag] ?? [];
                  if (data.length === 0) return null;
                  return (
                    <MetricLineChart
                      key={def.tag}
                      title={def.label}
                      subtitle={def.description}
                      color={def.color}
                      data={data}
                      compact
                      valueDecimals={def.decimals ?? 2}
                    />
                  );
                })}
                {/* 定義外のカスタム tag */}
                {Object.keys(scalars.series)
                  .filter((tag) => !ISAAC_RL_METRIC_BY_TAG[tag])
                  .map((tag) => (
                    <MetricLineChart
                      key={tag}
                      title={tag}
                      color="#8b949e"
                      data={scalars.series[tag] ?? []}
                      compact
                    />
                  ))}
              </div>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}
