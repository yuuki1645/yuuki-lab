import { useCallback, useEffect, useState } from "react";
import {
  createExperiment,
  deleteExperiment,
  fetchExperiments,
  renameExperiment,
  selectExperiment,
  type RecorderExperiment,
} from "@/shared/recorderApi";

type ExperimentManagerProps = {
  /** 録画中は実験の切替・削除を禁止 */
  recording: boolean;
  onActiveChange?: (experimentId: string | null) => void;
};

/**
 * 録り込む実験フォルダの選択・作成・改名・削除。
 */
export default function ExperimentManager({
  recording,
  onActiveChange,
}: ExperimentManagerProps) {
  const [items, setItems] = useState<RecorderExperiment[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [renameName, setRenameName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchExperiments();
      setItems(data.experiments);
      setActiveId(data.active_experiment_id);
      onActiveChange?.(data.active_experiment_id);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [onActiveChange]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => {
      void refresh();
    }, 3000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    const cur = items.find((x) => x.id === activeId);
    if (cur) setRenameName(cur.name);
  }, [activeId, items]);

  const onSelect = async (id: string) => {
    if (recording) return;
    setBusy(true);
    try {
      await selectExperiment(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onCreate = async () => {
    if (recording) return;
    const name = newName.trim();
    if (!name) return;
    setBusy(true);
    try {
      const exp = await createExperiment(name);
      setNewName("");
      await selectExperiment(exp.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onRename = async () => {
    if (recording || !activeId) return;
    const name = renameName.trim();
    if (!name) return;
    setBusy(true);
    try {
      await renameExperiment(activeId, name);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async () => {
    if (recording || !activeId) return;
    if (!window.confirm("この実験フォルダを削除しますか？（takes が空のときのみ）")) {
      return;
    }
    setBusy(true);
    try {
      await deleteExperiment(activeId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="live-capture__section live-capture__experiments" aria-label="実験フォルダ">
      <h2 className="live-capture__section-title">実験フォルダ</h2>
      <p className="live-capture__hint">
        記録データは選択中の実験フォルダ配下の take に入ります。公開から外す実験はフォルダごと管理できます。
      </p>

      <div className="live-capture__exp-row">
        <label className="live-capture__exp-label" htmlFor="exp-select">
          録り込む実験
        </label>
        <select
          id="exp-select"
          className="live-capture__exp-select"
          disabled={busy || recording || items.length === 0}
          value={activeId ?? ""}
          onChange={(e) => void onSelect(e.target.value)}
        >
          {items.length === 0 ? (
            <option value="">（実験がありません）</option>
          ) : (
            items.map((exp) => (
              <option key={exp.id} value={exp.id}>
                {exp.name}（{exp.id} / takes:{exp.take_count ?? 0}）
              </option>
            ))
          )}
        </select>
      </div>

      <div className="live-capture__exp-row">
        <input
          className="live-capture__exp-input"
          type="text"
          placeholder="新規実験名"
          value={newName}
          disabled={busy || recording}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void onCreate();
          }}
        />
        <button
          type="button"
          className="live-capture__btn live-capture__btn--primary"
          disabled={busy || recording || !newName.trim()}
          onClick={() => void onCreate()}
        >
          作成して選択
        </button>
      </div>

      {activeId ? (
        <div className="live-capture__exp-row">
          <input
            className="live-capture__exp-input"
            type="text"
            value={renameName}
            disabled={busy || recording}
            onChange={(e) => setRenameName(e.target.value)}
            aria-label="実験の表示名"
          />
          <button
            type="button"
            className="live-capture__btn"
            disabled={busy || recording || !renameName.trim()}
            onClick={() => void onRename()}
          >
            名称変更
          </button>
          <button
            type="button"
            className="live-capture__btn live-capture__btn--danger"
            disabled={busy || recording}
            onClick={() => void onDelete()}
          >
            削除
          </button>
        </div>
      ) : null}

      {error ? (
        <div className="live-capture__error" role="alert">
          {error}
        </div>
      ) : null}
    </section>
  );
}
