import { useServos } from "@/shared/hooks/useServos";
import { PoseEditorOverviewSection } from "./PoseEditorOverviewSection";
import { PoseEditorSideDetailSection } from "./PoseEditorSideDetailSection";
import { usePoseEditorControl } from "./usePoseEditorControl";
import "./PoseEditorPage.css";

export default function PoseEditorPage() {
  const { servos, loading, error } = useServos();
  const { readout, activeDrag, onArrowDown } = usePoseEditorControl(
    servos,
    error
  );

  if (loading) {
    return (
      <div className="pose-editor pose-editor--centered">
        <h1 className="pose-editor-title">ポーズエディタ</h1>
        <p>読み込み中…</p>
      </div>
    );
  }

  return (
    <div className="pose-editor">
      <header className="pose-editor-header">
        <h1 className="pose-editor-title">ポーズエディタ</h1>
        <p className="pose-editor-lead">
          メモ風の脚スケッチをドラッグして関節角を変えます。数値は論理角（度）です。
        </p>
        {error ? (
          <p className="pose-editor-warn" role="alert">
            サーボ API に接続できませんでした（{error}）。表示とドラッグは試せますが、実機への反映は失敗します。
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
