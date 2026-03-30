import { useState, useEffect, useRef } from "react";
import { useServos } from "@/shared/hooks/useServos";
import { moveServo } from "@/shared/api/servoApi";
import { SERVO_NAME_TO_CH } from "@/shared/constants";
import type { ServoMode } from "@/shared/types";
import ModeSelector from "./components/ModeSelector";
import ServoSelector from "./components/ServoSelector";
import TunerGuideImage from "./components/TunerGuideImage";
import AngleSlider from "./components/AngleSlider";
import "./LegServoTunerPage.css";

export default function LegServoTunerPage() {
  const { servos, loading, error } = useServos();
  const [selectedServo, setSelectedServo] = useState("");
  const [mode, setMode] = useState<ServoMode>("logical");
  const [angle, setAngle] = useState(0);
  /** スライダーで変更した角度（API の初回値が古いままでも再選択時に復元する） */
  const angleOverridesRef = useRef<
    Partial<Record<string, Partial<Record<ServoMode, number>>>>
  >({});

  useEffect(() => {
    if (servos.length > 0 && !selectedServo) {
      setSelectedServo(servos[0]!.name);
      setMode("logical");
    }
  }, [servos, selectedServo]);

  useEffect(() => {
    if (servos.length === 0 || !selectedServo) return;

    const servo = servos.find((s) => s.name === selectedServo);
    if (!servo) return;

    const cached = angleOverridesRef.current[selectedServo]?.[mode];
    if (cached !== undefined) {
      setAngle(Math.round(cached));
      return;
    }
    const newAngle =
      mode === "physical" ? servo.last_physical : servo.last_logical;
    setAngle(Math.round(newAngle));
  }, [selectedServo, mode, servos]);

  const handleAngleChange = async (newAngle: number) => {
    setAngle(newAngle);

    if (!selectedServo) return;

    const prev = angleOverridesRef.current[selectedServo] ?? {};
    angleOverridesRef.current = {
      ...angleOverridesRef.current,
      [selectedServo]: { ...prev, [mode]: newAngle },
    };

    const ch = SERVO_NAME_TO_CH[selectedServo];
    if (ch === undefined) {
      window.alert(`Unknown servo: ${selectedServo}`);
      return;
    }

    try {
      await moveServo(ch, mode, newAngle);
    } catch (err) {
      window.alert(
        `Network error:\n${err instanceof Error ? err.message : String(err)}`
      );
    }
  };

  const currentServo = servos.find((s) => s.name === selectedServo);

  if (loading) {
    return (
      <div className="leg-tuner leg-tuner--centered">
        <h1 className="leg-tuner-title">レッグサーボ調整</h1>
        <p>読み込み中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="leg-tuner leg-tuner--centered">
        <h1 className="leg-tuner-title">レッグサーボ調整</h1>
        <p className="leg-tuner-error">エラー: {error}</p>
        <p className="leg-tuner-help">
          servo-daemon（同一ホストのポート 5000）が起動しているか確認してください。
        </p>
      </div>
    );
  }

  return (
    <div className="leg-tuner">
      <h1 className="leg-tuner-title">レッグサーボ調整</h1>

      <div className="leg-tuner-panel">
        <ModeSelector mode={mode} onChange={setMode} />

        <ServoSelector
          servos={servos}
          selectedServo={selectedServo}
          onChange={setSelectedServo}
        />

        <TunerGuideImage servoName={selectedServo} />

        <AngleSlider
          angle={angle}
          mode={mode}
          servo={currentServo}
          onChange={handleAngleChange}
        />
      </div>
    </div>
  );
}
