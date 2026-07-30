import { useCallback, useEffect, useMemo, useState } from "react";
import { getCaptureRealtimeBaseUrl } from "@/shared/constants";
import {
  fetchExperimentTakes,
  fetchExperiments,
  type RecorderExperiment,
  type RecorderTakeDescription,
} from "@/shared/recorderApi";
import { resolveLabFormat } from "@/features/lab-data-viewer/registry";
import "./LabDataViewerPage.css";

/**
 * 実機 Recorder データのラボ用ビュワー（既存 /data-viewer とは別ツール）。
 * 実験 → take を選び、format_id に応じたサブビュワーを表示する。
 */
export default function LabDataViewerPage() {
  const recorderBaseUrl = useMemo(() => getCaptureRealtimeBaseUrl(), []);
  const [experiments, setExperiments] = useState<RecorderExperiment[]>([]);
  const [experimentId, setExperimentId] = useState("");
  const [takes, setTakes] = useState<RecorderTakeDescription[]>([]);
  const [takeId, setTakeId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshExperiments = useCallback(async () => {
    try {
      const data = await fetchExperiments();
      setExperiments(data.experiments);
      setError(null);
      if (!experimentId && data.experiments.length > 0) {
        const preferred =
          data.experiments.find((e) => e.id === data.active_experiment_id) ??
          data.experiments[0];
        if (preferred) setExperimentId(preferred.id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [experimentId]);

  useEffect(() => {
    void refreshExperiments();
  }, [refreshExperiments]);

  useEffect(() => {
    if (!experimentId) {
      setTakes([]);
      setTakeId("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const list = await fetchExperimentTakes(experimentId);
        if (cancelled) return;
        setTakes(list);
        setTakeId((prev) =>
          list.some((t) => t.take_id === prev) ? prev : list[0]?.take_id ?? ""
        );
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setTakes([]);
        setTakeId("");
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [experimentId]);

  const selectedTake = takes.find((t) => t.take_id === takeId) ?? null;
  const formatEntry = selectedTake
    ? resolveLabFormat(selectedTake.format_id)
    : null;
  const FormatViewer = formatEntry?.Viewer;

  return (
    <div className="lab-dv">
      <header className="lab-dv__header">
        <h1>ラボデータビュワー</h1>
        <p>
          robot-recorder の実験／take を <code>format_id</code> 別ビュワーで確認します。
          YouTube 紹介の「データビュワー」(<code>/data-viewer</code>) とは別ツールです。
        </p>
        <p className="lab-dv__recorder">Recorder: {recorderBaseUrl}</p>
      </header>

      <div className="lab-dv__controls">
        <label className="lab-dv__field">
          <span>実験</span>
          <select
            value={experimentId}
            onChange={(e) => setExperimentId(e.target.value)}
            disabled={experiments.length === 0}
          >
            {experiments.length === 0 ? (
              <option value="">（実験なし — Recorder で作成）</option>
            ) : (
              experiments.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}（{e.id}）
                </option>
              ))
            )}
          </select>
        </label>

        <label className="lab-dv__field">
          <span>take</span>
          <select
            value={takeId}
            onChange={(e) => setTakeId(e.target.value)}
            disabled={takes.length === 0}
          >
            {takes.length === 0 ? (
              <option value="">（take なし）</option>
            ) : (
              takes.map((t) => (
                <option key={t.take_id} value={t.take_id}>
                  {t.take_id}
                  {t.has_video ? "" : " [no video]"}
                  {" · "}
                  {t.format_id}
                </option>
              ))
            )}
          </select>
        </label>

        <button
          type="button"
          className="lab-dv__btn"
          onClick={() => void refreshExperiments()}
        >
          一覧更新
        </button>
      </div>

      {error ? (
        <div className="lab-dv__error" role="alert">
          {error}
        </div>
      ) : null}
      {loading ? <p className="lab-dv__hint">読み込み中…</p> : null}

      {!selectedTake ? (
        <p className="lab-dv__hint">
          実験を選び、録画済み take を選択してください（<code>npm run dev:lab</code> で
          Recorder 起動が必要です）。
        </p>
      ) : !FormatViewer ? (
        <div className="lab-dv__error" role="alert">
          未対応の format_id: <code>{selectedTake.format_id}</code>
          。registry にサブビュワーを追加してください。
        </div>
      ) : (
        <FormatViewer take={selectedTake} recorderBaseUrl={recorderBaseUrl} />
      )}
    </div>
  );
}
