# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""接続中の XInput パッドを、左右の踵速度に読む。

Isaac Sim の carb ゲームパッドを使う。Logicool F310 を XInput にすると
Windows 上では Xbox 360 Controller として見え、肩ボタンは次の対応になる。

- L / R: バンパー（LEFT_SHOULDER / RIGHT_SHOULDER）。押しているあいだ天井側。
- ZL / ZR: トリガー（LEFT_TRIGGER / RIGHT_TRIGGER）。引いているあいだ床側。

スティックは速度である。中立は 0 を返し、位置を戻す責務は持たない。
"""

from __future__ import annotations

import weakref

import carb
import numpy as np
import omni

# スティックの遊び。既存の歩行再生と同じくらい、中央付近を無視する。
_STICK_DEAD_ZONE = 0.15
# トリガーはアナログで、指を置いただけの値を高さ指令にしない。
_TRIGGER_DEAD_ZONE = 0.08


class HeelGamepad:
    """左右スティックと肩ボタン 4 つを、腰座標系の速度係数 [-1, 1] にする。"""

    def __init__(self) -> None:
        self.available = False
        self.name = ""
        self._sticks = {
            "left_x": _SplitAxis(),
            "left_y": _SplitAxis(),
            "right_x": _SplitAxis(),
            "right_y": _SplitAxis(),
        }
        self._buttons = {"l": 0.0, "zl": 0.0, "r": 0.0, "zr": 0.0}
        # ビューポートがパッドをカメラ操作に取らないようにする。
        carb.settings.get_settings().set_bool("/persistent/app/omniverse/gamepadCameraControl", False)
        self._input = carb.input.acquire_input_interface()
        window = omni.appwindow.get_default_app_window()
        self._gamepad = window.get_gamepad(0)
        if self._gamepad is None:
            raise RuntimeError("ゲームパッド 0 が見つからない")
        self._gamepad_sub = self._input.subscribe_to_gamepad_events(
            self._gamepad,
            lambda event, *args, obj=weakref.proxy(self): obj._on_event(event, *args),
        )
        self._bind_inputs()
        self.name = str(self._input.get_gamepad_name(self._gamepad))
        self.available = True
        print(f"gamepad: {self.name}", flush=True)

    def close(self) -> None:
        """購読を外す。シミュレーション終了時に呼ぶ。"""
        if getattr(self, "_gamepad_sub", None) is not None:
            self._input.unsubscribe_to_gamepad_events(self._gamepad, self._gamepad_sub)
            self._gamepad_sub = None

    def velocity_weights(self) -> tuple[np.ndarray, np.ndarray]:
        """左右の踵について、腰座標 ``(x, y, z)`` の速度係数を返す。

        スティックの奥が腰の +X（前）、スティックの右が腰の -Y（ロボットの右）。
        真上から見た XY で、倒した方向へ踵が進む。Z は L/R が正、ZL/ZR が負。
        """
        left = np.array(
            [
                self._shaped_stick(self._sticks["left_y"].value()),
                -self._shaped_stick(self._sticks["left_x"].value()),
                self._shoulder_rate(self._buttons["l"], self._buttons["zl"]),
            ],
            dtype=float,
        )
        right = np.array(
            [
                self._shaped_stick(self._sticks["right_y"].value()),
                -self._shaped_stick(self._sticks["right_x"].value()),
                self._shoulder_rate(self._buttons["r"], self._buttons["zr"]),
            ],
            dtype=float,
        )
        return left, right

    def snapshot(self) -> str:
        """コンソール表示用に、今の入力を短い文字列にする。"""
        left, right = self.velocity_weights()
        return (
            f"L stick=({left[0]:+.2f},{left[1]:+.2f}) z={left[2]:+.2f} "
            f"R stick=({right[0]:+.2f},{right[1]:+.2f}) z={right[2]:+.2f}"
        )

    def _on_event(self, event, *args, **kwargs) -> bool:
        """carb のゲームパッドイベントを、軸バッファへ写す。"""
        value = float(event.value)
        if event.input in self._stick_map:
            name, sign = self._stick_map[event.input]
            # 上下左右は別イベントで届く。反対側を消さないと、戻したあとも残り続ける。
            self._sticks[name].set(sign, value)
        elif event.input in self._button_map:
            self._buttons[self._button_map[event.input]] = value
        return True

    def _bind_inputs(self) -> None:
        """この Kit の GamepadInput 名で、スティックと肩ボタンを結ぶ。"""
        pad = carb.input.GamepadInput
        self._stick_map = {
            _require(pad, "LEFT_STICK_UP"): ("left_y", +1.0),
            _require(pad, "LEFT_STICK_DOWN"): ("left_y", -1.0),
            _require(pad, "LEFT_STICK_RIGHT"): ("left_x", +1.0),
            _require(pad, "LEFT_STICK_LEFT"): ("left_x", -1.0),
            _require(pad, "RIGHT_STICK_UP"): ("right_y", +1.0),
            _require(pad, "RIGHT_STICK_DOWN"): ("right_y", -1.0),
            _require(pad, "RIGHT_STICK_RIGHT"): ("right_x", +1.0),
            _require(pad, "RIGHT_STICK_LEFT"): ("right_x", -1.0),
        }
        self._button_map = {
            _require(pad, "LEFT_SHOULDER", "LEFT_BUMPER"): "l",
            _require(pad, "RIGHT_SHOULDER", "RIGHT_BUMPER"): "r",
            _require(pad, "LEFT_TRIGGER"): "zl",
            _require(pad, "RIGHT_TRIGGER"): "zr",
        }

    @staticmethod
    def _shaped_stick(value: float) -> float:
        """デッドゾーンの外側を、倒し切りが ±1 になるよう伸ばす。"""
        magnitude = abs(value)
        if magnitude < _STICK_DEAD_ZONE:
            return 0.0
        shaped = (magnitude - _STICK_DEAD_ZONE) / (1.0 - _STICK_DEAD_ZONE)
        return float(np.clip(shaped, 0.0, 1.0)) * (1.0 if value > 0.0 else -1.0)

    @staticmethod
    def _shoulder_rate(up_value: float, down_value: float) -> float:
        """バンパーを天井側、トリガーを床側にして、同時押しは相殺する。"""
        up = 0.0 if up_value < 0.5 else 1.0
        if down_value < _TRIGGER_DEAD_ZONE:
            down = 0.0
        else:
            down = (down_value - _TRIGGER_DEAD_ZONE) / (1.0 - _TRIGGER_DEAD_ZONE)
            down = float(np.clip(down, 0.0, 1.0))
        return up - down


class _SplitAxis:
    """スティックの正方向と負方向を別々に覚える。

    carb は「上」と「下」を別の軸として送る。片方だけ見ると、倒した値が 0 に見える。
    """

    def __init__(self) -> None:
        self.positive = 0.0
        self.negative = 0.0

    def set(self, sign: float, value: float) -> None:
        if sign >= 0.0:
            self.positive = value
        else:
            self.negative = value

    def value(self) -> float:
        if self.negative > self.positive:
            return -self.negative
        return self.positive


def _require(enum_type, *names: str):
    """GamepadInput のメンバーを、別名候補の順に探す。"""
    for name in names:
        if hasattr(enum_type, name):
            return getattr(enum_type, name)
    available = [name for name in dir(enum_type) if name.isupper()]
    raise AttributeError(f"{names[0]} が GamepadInput に無い。使える名前: {available}")
