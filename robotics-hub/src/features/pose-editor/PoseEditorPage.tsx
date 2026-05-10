import { useEffect, useState } from "react";
import { getMujocoSimUrl } from "@/shared/constants";
import { PoseEditorOverviewSection } from "./components/overview/PoseEditorOverviewSection";
import { PoseEditorSideDetailSection } from "./components/side/PoseEditorSideDetailSection";
import { usePoseEditorControl } from "./hooks/usePoseEditorControl";
import { usePoseEditorData } from "./hooks/usePoseEditorData";
import type { PoseBackendMode } from "./types";
import "./PoseEditorPage.css";

const BACKEND_STORAGE_KEY = "pose-editor-backend";

function readStoredBackend(): PoseBackendMode {
  try {
    const v = sessionStorage.getItem(BACKEND_STORAGE_KEY);
    if (v === "mujoco" || v === "daemon") return v;
  } catch {
    /* noop */
  }
  return "daemon";
}

export default function PoseEditorPage() {
  const [backendMode, setBackendMode] = useState<PoseBackendMode>(readStoredBackend);

  useEffect(() => {
    try {
      sessionStorage.setItem(BACKEND_STORAGE_KEY, backendMode);
    } catch {
      /* noop */
    }
  }, [backendMode]);

  const { servos, loading, error } = usePoseEditorData(backendMode);
  const { readout, activeDrag, onArrowDown } = usePoseEditorControl(
    servos,
    error,
    backendMode
  );

  if (loading) {
    return (
      <div className="pose-editor pose-editor--centered">
        <h1 className="pose-editor-title">ポーズエディタ</h1>
        <p>読み込み中…</p>
      </div>
    );
  }

  const backendLabel =
    backendMode === "mujoco"
      ? `MuJoCo（${getMujocoSimUrl()}）`
      : "実機（robot-daemon）";

  return (
    <div className="pose-editor">
      <header className="pose-editor-header">
        <div className="pose-editor-header-row">
          <h1 className="pose-editor-title">ポーズエディタ</h1>
          <label className="pose-editor-backend">
            <span className="pose-editor-backend-label">連携先</span>
            <select
              className="pose-editor-backend-select"
              value={backendMode}
              onChange={(e) =>
                setBackendMode(e.target.value as PoseBackendMode)
              }
              aria-label="ポーズ指令の送信先"
            >
              <option value="daemon">実機（robot-daemon）</option>
              <option value="mujoco">MuJoCo（mujoco-sim）</option>
            </select>
          </label>
        </div>
        <p className="pose-editor-lead">
          メモ風の脚スケッチをドラッグして関節角を変えます。数値は論理角（度）です。
          {backendMode === "mujoco" ? (
            <>
              {" "}
              MuJoCo モードでは角度をラジアンに換算してシミュへ送ります（表示は度）。
            </>
          ) : null}
        </p>
        <p className="pose-editor-backend-hint">現在: {backendLabel}</p>
        {error ? (
          <p className="pose-editor-warn" role="alert">
            {backendMode === "mujoco"
              ? `mujoco-sim に接続できませんでした（${error}）。シミュを起動しているか、URL（既定は同一ホストの :8787）を確認してください。`
              : `サーボ API に接続できませんでした（${error}）。表示とドラッグは試せますが、実機への反映は失敗します。`}
          </p>
        ) : null}
      </header>

      <div className="pose-editor-grid">
        <PoseEditorOverviewSection
          left={readout.L}
          right={readout.R}
          activeDrag={activeDrag}
          onArrowDown={onArrowDown}
        />
        <PoseEditorSideDetailSection
          readout={readout}
          servos={servos}
          activeDrag={activeDrag}
          onArrowDown={onArrowDown}
        />
      </div>
    </div>
  );
}
