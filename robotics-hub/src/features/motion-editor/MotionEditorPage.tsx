import MotionContextProvider from "./components/MotionContextProvider";
import AppContent from "./components/AppContent";
import { useMotionContext } from "./contexts/MotionContext";
import { getMujocoSimUrl } from "@/shared/constants";
import type { ServoBackendMode } from "@/shared/types";
import "./MotionEditorPage.css";

function MotionEditorHeader() {
  const { backendMode, setBackendMode, backendError } = useMotionContext();
  const backendLabel =
    backendMode === "mujoco"
      ? `MuJoCo（${getMujocoSimUrl()}）`
      : "実機（robot-daemon）";

  return (
    <div className="app-header">
      <div className="motion-editor-header-row">
        <h1>モーションエディタ</h1>
        <label className="motion-editor-backend">
          <span className="motion-editor-backend-label">連携先</span>
          <select
            className="motion-editor-backend-select"
            value={backendMode}
            onChange={(e) => setBackendMode(e.target.value as ServoBackendMode)}
            aria-label="モーション指令の送信先"
          >
            <option value="daemon">実機（robot-daemon）</option>
            <option value="mujoco">MuJoCo（mujoco-sim）</option>
          </select>
        </label>
      </div>
      <p className="motion-editor-backend-hint">現在: {backendLabel}</p>
      {backendError ? (
        <p className="motion-editor-warn" role="alert">
          {backendMode === "mujoco"
            ? `mujoco-sim に接続できませんでした（${backendError}）。シミュを起動しているか、URL（既定は同一ホストの :8787）を確認してください。`
            : `サーボ API に接続できませんでした（${backendError}）。編集はできますが、再生や初期位置への反映は失敗します。`}
        </p>
      ) : null}
    </div>
  );
}

export default function MotionEditorPage() {
  return (
    <div className="motion-editor-page">
      <div className="app">
        <MotionContextProvider>
          <MotionEditorHeader />
          <AppContent />
        </MotionContextProvider>
      </div>
    </div>
  );
}
