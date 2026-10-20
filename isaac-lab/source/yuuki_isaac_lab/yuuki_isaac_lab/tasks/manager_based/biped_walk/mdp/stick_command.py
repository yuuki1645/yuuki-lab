"""再生中だけ、左スティックを前後の速度指令にする。

学習の SlowWalkVelocityCommand は変えない。このクラスは再生用の設定からのみ使う。
奥へ倒すと正の前進、倒し切りで 0.2 m/s。中央と手前は、方策へは 0。
手前をマイナスにしないのは、この方策が後ろ歩きを学習していないため。
左右は画面の図にだけ残し、方策とヨーには渡さない。
"""

from __future__ import annotations

from isaaclab.devices.gamepad.se2_gamepad import Se2Gamepad
from isaaclab.devices.gamepad.se2_gamepad_cfg import Se2GamepadCfg

from .forward_command import SlowWalkVelocityCommand
from .hub_play_link import HubPlayLink
from .phase import FORWARD_SPEED_MPS

# スティックの遊び。これ未満は中央とみなし、勝手に歩き出さない。
_STICK_DEAD_ZONE = 0.15


class StickWalkCommand(SlowWalkVelocityCommand):
    """左スティックの奥を、0〜0.2 m/s の前進指令にする。"""

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self._gamepad = None
        self._last_print_vx = -1.0
        # 画面のスティック図へ、指の位置と方策への速度を渡す。橋が無くても再生は続ける。
        self._hub = HubPlayLink()
        self._stick = _idle_stick()
        # ウィンドウのゲームパッド 0 を読む。無いときは 0 m/s のまま再生する。
        try:
            pad_cfg = Se2GamepadCfg(
                # 倒し切りが、この歩行の最大速度 0.2 m/s になる。
                v_x_sensitivity=FORWARD_SPEED_MPS,
                # 左右は方策へ渡さない。図で指の位置を残すため、感度だけ 1 にして読む。
                v_y_sensitivity=1.0,
                omega_z_sensitivity=0.0,
                dead_zone=_STICK_DEAD_ZONE,
                sim_device=self.device,
            )
            self._gamepad = Se2Gamepad(pad_cfg)
            name = self._gamepad._input.get_gamepad_name(self._gamepad._gamepad)
            print(f"stick gamepad: {name}", flush=True)
        except Exception as exc:
            print(f"stick gamepad unavailable: {exc}", flush=True)

    def _resample_command(self, env_ids):
        # 出現時の自動抽選も、すぐスティックの値で上書きする。
        super()._resample_command(env_ids)
        self._apply_stick()

    def _update_command(self):
        # 親は約2割を 0 にする。再生では毎ステップ、スティックを優先する。
        super()._update_command()
        self._apply_stick()

    def _apply_stick(self):
        """左スティックの前後だけを指令にする。手前と左右は 0。"""
        if self._gamepad is None:
            self.vel_command_b[:] = 0.0
            self._stick = _idle_stick()
            self._hub.publish(self._env, self._stick)
            return
        # advance は (前後, 左右, ヨー)。奥が正、手前が負。左右は ±1。
        raw = self._gamepad.advance().to(device=self.device)
        signed = float(raw[0])
        # 方策は後ろ歩きを知らないので、手前は 0 にする。
        forward = raw[0].clamp(min=0.0, max=FORWARD_SPEED_MPS)
        self.vel_command_b[:, 0] = forward
        self.vel_command_b[:, 1] = 0.0
        self.vel_command_b[:, 2] = 0.0
        vx = float(forward)
        # 図の y は奥が +1。感度 0.2 で割ると、倒し切りが ±1 に戻る。
        scale = FORWARD_SPEED_MPS if FORWARD_SPEED_MPS > 1.0e-6 else 1.0
        self._stick = {
            "x": float(raw[1]),
            "y": signed / scale,
            "vx": vx,
            "max_vx": FORWARD_SPEED_MPS,
            "dead_zone": _STICK_DEAD_ZONE,
        }
        # 30 Hz では流しすぎるので、速度が一段変わったときだけ出す。
        if abs(vx - self._last_print_vx) >= 0.01:
            self._last_print_vx = vx
            print(f"stick_vx {vx:.2f}", flush=True)
        self._hub.publish(self._env, self._stick)


def _idle_stick() -> dict:
    """パッドが無いときの図。中央で、方策への速度は 0。"""
    return {
        "x": 0.0,
        "y": 0.0,
        "vx": 0.0,
        "max_vx": FORWARD_SPEED_MPS,
        "dead_zone": _STICK_DEAD_ZONE,
    }
