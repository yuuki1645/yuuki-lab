import type { ServoMode } from "@/shared/types";

interface ModeSelectorProps {
  mode: ServoMode;
  onChange: (mode: ServoMode) => void;
}

export default function ModeSelector({ mode, onChange }: ModeSelectorProps) {
  return (
    <div className="leg-tuner-mode">
      <label className="leg-tuner-mode-item">
        <input
          type="radio"
          name="leg-servo-mode"
          value="logical"
          checked={mode === "logical"}
          onChange={() => onChange("logical")}
        />
        論理角
      </label>
      <label className="leg-tuner-mode-item">
        <input
          type="radio"
          name="leg-servo-mode"
          value="physical"
          checked={mode === "physical"}
          onChange={() => onChange("physical")}
        />
        物理角
      </label>
    </div>
  );
}
