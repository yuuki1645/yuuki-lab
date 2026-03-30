import { PHYSICAL_MIN, PHYSICAL_MAX } from "@/shared/constants";
import type { Servo, ServoMode } from "@/shared/types";

interface AngleSliderProps {
  angle: number;
  mode: ServoMode;
  servo: Servo | undefined;
  onChange: (angle: number) => void;
}

export default function AngleSlider({ angle, mode, servo, onChange }: AngleSliderProps) {
  const getSliderRange = () => {
    if (!servo) {
      return { min: 0, max: 180 };
    }
    if (mode === "physical") {
      return { min: PHYSICAL_MIN, max: PHYSICAL_MAX };
    }
    return { min: servo.logical_lo, max: servo.logical_hi };
  };

  const generateTicks = (min: number, max: number, divisions = 5) => {
    const ticks: number[] = [];
    for (let i = 0; i <= divisions; i++) {
      const value = min + (max - min) * (i / divisions);
      ticks.push(Math.round(value));
    }
    return ticks;
  };

  const range = getSliderRange();
  const ticks = generateTicks(range.min, range.max, 5);

  return (
    <>
      <label>
        角度: <span>{angle}</span>°
        <span className="leg-tuner-hint">
          {mode === "physical"
            ? "（物理角：サーボ直指定）"
            : "（論理角：変換してサーボへ）"}
        </span>
      </label>

      <input
        type="range"
        min={range.min}
        max={range.max}
        step={1}
        value={angle}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
      <div className="leg-tuner-slider-ticks">
        {ticks.map((tick, index) => (
          <span key={index}>{tick}</span>
        ))}
      </div>
    </>
  );
}
