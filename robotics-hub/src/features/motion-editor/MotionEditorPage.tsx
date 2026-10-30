import MotionContextProvider from "./components/MotionContextProvider";
import AppContent from "./components/AppContent";
import { useMotionContext } from "./contexts/MotionContext";
import { getMujocoSimUrl } from "@/shared/constants";
import "./MotionEditorPage.css";

function MotionEditorHeader() {
  const { backendError } = useMotionContext();

  return (
    <div className="app-header">
      <div className="motion-editor-header-row">
        <h1>モーションエディタ</h1>
      </div>
      <p className="motion-editor-backend-hint">再生先: MuJoCo（{getMujocoSimUrl()}）</p>
      {backendError ? (
        <p className="motion-editor-warn" role="alert">
          mujoco-sim に接続できませんでした（{backendError}）。シミュを起動しているか、URL（既定は同一ホストの
          :8787）を確認してください。
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
