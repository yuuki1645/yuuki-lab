import type { Servo } from "@/shared/types";

interface ServoSelectorProps {
  servos: Servo[];
  selectedServo: string;
  onChange: (name: string) => void;
}

export default function ServoSelector({
  servos,
  selectedServo,
  onChange,
}: ServoSelectorProps) {
  return (
    <>
      <label htmlFor="leg-servo-select">サーボ選択</label>
      <select
        id="leg-servo-select"
        value={selectedServo}
        onChange={(e) => onChange(e.target.value)}
      >
        {servos.map((servo) => (
          <option key={servo.name} value={servo.name}>
            {servo.name}
          </option>
        ))}
      </select>
    </>
  );
}
