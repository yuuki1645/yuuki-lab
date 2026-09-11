import { useState } from "react";
import type { M5RecordMeta } from "./types";

type Props = {
  open: boolean;
  onClose: () => void;
  rows: M5RecordMeta[];
  loading: boolean;
  error: string | null;
  busy: boolean;
  playingId: string | null;
  onRefresh: () => void;
  onPlay: (id: string) => void;
  onSave: (id: string, name: string, notes: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
};

function fmtWhen(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function fmtDur(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec)) return "—";
  const s = Math.max(0, Math.round(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}:${String(m % 60).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  }
  return `${m}:${String(r).padStart(2, "0")}`;
}

function fmtBytes(n: number | undefined): string {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * PC に保存した本記録の一覧・メモ編集・削除。
 * 再生すると M5 画面全体がその時刻のサンプルを表示する。
 */
export function M5RecordLibrary({
  open,
  onClose,
  rows,
  loading,
  error,
  busy,
  playingId,
  onRefresh,
  onPlay,
  onSave,
  onDelete,
}: Props) {
  const [q, setQ] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const filtered = rows.filter((r) => {
    const hay = `${r.name} ${r.notes} ${r.atom_name} ${r.port} ${r.id}`.toLowerCase();
    return hay.includes(q.trim().toLowerCase());
  });

  const beginEdit = (row: M5RecordMeta) => {
    setEditId(row.id);
    setName(row.name);
    setNotes(row.notes);
  };

  return (
    <div className="m5-lib" role="dialog" aria-label="記録ライブラリ">
      <div className="m5-lib__scrim" onClick={onClose} />
      <aside className="m5-lib__panel">
        <header className="m5-lib__head">
          <div>
            <h2>記録ライブラリ</h2>
            <p>ATOM 接続 PC の <code>atom-rt/data/recordings</code>。名前とメモはここから直せます。</p>
          </div>
          <div className="m5-lib__head-actions">
            <button type="button" className="m5__btn" onClick={onRefresh} disabled={loading}>
              {loading ? "更新中…" : "更新"}
            </button>
            <button type="button" className="m5__btn" onClick={onClose}>
              閉じる
            </button>
          </div>
        </header>

        <input
          className="m5-lib__search"
          type="search"
          placeholder="名前・メモ・ATOM で検索"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />

        {error ? <div className="m5__error">{error}</div> : null}

        {filtered.length === 0 && !loading ? (
          <p className="m5-lib__empty">記録はまだありません。ライブ画面で「記録開始」してください。</p>
        ) : (
          <ul className="m5-lib__list">
            {filtered.map((row) => {
              const active = playingId === row.id;
              const editing = editId === row.id;
              return (
                <li key={row.id} className={"m5-lib__card" + (active ? " m5-lib__card--on" : "")}>
                  <div className="m5-lib__card-top">
                    <strong>{row.name || row.id}</strong>
                    {row.recording ? <span className="m5-lib__tag m5-lib__tag--rec">記録中</span> : null}
                    {row.camera?.take_id || row.camera?.mp4_url ? (
                      <span className="m5-lib__tag">映像</span>
                    ) : null}
                    {active ? <span className="m5-lib__tag">再生中</span> : null}
                  </div>
                  <dl className="m5-lib__meta">
                    <div>
                      <dt>開始</dt>
                      <dd>{fmtWhen(row.started_at)}</dd>
                    </div>
                    <div>
                      <dt>終了</dt>
                      <dd>{row.ended_at ? fmtWhen(row.ended_at) : "—"}</dd>
                    </div>
                    <div>
                      <dt>時間</dt>
                      <dd>{fmtDur(row.duration_sec)}</dd>
                    </div>
                    <div>
                      <dt>点数</dt>
                      <dd>{row.sample_count.toLocaleString()}</dd>
                    </div>
                    <div>
                      <dt>ATOM</dt>
                      <dd>{row.atom_name || row.port || "—"}</dd>
                    </div>
                    <div>
                      <dt>サイズ</dt>
                      <dd>{fmtBytes(row.bytes)}</dd>
                    </div>
                  </dl>
                  {!editing && row.notes ? <p className="m5-lib__notes">{row.notes}</p> : null}
                  {editing ? (
                    <div className="m5-lib__edit">
                      <input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="データ名"
                      />
                      <textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        placeholder="実験メモ（目的、配線、気づき）"
                        rows={3}
                      />
                      <div className="m5-lib__card-actions">
                        <button
                          type="button"
                          className="m5__btn m5__btn--on"
                          disabled={saving}
                          onClick={() => {
                            setSaving(true);
                            void onSave(row.id, name, notes).finally(() => {
                              setSaving(false);
                              setEditId(null);
                            });
                          }}
                        >
                          保存
                        </button>
                        <button type="button" className="m5__btn" onClick={() => setEditId(null)}>
                          キャンセル
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="m5-lib__card-actions">
                      <button
                        type="button"
                        className="m5__btn m5__btn--on"
                        disabled={busy || row.recording || row.sample_count < 1}
                        onClick={() => onPlay(row.id)}
                      >
                        再生
                      </button>
                      <button type="button" className="m5__btn" onClick={() => beginEdit(row)}>
                        メモ
                      </button>
                      <button
                        type="button"
                        className="m5__btn m5__btn--danger"
                        disabled={row.recording}
                        onClick={() => {
                          if (!window.confirm(`「${row.name}」を削除しますか？ PC 上のファイルも消えます。`)) return;
                          void onDelete(row.id);
                        }}
                      >
                        削除
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </aside>
    </div>
  );
}
