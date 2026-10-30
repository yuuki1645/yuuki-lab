import { getMujocoSimUrl } from "@/shared/constants";
import { PoseEditorOverviewSection } from "./components/overview/PoseEditorOverviewSection";
import { PoseEditorSideDetailSection } from "./components/side/PoseEditorSideDetailSection";
import { usePoseEditorControl } from "./hooks/usePoseEditorControl";
import { usePoseEditorData } from "./hooks/usePoseEditorData";
import "./PoseEditorPage.css";

/**
 * 脚スケッチのドラッグで MuJoCo の論理角を変える。
 * 実機のサーボへは出さない。
 */
export default function PoseEditorPage() {
  const { servos, loading, error } = usePoseEditorData();
  const { readout, activeDrag, onArrowDown } = usePoseEditorControl(servos, error);

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
        <div className="pose-editor-header-row">
          <h1 className="pose-editor-title">ポーズエディタ</h1>
        </div>
        <p className="pose-editor-lead">
          メモ風の脚スケッチをドラッグして関節角を変えます。数値は論理角（度）です。
          角度はラジアンに換算して MuJoCo（{getMujocoSimUrl()}）へ送ります。表示は度のままです。
        </p>
        {error ? (
          <p className="pose-editor-warn" role="alert">
            mujoco-sim に接続できませんでした（{error}）。シミュを起動しているか、URL（既定は同一ホストの
            :8787）を確認してください。
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
