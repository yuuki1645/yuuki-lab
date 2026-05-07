# type: ignore

"""サーボの状態更新・一括操作・遷移（ハードウェアと state_manager の橋渡し）。"""

from __future__ import annotations

import threading
import time
from typing import Any

from kinematics import KINEMATICS
from servo import SERVO_MAP, move_servo_logical, move_servo_physical, move_servos_logical, move_servos_physical
from state_manager import StateManager

SERVO_CH_2_NAME: dict[int, str] = {
    0: "R_HIP1",
    1: "R_HIP2",
    2: "R_KNEE",
    3: "R_HEEL",
    4: "R_HEEL_ROLL",
    8: "L_HIP1",
    9: "L_HIP2",
    10: "L_KNEE",
    11: "L_HEEL",
    12: "L_HEEL_ROLL",
}


def parse_transition_payload(data: dict) -> tuple[str, dict[int, float], float]:
    mode = data.get("mode", "logical")
    angles = data.get("angles", {})
    duration = float(data.get("duration", 3.0))
    angles_dict = {int(ch_str): float(angle) for ch_str, angle in angles.items()}
    return mode, angles_dict, duration


class ServoController:
    """サーボ角度の設定・一覧・遷移を一手に扱う。"""

    def __init__(self, state_manager: StateManager) -> None:
        self._state = state_manager

    def list_payload(self) -> dict[str, Any]:
        state = self._state.get_all()
        servos = []
        for name, ch in SERVO_MAP.items():
            kin = KINEMATICS[name]
            ch_str = str(ch)
            servo_state = state.get(ch_str, {})
            servos.append(
                {
                    "name": name,
                    "ch": ch,
                    "logical_lo": kin.logical_range.lo,
                    "logical_hi": kin.logical_range.hi,
                    "physical_min": kin.physical_range.lo,
                    "physical_max": kin.physical_range.hi,
                    "default_logical": kin.default_logical,
                    "default_physical": kin.default_physical,
                    "last_logical": servo_state.get("logical"),
                    "last_physical": servo_state.get("physical"),
                }
            )
        return {"servos": servos}

    def set_angle(self, ch: int, angle: float, mode: str) -> dict[str, Any]:
        if mode == "logical":
            result = move_servo_logical(SERVO_CH_2_NAME[ch], angle)
        else:
            result = move_servo_physical(SERVO_CH_2_NAME[ch], angle)

        self._state.set(
            str(ch),
            {"logical": result["logical"], "physical": result["physical"]},
        )
        servo_name = SERVO_CH_2_NAME[ch]
        print(
            f"[SERVO] SUCCESS - {servo_name} (ch={ch}): "
            f"logical={result['logical']:.1f}, physical={result['physical']:.1f}"
        )
        return result

    def set_angles_batch(self, angles_dict: dict[int, float], mode: str) -> dict[str, list]:
        results: dict[str, list] = {"success": [], "errors": []}
        servo_angles: dict[str, float] = {}
        for ch, angle in angles_dict.items():
            if ch not in SERVO_CH_2_NAME:
                results["errors"].append({"ch": ch, "message": f"Unknown channel: {ch}"})
                continue
            servo_name = SERVO_CH_2_NAME[ch]
            servo_angles[servo_name] = float(angle)

        if not servo_angles:
            return results

        try:
            if mode == "logical":
                servo_results = move_servos_logical(servo_angles)
            else:
                servo_results = move_servos_physical(servo_angles)

            state_updates: dict[str, dict[str, float]] = {}
            for servo_name, result in servo_results.items():
                ch = result["ch"]
                state_updates[str(ch)] = {
                    "logical": result["logical"],
                    "physical": result["physical"],
                }
                results["success"].append(
                    {
                        "ch": ch,
                        "servo_name": servo_name,
                        "logical": result["logical"],
                        "physical": result["physical"],
                    }
                )
            for ch_str, state_data in state_updates.items():
                self._state.set(ch_str, state_data)
        except Exception as e:
            print(f"[SERVO] ERROR during batch operation: {e}")
            for ch, angle in angles_dict.items():
                if ch not in SERVO_CH_2_NAME:
                    continue
                try:
                    self.set_angle(ch, angle, mode)
                    results["success"].append({"ch": ch, "status": "ok"})
                except Exception as e2:
                    servo_name = SERVO_CH_2_NAME.get(ch, f"ch{ch}")
                    results["errors"].append(
                        {"ch": ch, "servo_name": servo_name, "message": str(e2)}
                    )

        return results

    def start_transition(self, angles_dict: dict[int, float], mode: str, duration: float) -> int:
        state = self._state.get_all()
        transitions: dict[int, dict[str, Any]] = {}
        for ch, target_angle in angles_dict.items():
            if ch not in SERVO_CH_2_NAME:
                continue
            servo_state = state.get(str(ch), {})
            current_angle = float(servo_state.get(mode, 0))
            target_angle_float = float(target_angle)
            transitions[ch] = {
                "current": current_angle,
                "target": target_angle_float,
                "servo_name": SERVO_CH_2_NAME[ch],
            }

        def execute_transition() -> None:
            steps = max(30, int(duration * 10))
            step_delay = duration / steps
            for step in range(steps + 1):
                progress = step / steps
                interpolated: dict[int, float] = {}
                for ch, trans in transitions.items():
                    current = trans["current"]
                    target = trans["target"]
                    interpolated[ch] = current + (target - current) * progress
                try:
                    self.set_angles_batch(interpolated, mode)
                except Exception as ex:
                    print(f"[SERVO] ERROR during transition: {ex}")
                if step < steps:
                    time.sleep(step_delay)

        thread = threading.Thread(target=execute_transition)
        thread.daemon = True
        thread.start()
        return len(transitions)
