#!/usr/bin/env python3
"""サブ PC のゲームパッドで、実機の左右の踵を腰基準に動かす。

Isaac の手動操作と同じ積算と逆運動学を、USB を握っている lab_debug.py へ渡す。
このプロセスは COM を開かない。Socket.IO（既定 http://127.0.0.1:8794）の m5/cmd で
関節角を送る。PWM は入れない。出力は、実機テレメトリで入れた関節だけが動く。

角度は URDF の可動域と、ファームが受ける 40〜230° の内側に収める。
画面の 100〜170° は机上の単軸実験用で、そのままだと膝が約 35° しか曲がらない。
足裏の合計がしきい値を超えているあいだは、その足を腰の床側へは進めない。
スタートを押しているあいだは、開始時の踵へゆっくり戻る。離すと止まる。

起動（lab_debug.py が先に COM を開いていること）::

    python link/host/heel_gamepad.py

パッドと逆運動学だけ確認するとき::

    python link/host/heel_gamepad.py --self-check

Ctrl+C で送出を止める。PWM が入った脚は、指令が 200 ms 途切れると脱力する。
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import threading
import time
from pathlib import Path

import numpy as np

# リポジトリ直下。host → link → リポジトリ。
_REPO = Path(__file__).resolve().parents[2]
_HUB = _REPO / "robot_description"
if str(_HUB) not in sys.path:
    sys.path.insert(0, str(_HUB))

from hub_link import deg_to_rad, rad_to_deg  # noqa: E402

# ファームが受ける指令。これより外はボードへ届かない。
_SERVO_MIN_DEG = 40.0
_SERVO_MAX_DEG = 230.0
# 足が床を押しているとみなす合計。立位の片足はこれより明らかに大きい。
_FLOOR_HOLD_KG = 0.5
# 積分は細かく、USB は lab_debug の 0.08 秒ゲートより遅く出す。
_INTEGRATE_S = 0.02
_SEND_S = 0.10
# シミュの手動操作と同じ最高速。少し倒したときは二乗で遅くなる。
_XY_SPEED_MPS = 0.30
_Z_SPEED_MPS = 0.20
_STICK_DEAD_ZONE = 0.15
_TRIGGER_DEAD_ZONE = 0.08
# L/R は ON/OFF だけなので、倒し切りと同じ 1.0 だと天井側が一気に動く。
# トリガーの中間くらいに合わせ、天井側の速さは上下最高速の約 1/3 にする。
_BUMPER_RATE = 1.0 / 3.0
# スタート押下中に、開始時の踵へ戻る速さ。倒し切りより遅く、一気に飛ばない。
_HOME_SPEED_MPS = 0.06
# これより近ければ、そのフレームで初期位置へ着ける。
_HOME_ARRIVE_M = 0.001

# XInput の肩ボタン。バンパーが天井側、トリガーが床側。スタートは初期位置へ戻す。
_BTN_LEFT_SHOULDER = 0x0100
_BTN_RIGHT_SHOULDER = 0x0200
_BTN_START = 0x0010

# 画面と同じ順。右 5 のあと左 5。
_RIGHT_NAMES = (
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee_pitch",
    "right_ankle_pitch",
    "right_ankle_roll",
)
_LEFT_NAMES = (
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee_pitch",
    "left_ankle_pitch",
    "left_ankle_roll",
)


def _load_ik():
    """逆運動学だけを読む。パッケージ初期化は Isaac を引き込むので使わない。"""
    path = (
        _REPO
        / "isaac-lab"
        / "source"
        / "yuuki_isaac_lab"
        / "yuuki_isaac_lab"
        / "manual_heel"
        / "leg_ik.py"
    )
    spec = importlib.util.spec_from_file_location("yuuki_heel_leg_ik", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"逆運動学がありません: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shaped_stick(value: float) -> float:
    """デッドゾーンの外側を二乗する。倒し切りだけが ±1。"""
    magnitude = abs(value)
    if magnitude < _STICK_DEAD_ZONE:
        return 0.0
    shaped = (magnitude - _STICK_DEAD_ZONE) / (1.0 - _STICK_DEAD_ZONE)
    shaped = float(np.clip(shaped, 0.0, 1.0)) ** 2
    return shaped * (1.0 if value > 0.0 else -1.0)


def _shoulder_rate(bumper: bool, trigger: float) -> float:
    """バンパーを天井側、トリガーを床側。トリガーは二乗する。

    バンパーは押しているあいだ一定なので、最高速ではなく _BUMPER_RATE で上げる。
    """
    up = _BUMPER_RATE if bumper else 0.0
    if trigger < _TRIGGER_DEAD_ZONE:
        down = 0.0
    else:
        down = (trigger - _TRIGGER_DEAD_ZONE) / (1.0 - _TRIGGER_DEAD_ZONE)
        down = float(np.clip(down, 0.0, 1.0)) ** 2
    return up - down


def _home_step(current: np.ndarray, home: np.ndarray, dt: float) -> np.ndarray:
    """初期位置へ、最高でも _HOME_SPEED_MPS で近づく変位を返す。

    残りが 1 フレーム分より短ければ、その差分だけ返す。行き過ぎない。
    """
    delta = np.asarray(home, dtype=float) - np.asarray(current, dtype=float)
    dist = float(np.linalg.norm(delta))
    if dist <= _HOME_ARRIVE_M:
        return delta
    step = _HOME_SPEED_MPS * max(float(dt), 0.0)
    if dist <= step:
        return delta
    return delta * (step / dist)


def _thumb(raw: int) -> float:
    """XInput の符号付き 16 bit を -1〜1 にする。"""
    if raw < 0:
        return float(raw) / 32768.0
    return float(raw) / 32767.0


class XInputPad:
    """接続中の XInput パッドを、左右の踵速度に読む。

    軸の意味は Isaac 側と同じ。左スティックが左踵、右が右踵。
    奥が腰の +X、右が腰の -Y。L/R が天井側、ZL/ZR が床側。
    """

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._state = None
        self._get_state = None
        self._index = 0
        self.name = ""
        for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                lib = ctypes.windll.LoadLibrary(dll)
            except OSError:
                continue

            class _Gamepad(ctypes.Structure):
                _fields_ = [
                    ("wButtons", wintypes.WORD),
                    ("bLeftTrigger", wintypes.BYTE),
                    ("bRightTrigger", wintypes.BYTE),
                    ("sThumbLX", wintypes.SHORT),
                    ("sThumbLY", wintypes.SHORT),
                    ("sThumbRX", wintypes.SHORT),
                    ("sThumbRY", wintypes.SHORT),
                ]

            class _State(ctypes.Structure):
                _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", _Gamepad)]

            self._state = _State()
            self._get_state = lib.XInputGetState
            self._get_state.argtypes = [wintypes.DWORD, ctypes.POINTER(_State)]
            self._get_state.restype = wintypes.DWORD
            self.name = dll
            break
        if self._get_state is None:
            raise RuntimeError("XInput が使えません。Windows のゲームパッド API がありません。")

    def connected(self) -> bool:
        """パッドが挿さっていれば True。抜くと False。"""
        code = int(self._get_state(self._index, self._ctypes.byref(self._state)))
        return code == 0

    def velocity_weights(self) -> tuple[np.ndarray, np.ndarray]:
        """左右の速度係数 [-1, 1]。未接続のフレームはゼロ。"""
        if not self.connected():
            zero = np.zeros(3)
            return zero, zero.copy()
        pad = self._state.Gamepad
        buttons = int(pad.wButtons)
        left = np.array(
            [
                _shaped_stick(_thumb(int(pad.sThumbLY))),
                -_shaped_stick(_thumb(int(pad.sThumbLX))),
                _shoulder_rate(bool(buttons & _BTN_LEFT_SHOULDER), int(pad.bLeftTrigger) / 255.0),
            ],
            dtype=float,
        )
        right = np.array(
            [
                _shaped_stick(_thumb(int(pad.sThumbRY))),
                -_shaped_stick(_thumb(int(pad.sThumbRX))),
                _shoulder_rate(bool(buttons & _BTN_RIGHT_SHOULDER), int(pad.bRightTrigger) / 255.0),
            ],
            dtype=float,
        )
        return left, right

    def start_held(self) -> bool:
        """スタートが押されていれば True。抜いているフレームは False。"""
        if not self.connected():
            return False
        return bool(int(self._state.Gamepad.wButtons) & _BTN_START)


def _command_limits(ik) -> np.ndarray:
    """URDF の可動域を、ファームの 40〜230° でさらに狭める。"""
    limits = np.array(ik.LEG_LIMITS, dtype=float)
    low = deg_to_rad(_SERVO_MIN_DEG)
    high = deg_to_rad(_SERVO_MAX_DEG)
    limits[:, 0] = np.maximum(limits[:, 0], low)
    limits[:, 1] = np.minimum(limits[:, 1], high)
    return limits


def _clip_command(q: np.ndarray) -> np.ndarray:
    """送り角を 40〜230° に収め、そのラジアンを返す。"""
    degrees = np.array([rad_to_deg(float(v)) for v in q], dtype=float)
    degrees = np.clip(degrees, _SERVO_MIN_DEG, _SERVO_MAX_DEG)
    return np.array([deg_to_rad(float(v)) for v in degrees], dtype=float)


def _block_into_floor(delta: np.ndarray, loaded: bool) -> np.ndarray:
    """接地中は、腰の床側（-Z）への変位だけ捨てる。"""
    out = np.array(delta, dtype=float)
    if loaded and out[2] < 0.0:
        out[2] = 0.0
    return out


def _foot_kg(sample: object) -> float | None:
    """足裏 1 枚の合計 kg。欠測は None。"""
    if not isinstance(sample, dict):
        return None
    if sample.get("ok") is False:
        return None
    try:
        return float(sample.get("force_kg") or 0.0)
    except (TypeError, ValueError):
        return None


class _Telemetry:
    """m5/frame を覚え、m5/cmd で関節角を出す。"""

    def __init__(self, url: str) -> None:
        import socketio

        self.url = url
        self._lock = threading.Lock()
        self.frame: dict | None = None
        self._sio = socketio.Client(reconnection=True, logger=False, engineio_logger=False)
        self._sio.on("m5/frame", self._on_frame)

    def _on_frame(self, payload) -> None:
        if isinstance(payload, dict):
            with self._lock:
                self.frame = payload

    def connect(self) -> None:
        """lab_debug の橋へつなぐ。COM は向こうが握ったまま。"""
        self._sio.connect(self.url, wait_timeout=5)

    def latest(self) -> dict | None:
        with self._lock:
            return None if self.frame is None else dict(self.frame)

    def send_joints(self, degrees: list[float]) -> None:
        """10 関節を 1 回ずつ出す。wide で机上の 100〜170° クランプを外す。"""
        for channel, deg in enumerate(degrees):
            self._sio.emit(
                "m5/cmd",
                {"op": "joint", "ch": channel, "deg": float(deg), "wide": True},
            )

    def close(self) -> None:
        if self._sio.connected:
            self._sio.disconnect()


def _seed_from_frame(frame: dict, ik) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """今の補正角を、左右の関節と踵目標にする。欠測の軸は 135°。"""
    corr = list(frame.get("corr") or [])
    ok = list(frame.get("as_ok") or [])
    radians = []
    for index in range(10):
        value = corr[index] if index < len(corr) else None
        good = True if index >= len(ok) else bool(ok[index])
        if value is None or not good:
            radians.append(0.0)
        else:
            radians.append(deg_to_rad(float(value)))
    right_q = _clip_command(np.array(radians[0:5], dtype=float))
    left_q = _clip_command(np.array(radians[5:10], dtype=float))
    left_heel, _ = ik.fk_heel(left_q, ik.Y_HIP_LEFT, ik.ROLL_SIGN_LEFT)
    right_heel, _ = ik.fk_heel(right_q, ik.Y_HIP_RIGHT, ik.ROLL_SIGN_RIGHT)
    return left_q, right_q, left_heel, right_heel


def _advance_leg(ik, limits, target, q, delta, y_hip, roll_sign, loaded: bool):
    """1 本の脚を 1 フレーム進める。接地中の床方向は動かさない。"""
    step = _block_into_floor(delta, loaded)
    new_target, new_q, _ = ik.step_heel_target(
        target, step, y_hip, q, limits=limits, roll_sign=roll_sign
    )
    clipped = _clip_command(new_q)
    if float(np.max(np.abs(clipped - new_q))) > 1.0e-4:
        # ファームの端で切った角度に、記憶している踵を合わせる。端の外へ溜めない。
        new_target, _ = ik.fk_heel(clipped, y_hip, roll_sign)
        new_q = clipped
    return new_target, new_q, bool(loaded and float(delta[2]) < 0.0 and float(step[2]) == 0.0)


def _run(url: str) -> None:
    """パッドを読み、踵を積算し、角度を橋へ出す。"""
    ik = _load_ik()
    limits = _command_limits(ik)
    pad = XInputPad()
    link = _Telemetry(url)
    print(f"パッド: {pad.name}", flush=True)
    print(f"橋へ接続します: {url}", flush=True)
    print("PWM は入れません。動かしたい関節は、実機テレメトリで PWM を入れてください。", flush=True)
    print("足が床を押しているあいだは、その足を床側へは動かしません。", flush=True)
    print("スタートを押しているあいだ、開始時の踵へゆっくり戻ります。離すと止まります。", flush=True)
    link.connect()
    print("補正角が届くまで待ちます。", flush=True)
    deadline = time.perf_counter() + 10.0
    frame = None
    while time.perf_counter() < deadline:
        frame = link.latest()
        corr = frame.get("corr") if isinstance(frame, dict) else None
        if isinstance(corr, list) and len(corr) >= 10:
            break
        time.sleep(0.05)
    else:
        link.close()
        raise RuntimeError("10 秒待っても補正角が 10 軸届きません。CoreS3 の USB と lab_debug.py を確認してください。")

    left_q, right_q, left_heel, right_heel = _seed_from_frame(frame, ik)
    # このあと踵は積算で動く。初期位置は開始時のコピーを残す。
    left_home = np.array(left_heel, dtype=float)
    right_home = np.array(right_heel, dtype=float)
    print(
        f"開始  L heel=({left_heel[0]:+.3f},{left_heel[1]:+.3f},{left_heel[2]:+.3f}) "
        f"R heel=({right_heel[0]:+.3f},{right_heel[1]:+.3f},{right_heel[2]:+.3f})",
        flush=True,
    )
    speed = np.array([_XY_SPEED_MPS, _XY_SPEED_MPS, _Z_SPEED_MPS], dtype=float)
    next_send = 0.0
    next_status = 0.0
    clock = time.perf_counter()
    try:
        while True:
            now = time.perf_counter()
            dt = min(now - clock, 0.05)
            clock = now
            latest = link.latest() or {}
            left_load = _foot_kg(latest.get("foot_left"))
            right_load = _foot_kg(latest.get("foot"))
            # スタート中はスティックを使わず、開始時の踵へ一定の速さで戻す。
            homing = pad.start_held()
            if homing:
                left_delta = _home_step(left_heel, left_home, dt)
                right_delta = _home_step(right_heel, right_home, dt)
            else:
                left_w, right_w = pad.velocity_weights()
                left_delta = left_w * speed * dt
                right_delta = right_w * speed * dt
            left_heel, left_q, left_held = _advance_leg(
                ik,
                limits,
                left_heel,
                left_q,
                left_delta,
                ik.Y_HIP_LEFT,
                ik.ROLL_SIGN_LEFT,
                left_load is not None and left_load >= _FLOOR_HOLD_KG,
            )
            right_heel, right_q, right_held = _advance_leg(
                ik,
                limits,
                right_heel,
                right_q,
                right_delta,
                ik.Y_HIP_RIGHT,
                ik.ROLL_SIGN_RIGHT,
                right_load is not None and right_load >= _FLOOR_HOLD_KG,
            )
            if now >= next_send:
                next_send = now + _SEND_S
                degrees = [rad_to_deg(float(v)) for v in (*right_q, *left_q)]
                link.send_joints(degrees)
            if now >= next_status:
                next_status = now + 2.0
                hold = []
                if left_held:
                    hold.append("左は接地中なので床側を止めました")
                if right_held:
                    hold.append("右は接地中なので床側を止めました")
                if homing:
                    hold.append("初期位置へ戻しています")
                extra = (" " + " ".join(hold)) if hold else ""
                print(
                    f"L=({left_heel[0]:+.3f},{left_heel[1]:+.3f},{left_heel[2]:+.3f}) "
                    f"R=({right_heel[0]:+.3f},{right_heel[1]:+.3f},{right_heel[2]:+.3f}){extra}",
                    flush=True,
                )
            remain = _INTEGRATE_S - (time.perf_counter() - now)
            if remain > 0.0:
                time.sleep(remain)
    finally:
        link.close()
        print("送出を止めました。PWM 中の脚は、約 200 ms 後に脱力します。", flush=True)


def _self_check() -> None:
    """パッドと USB が無くても、床止めと可動域の端を確認する。"""
    ik = _load_ik()
    limits = _command_limits(ik)
    # 膝の正方向は、230° でファームの端になる。URDF の 120° より手前。
    knee_hi = float(limits[2, 1])
    if knee_hi > deg_to_rad(_SERVO_MAX_DEG) + 1.0e-9:
        raise AssertionError(f"knee limit exceeds firmware: {knee_hi}")
    if abs(_shaped_stick(1.0) - 1.0) > 1.0e-9:
        raise AssertionError("full stick is not full speed")
    if _shaped_stick(0.0) != 0.0:
        raise AssertionError("neutral stick is not held")
    half = _shaped_stick(0.15 + 0.5 * (1.0 - 0.15))
    if not 0.20 < half < 0.30:
        raise AssertionError(f"half stick should be near 1/4 speed, got {half}")
    # バンパーはデジタルなので、押しているあいだの天井側は最高速の 1/3。
    if abs(_shoulder_rate(True, 0.0) - (1.0 / 3.0)) > 1.0e-9:
        raise AssertionError("bumper lift is not one third of full vertical speed")
    if abs(_shoulder_rate(False, 1.0) + 1.0) > 1.0e-9:
        raise AssertionError("full trigger is not full downward speed")
    # 0.3 m 先を 0.06 m/s で 0.02 秒進めると、1.2 mm だけ初期位置へ寄る。
    far = _home_step(np.array([0.3, 0.0, 0.0]), np.zeros(3), 0.02)
    if abs(float(np.linalg.norm(far)) - 0.0012) > 1.0e-9 or far[0] >= 0.0:
        raise AssertionError(f"home step is not a slow approach: {far}")
    near = _home_step(np.array([0.0004, 0.0, 0.0]), np.zeros(3), 0.02)
    if abs(float(near[0]) + 0.0004) > 1.0e-12:
        raise AssertionError(f"home step overshot a short gap: {near}")
    blocked = _block_into_floor(np.array([0.01, 0.0, -0.02]), True)
    if blocked[2] != 0.0 or blocked[0] != 0.01:
        raise AssertionError(f"floor block changed the wrong axis: {blocked}")
    free = _block_into_floor(np.array([0.0, 0.0, -0.02]), False)
    if free[2] == 0.0:
        raise AssertionError("unloaded foot was not allowed downward")
    straight = ik.stand_heel(ik.Y_HIP_LEFT, ik.ROLL_SIGN_LEFT)
    moved, q, held = _advance_leg(
        ik,
        limits,
        straight,
        np.zeros(5),
        np.array([0.0, 0.0, -0.03]),
        ik.Y_HIP_LEFT,
        ik.ROLL_SIGN_LEFT,
        True,
    )
    if held is not True or float(np.max(np.abs(moved - straight))) > 1.0e-9:
        raise AssertionError("loaded leg stored a downward step")
    lifted, q_up, held_up = _advance_leg(
        ik,
        limits,
        straight,
        np.zeros(5),
        np.array([0.0, 0.0, 0.04]),
        ik.Y_HIP_LEFT,
        ik.ROLL_SIGN_LEFT,
        True,
    )
    if held_up or lifted[2] <= straight[2]:
        raise AssertionError("loaded leg refused to lift")
    degrees = [rad_to_deg(float(v)) for v in q_up]
    if any(d < _SERVO_MIN_DEG - 1.0e-6 or d > _SERVO_MAX_DEG + 1.0e-6 for d in degrees):
        raise AssertionError(f"command left the firmware range: {degrees}")
    print("heel_gamepad self-check: OK")


def main() -> None:
    parser = argparse.ArgumentParser(description="実機の踵をゲームパッドで動かす。")
    parser.add_argument("--url", default="http://127.0.0.1:8794", help="lab_debug.py の Socket.IO。")
    parser.add_argument("--self-check", action="store_true", help="USB もパッドも使わず、床止めと可動域だけ確認する。")
    args = parser.parse_args()
    if args.self_check:
        _self_check()
        return
    try:
        _run(args.url)
    except KeyboardInterrupt:
        print("中断しました。", flush=True)


if __name__ == "__main__":
    main()
