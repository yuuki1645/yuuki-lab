import { useCallback, useEffect, useMemo, useState } from "react";
import { getIsaacHubSocketUrl, getM5TelemetrySocketUrl } from "@/shared/constants";
import "./PolicyComparePage.css";

type TraceMeta = {
  id: string;
  name: string;
  side: string;
  sample_count: number;
  started_at: string;
};

type DimStat = {
  index: number;
  label: string;
  group: string;
  mean: number | null;
  std: number | null;
  n: number;
  missing_rate: number | null;
  jump_rate: number | null;
  shake_rate: number | null;
};

type SideSummary = {
  rows: number;
  dims: DimStat[];
  timing: {
    rows: number;
    period_us_median: number | null;
    overrun_rate: number | null;
    age_ms_median: number | null;
    safety_rate: number | null;
  };
};

type SeriesPoint = { t: number; v: number | null; flag: number; safety: number };

const EXPERIMENTS = ["直立", "1関節", "体重移動", "浅いしゃがみ"];

async function fetchJson<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(base.replace(/\/$/, "") + path, { cache: "no-store", ...init });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/** 実機の橋か、再生の橋。片方だけが起きている。 */
async function withBridge<T>(path: string, init?: RequestInit): Promise<T> {
  const bases = [getM5TelemetrySocketUrl(), getIsaacHubSocketUrl()];
  let last = "橋がありません";
  for (const base of bases) {
    try {
      return await fetchJson<T>(base, path, init);
    } catch (err) {
      last = err instanceof Error ? err.message : String(err);
    }
  }
  throw new Error(last);
}

function explain(err: unknown): string {
  const text = err instanceof Error ? err.message : String(err);
  if (text.includes("Failed to fetch") || text.includes("NetworkError")) {
    return "実機の橋（8794）も再生の橋（8795）も応答していません。どちらかを起動すると一覧が出ます。";
  }
  return text;
}

function fmt(value: number | null, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

function pct(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(100 * value).toFixed(1)}%`;
}

function SeriesChart({ points }: { points: SeriesPoint[] }) {
  const finite = points.map((p) => p.v).filter((v): v is number => v != null && Number.isFinite(v));
  if (points.length === 0) {
    return <p className="pcmp__empty">この記録には点がありません。</p>;
  }
  const width = 760;
  const height = 180;
  const pad = 16;
  const lo = finite.length ? Math.min(...finite) : 0;
  const hi = finite.length ? Math.max(...finite) : 1;
  const span = hi - lo || 1;
  const xOf = (i: number) => pad + (i / Math.max(1, points.length - 1)) * (width - pad * 2);
  const yOf = (v: number) => pad + (1 - (v - lo) / span) * (height - pad * 2);
  const parts: string[] = [];
  let pen = "";
  points.forEach((point, i) => {
    if (point.v == null) {
      if (pen) parts.push(pen);
      pen = "";
      return;
    }
    const cmd = `${xOf(i).toFixed(1)},${yOf(point.v).toFixed(1)}`;
    pen = pen ? `${pen} L ${cmd}` : `M ${cmd}`;
  });
  if (pen) parts.push(pen);
  return (
    <svg className="pcmp__chart" viewBox={`0 0 ${width} ${height}`} role="img">
      {parts.map((d, i) => (
        <path key={i} d={d} fill="none" stroke="currentColor" strokeWidth="1.6" />
      ))}
    </svg>
  );
}

export default function PolicyComparePage() {
  const [realList, setRealList] = useState<TraceMeta[]>([]);
  const [simList, setSimList] = useState<TraceMeta[]>([]);
  const [realId, setRealId] = useState("");
  const [simId, setSimId] = useState("");
  const [realSum, setRealSum] = useState<SideSummary | null>(null);
  const [simSum, setSimSum] = useState<SideSummary | null>(null);
  const [dim, setDim] = useState(0);
  const [side, setSide] = useState<"real" | "sim">("real");
  const [points, setPoints] = useState<SeriesPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [simName, setSimName] = useState(EXPERIMENTS[0]);

  const reload = useCallback(async () => {
    const body = await withBridge<{ real: TraceMeta[]; sim: TraceMeta[]; next_name?: string }>(
      "/api/policy-trace/list",
    );
    setRealList(body.real ?? []);
    setSimList(body.sim ?? []);
    if (body.next_name) setSimName(body.next_name);
    setRealId((cur) => cur || body.real?.[0]?.id || "");
    setSimId((cur) => cur || body.sim?.[0]?.id || "");
  }, []);

  useEffect(() => {
    void reload().catch((err: unknown) => {
      setError(explain(err));
    });
  }, [reload]);

  const compare = useCallback(async () => {
    if (!realId || !simId) {
      setError("実機とシミュを 1 本ずつ選んでください。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = await withBridge<{ ok: boolean; real: SideSummary; sim: SideSummary }>(
        `/api/policy-trace/summary?real=${encodeURIComponent(realId)}&sim=${encodeURIComponent(simId)}`,
      );
      setRealSum(body.real);
      setSimSum(body.sim);
    } catch (err) {
      setError(explain(err));
    } finally {
      setBusy(false);
    }
  }, [realId, simId]);

  const loadSeries = useCallback(async () => {
    const id = side === "real" ? realId : simId;
    if (!id) return;
    try {
      const body = await withBridge<{ points: SeriesPoint[] }>(
        `/api/policy-trace/series?side=${side}&id=${encodeURIComponent(id)}&dim=${dim}`,
      );
      setPoints(body.points ?? []);
    } catch (err) {
      setError(explain(err));
    }
  }, [side, realId, simId, dim]);

  useEffect(() => {
    if (realSum && simSum) void loadSeries();
  }, [realSum, simSum, loadSeries]);

  const rows = useMemo(() => {
    if (!realSum || !simSum) return [];
    return realSum.dims.map((real, i) => ({ real, sim: simSum.dims[i] }));
  }, [realSum, simSum]);

  const selected = rows[dim];

  return (
    <section className="pcmp">
      <header className="pcmp__head">
        <h1>分布の比較</h1>
        <p>
          同じ実験の、有効な周期だけの平均とばらつきです。実験開始から何秒、という時刻同士は見ていません。
          欠測と飛びは平均に入れず、率だけを出します。
        </p>
      </header>

      <div className="pcmp__pick">
        <label>
          実機
          <select value={realId} onChange={(e) => setRealId(e.target.value)}>
            <option value="">選ぶ</option>
            {realList.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}（{row.sample_count} 点）
              </option>
            ))}
          </select>
        </label>
        <label>
          シミュ
          <select value={simId} onChange={(e) => setSimId(e.target.value)}>
            <option value="">選ぶ</option>
            {simList.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}（{row.sample_count} 点）
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="pcmp__go" disabled={busy} onClick={() => void compare()}>
          {busy ? "集計中" : "比べる"}
        </button>
        <button type="button" onClick={() => void reload().catch(() => undefined)}>
          一覧を更新
        </button>
      </div>

      <div className="pcmp__name">
        <span>次のシミュ再生の実験名</span>
        {EXPERIMENTS.map((name) => (
          <button
            key={name}
            type="button"
            className={simName === name ? "pcmp__on" : ""}
            onClick={() => {
              setSimName(name);
              void withBridge("/api/policy-trace/sim-name", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name }),
              }).catch((err: unknown) => setError(explain(err)));
            }}
          >
            {name}
          </button>
        ))}
      </div>

      {error ? <p className="pcmp__error">{error}</p> : null}

      {realSum ? (
        <p className="pcmp__timing">
          実機の計測: 周期の中央値 {fmt((realSum.timing.period_us_median ?? 0) / 1000, 1)} ms、
          遅れの周期 {pct(realSum.timing.overrun_rate)}、
          値の古さの中央値 {fmt(realSum.timing.age_ms_median, 0)} ms、
          安全が働いた周期 {pct(realSum.timing.safety_rate)}。
          これは実機の質で、シミュの波形とは重ねません。
        </p>
      ) : null}

      {rows.length > 0 ? (
        <table className="pcmp__table">
          <thead>
            <tr>
              <th>量</th>
              <th>実機 平均</th>
              <th>実機 ばらつき</th>
              <th>実機 欠測</th>
              <th>実機 飛び</th>
              <th>シミュ 平均</th>
              <th>シミュ ばらつき</th>
              <th>差</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ real, sim }) => {
              const delta =
                real.mean != null && sim.mean != null ? sim.mean - real.mean : null;
              return (
                <tr
                  key={real.index}
                  className={real.index === dim ? "pcmp__selected" : ""}
                  onClick={() => setDim(real.index)}
                >
                  <td>{real.label}</td>
                  <td>{fmt(real.mean)}</td>
                  <td>{fmt(real.std)}</td>
                  <td>{pct(real.missing_rate)}</td>
                  <td>{pct(real.jump_rate)}</td>
                  <td>{fmt(sim?.mean ?? null)}</td>
                  <td>{fmt(sim?.std ?? null)}</td>
                  <td>{fmt(delta)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="pcmp__empty">記録が無いときは、実機は「記録開始」、シミュは再生を走らせてから一覧を更新します。</p>
      )}

      {selected ? (
        <div className="pcmp__series">
          <h2>{selected.real.label}</h2>
          <div className="pcmp__pick">
            <button type="button" className={side === "real" ? "pcmp__on" : ""} onClick={() => setSide("real")}>
              実機だけ
            </button>
            <button type="button" className={side === "sim" ? "pcmp__on" : ""} onClick={() => setSide("sim")}>
              シミュだけ
            </button>
          </div>
          <p>欠測と飛びの区間は線を切ります。もう片方の同じ秒数とは並べていません。</p>
          <SeriesChart points={points} />
        </div>
      ) : null}
    </section>
  );
}
