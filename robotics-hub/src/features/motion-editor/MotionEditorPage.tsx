import MotionContextProvider from "./components/MotionContextProvider";
import AppContent from "./components/AppContent";
import "./MotionEditorPage.css";

export default function MotionEditorPage() {
  return (
    <div className="motion-editor-page">
      <div className="app">
        <div className="app-header">
          <h1>モーションエディタ</h1>
        </div>
        <MotionContextProvider>
          <AppContent />
        </MotionContextProvider>
      </div>
    </div>
  );
}
