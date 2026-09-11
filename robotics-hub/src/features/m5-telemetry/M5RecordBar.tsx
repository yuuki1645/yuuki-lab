import type { useM5Camera } from "./useM5Camera";
import type { useM5Recording } from "./useM5Recording";

type Rec = ReturnType<typeof useM5Recording>;
type Cam = ReturnType<typeof useM5Camera>;

type Props = {
  rec: Rec;
  atomOk: boolean;
  camera: Cam;
};

function fmtClock(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return "00:00.00";
  const ms = Math.floor((sec % 1) * 100);
  const s = Math.floor(sec);
  const m = Math.floor(s / 60);
  const r = s % 60;
  const h = Math.floor(m / 60);
  const mm = String(m % 60).padStart(2, "0");
  const ss = String(r).padStart(2, "0");
  const cc = String(ms).padStart(2, "0");
  // 分は常に 2 桁。1 時間超だけ時を足す（桁位置が秒ごとに動かない）
  if (h > 0) return `${h}:${mm}:${ss}.${cc}`;
  return `${mm}:${ss}.${cc}`;
}

/**
 * 記録開始／停止と、再生ヘッド（シーク・±1/5/10）。
 * sticky にしてタブを切り替えても同時刻のデータを見続けられる。
 */
export function M5RecordBar({ rec, atomOk, camera }: Props) {
  const liveRec = Boolean(rec.recordStatus?.recording);
  const replaying = rec.mode === "replay";
  const camRec = Boolean(camera.status?.recording);
  const camHint = camera.startError
    ? `映像を録画できていません: ${camera.startError}`
    : camera.linkError
      ? `カメラ未接続: ${camera.linkError}`
      : camera.status?.capture_error && !camera.status.has_frame
        ? camera.status.capture_error
        : null;

  return (
    <section
      className={
        "m5-rec" + (liveRec ? " m5-rec--hot" : "") + (replaying ? " m5-rec--replay" : "")
      }
      aria-label="記録と再生"
    >
      <div className="m5-rec__row">
        <div className="m5-rec__identity">
          {liveRec ? (
            <>
              <span className="m5-rec__dot" aria-hidden />
              <div>
                <strong>記録中{camRec ? " · 映像REC" : camera.busy ? " · 映像開始中" : ""}</strong>
                <p>
                  {rec.recordStatus?.name || "無題"}
                  {" · "}
                  <span className="m5-rec__nums">{fmtClock(rec.recordStatus?.elapsed_sec ?? 0)}</span>
                  {" · "}
                  <span className="m5-rec__nums m5-rec__nums--count">
                    {(rec.recordStatus?.sample_count ?? 0).toLocaleString()} 点
                  </span>
                </p>
              </div>
            </>
          ) : replaying ? (
            <>
              <span className="m5-rec__badge">再生</span>
              <div>
                <strong>{rec.meta?.name || "記録"}</strong>
                <p>
                  <span className="m5-rec__nums">
                    {fmtClock(rec.tNow)} / {fmtClock(rec.tEnd)}
                  </span>
                  {" · "}
                  <span className="m5-rec__nums m5-rec__nums--count">
                    {rec.index + 1} / {rec.sampleCount} 点
                  </span>
                </p>
              </div>
            </>
          ) : (
            <>
              <span className="m5-rec__badge m5-rec__badge--live">ライブ</span>
              <div>
                <strong>本記録</strong>
                <p>開始を押した区間だけ PC に残します。あとからこの画面で再生できます。</p>
              </div>
            </>
          )}
        </div>

        <div className="m5-rec__actions">
          {liveRec ? (
            <button type="button" className="m5__btn m5__btn--danger" onClick={rec.stopRecord}>
              記録停止
            </button>
          ) : replaying ? (
            <button type="button" className="m5__btn" onClick={rec.exitReplay}>
              ライブへ戻る
            </button>
          ) : (
            <button
              type="button"
              className="m5__btn m5__btn--danger"
              disabled={!atomOk}
              onClick={() => rec.startRecord(rec.draftName.trim(), rec.draftNotes.trim())}
            >
              記録開始
            </button>
          )}
          <button
            type="button"
            className="m5__btn"
            onClick={() => rec.setLibraryOpen(true)}
          >
            ライブラリ
          </button>
        </div>
      </div>

      {!liveRec && !replaying ? (
        <div className="m5-rec__draft">
          <label>
            データ名
            <input
              value={rec.draftName}
              onChange={(e) => rec.setDraftName(e.target.value)}
              placeholder="例: 右脚 磁石確認"
            />
          </label>
          <label className="m5-rec__draft-notes">
            実験メモ
            <input
              value={rec.draftNotes}
              onChange={(e) => rec.setDraftNotes(e.target.value)}
              placeholder="目的・配線・気づき（後から編集可）"
            />
          </label>
        </div>
      ) : null}

      {replaying ? (
        <div className="m5-rec__transport">
          {rec.steps.map((n) => (
            <button
              key={`b${n}`}
              type="button"
              className="m5-rec__step"
              onClick={() => rec.step(-n)}
              aria-label={`${n} フレーム戻る`}
            >
              −{n}
            </button>
          ))}
          <button
            type="button"
            className="m5__btn m5__btn--on m5-rec__play"
            onClick={() => rec.setPlaying(!rec.playing)}
          >
            {rec.playing ? "一時停止" : "再生"}
          </button>
          {rec.steps.map((n) => (
            <button
              key={`f${n}`}
              type="button"
              className="m5-rec__step"
              onClick={() => rec.step(n)}
              aria-label={`${n} フレーム進む`}
            >
              +{n}
            </button>
          ))}
          <label className="m5-rec__rate">
            速度
            <select
              value={rec.rate}
              onChange={(e) => rec.setRate(Number(e.target.value) as (typeof rec.rates)[number])}
            >
              {rec.rates.map((r) => (
                <option key={r} value={r}>
                  {r}×
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {replaying ? (
        <label className="m5-rec__seek">
          <span className="m5-rec__seek-label">シーク</span>
          <input
            type="range"
            min={0}
            max={Math.max(0, rec.sampleCount - 1)}
            step={1}
            value={rec.index}
            onChange={(e) => {
              rec.setPlaying(false);
              rec.seek(Number(e.target.value));
            }}
          />
        </label>
      ) : null}

      {rec.recordStatus?.error ? <p className="m5__error">{rec.recordStatus.error}</p> : null}
      {camHint ? <p className="m5__error">{camHint}</p> : null}
      {rec.loadProgress ? (
        <p className="m5__meta">
          読み込み中{" "}
          <span className="m5-rec__nums">
            {rec.loadProgress.loaded.toLocaleString()} / {rec.loadProgress.total.toLocaleString()}
          </span>
        </p>
      ) : null}
    </section>
  );
}
