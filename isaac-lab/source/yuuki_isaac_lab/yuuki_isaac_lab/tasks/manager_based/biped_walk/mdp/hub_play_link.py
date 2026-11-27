"""歩行再生の1体を、robotics-hub の実機テレメトリ（M5）へ送る。

橋は ``robot_description/isaac_hub_bridge.py``。ここは Isaac Lab の再生プロセスから
127.0.0.1:8796 へ JSON を1行ずつ書くだけ。flask は入れない。
橋が無いあいだは約1秒に1回だけつなぎ直し、シミュレーションは止めない。

画面の関節順は右脚5、左脚5（``hub_link.JOINTS`` と同じ）。
方策の関節順（左右交互）のまま送ると、欄がずれる。

角度はラジアンのまま送る。直立は 0 rad。画面の 135° と 0° への変換は橋が行う。
プラスの向きは URDF のプラスのまま（docs/joint_angles.md）。ここでは軸を反転しない。

送る「指令」は方策が出した目標角。画面のバーが返してくる目標は読まない。
歩行中にバーで関節を上書きしないため。

``policy`` は、方策が見ている残りの量。重力、角速度、位相、速度指令、直前の生出力。
関節角と足裏は、今までどおり rad と foot で送る。
"""

from __future__ import annotations

import json
import socket
import time
from typing import TYPE_CHECKING

import isaaclab.envs.mdp as isaac_mdp
from isaaclab.managers import SceneEntityCfg

from .feet import DF9_MAX_KG, foot_corner_kg
from .observations import command_forward_and_yaw
from .phase import PERIOD_S, phase_sincos

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv

# hub_link.py の HUB 側 TCP。実機の Socket.IO :8794 ではない。
_ISAAC_TCP_HOST = "127.0.0.1"
_ISAAC_TCP_PORT = 8796
# Hub の脚タブは 20 Hz で足りる。制御は 30 Hz なので、毎ステップは送らない。
_SEND_PERIOD_S = 0.05
# 橋が落ちているときに、接続待ちで再生を止めない。
_RETRY_PERIOD_S = 1.0

# hub_link.JOINTS と同じ順。右が先。名前で並べ替える。
_HUB_JOINTS = (
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee_pitch",
    "right_ankle_pitch",
    "right_ankle_roll",
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee_pitch",
    "left_ankle_pitch",
    "left_ankle_roll",
)

# foot_corner_kg の1足ぶん。左4のあと右4。画面は右が foot、左が foot_left。
_CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")


class HubPlayLink:
    """1体の再生を橋へ送る。学習の 4096 環境では使わない。"""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._next_try = 0.0
        self._next_send = 0.0
        self._seq = 0
        self._said_down = False
        self._said_up = False
        self._sensor_cfg: SceneEntityCfg | None = None
        self._sole_cfg: SceneEntityCfg | None = None

    def publish(self, env: ManagerBasedRLEnv, stick: dict) -> None:
        """今の関節・足裏・スティックと、方策の観測を1行送る。失敗しても再生は続ける。"""
        try:
            if env.num_envs != 1:
                return
            now = time.time()
            self._ensure(now)
            if self._sock is None:
                return
            self._drain()
            if now < self._next_send:
                return
            self._next_send = now + _SEND_PERIOD_S
            payload = self._payload(env, stick)
            data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            self._sock.sendall(data)
        except Exception as exc:
            # 橋が途中で切れても、歩行の再生自体は落とさない。
            self._close()
            if not self._said_down:
                self._said_down = True
                print(f"hub telemetry send failed: {exc}", flush=True)

    def _ensure(self, now: float) -> None:
        """未接続なら、間隔を空けて 8796 へつなぐ。"""
        if self._sock is not None:
            return
        if now < self._next_try:
            return
        self._next_try = now + _RETRY_PERIOD_S
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.05)
        try:
            sock.connect((_ISAAC_TCP_HOST, _ISAAC_TCP_PORT))
        except OSError:
            sock.close()
            if not self._said_down:
                self._said_down = True
                print(
                    "hub telemetry: isaac_hub_bridge.py (127.0.0.1:8796) が無いので、画面には出しません。",
                    flush=True,
                )
            return
        # 受信は捨てるだけなので、データが無いときに待たない。
        sock.setblocking(False)
        self._sock = sock
        self._said_down = False
        if not self._said_up:
            self._said_up = True
            print("hub telemetry: connected 127.0.0.1:8796", flush=True)

    def _drain(self) -> None:
        """橋が返してくる目標角を捨てる。歩行再生では関節に書かない。"""
        sock = self._sock
        if sock is None:
            return
        try:
            while True:
                chunk = sock.recv(65536)
                # 空は切断。橋からの目標角そのものは、歩行中は使わない。
                if not chunk:
                    self._close()
                    return
        except (BlockingIOError, TimeoutError):
            return
        except OSError:
            self._close()

    def _close(self) -> None:
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _payload(self, env: ManagerBasedRLEnv, stick: dict) -> dict:
        """橋が待つ joints 行。rad と cmd_rad は画面の関節順で、単位はラジアン。"""
        self._seq += 1
        measured, commanded = _joint_radians(env)
        elapsed = 0.0
        length = getattr(env, "episode_length_buf", None)
        if length is not None:
            elapsed = float(length[0]) * float(env.step_dt)
        payload = {
            "op": "joints",
            "rad": measured,
            "cmd_rad": commanded,
            "sim_time": elapsed,
            "foot": _foot_sample(self._corners(env, side="right"), self._seq),
            "foot_left": _foot_sample(self._corners(env, side="left"), self._seq),
            "stick": stick,
        }
        # 観測が読めないステップではキー自体を付けない。画面は前回の値を残さない。
        policy = _policy_obs(env)
        if policy is not None:
            payload["policy"] = policy
        return payload

    def _corners(self, env: ManagerBasedRLEnv, side: str) -> list[float] | None:
        """方策と同じ四隅 kg。センサがまだ無いステップは None。"""
        try:
            sensor_cfg, sole_cfg = self._sole_entities(env)
            corners = foot_corner_kg(env, sensor_cfg, sole_cfg)[0]
        except Exception:
            return None
        # 列は左4、右4。各足はつま先左・つま先右・かかと左・かかと右。
        block = corners[4:8] if side == "right" else corners[0:4]
        return [float(v) for v in block.detach().cpu().tolist()]

    def _sole_entities(self, env: ManagerBasedRLEnv) -> tuple[SceneEntityCfg, SceneEntityCfg]:
        """足リンクの番号は最初の1回だけ解決する。"""
        if self._sensor_cfg is None or self._sole_cfg is None:
            sensor_cfg = SceneEntityCfg(
                "contact_forces",
                body_names=["L_FOOT", "R_FOOT"],
                preserve_order=True,
            )
            sole_cfg = SceneEntityCfg(
                "robot",
                body_names=["L_FOOT", "R_FOOT"],
                preserve_order=True,
            )
            sensor_cfg.resolve(env.scene)
            sole_cfg.resolve(env.scene)
            self._sensor_cfg = sensor_cfg
            self._sole_cfg = sole_cfg
        return self._sensor_cfg, self._sole_cfg


def _joint_radians(env: ManagerBasedRLEnv) -> tuple[list[float], list[float | None]]:
    """実測角と、方策の目標角。どちらも画面の順（右5、左5）。"""
    robot = env.scene["robot"]
    measured_row = robot.data.joint_pos.torch[0].detach().cpu().tolist()
    measured_by_name = {name: float(measured_row[i]) for i, name in enumerate(robot.joint_names)}
    measured = [measured_by_name.get(name, 0.0) for name in _HUB_JOINTS]

    commanded: list[float | None] = [None] * len(_HUB_JOINTS)
    try:
        term = env.action_manager.get_term("joint_pos")
        target_row = term.processed_actions[0].detach().cpu().tolist()
        target_by_name = {name: float(target_row[i]) for i, name in enumerate(term._joint_names)}
        commanded = [target_by_name.get(name) for name in _HUB_JOINTS]
    except Exception:
        # 行動がまだ無い最初のステップでは、指令欄だけ空にする。
        pass
    return measured, commanded


def _policy_obs(env: ManagerBasedRLEnv) -> dict | None:
    """方策の policy 観測のうち、関節角と足裏以外。

    重力・角速度・位相・指令は、学習と同じ関数の戻り値をそのまま載せる。
    last_action はネットワークの生出力で、目標角ではない。画面の関節順に並べ替える。
    読めない最初のステップは None。その行には policy を付けない。
    """
    try:
        gravity = _row3(isaac_mdp.projected_gravity(env))
        ang_vel = _row3(isaac_mdp.base_ang_vel(env))
        phase = phase_sincos(env)[0].detach().cpu().tolist()
        command = command_forward_and_yaw(env, "base_velocity")[0].detach().cpu().tolist()
        term = env.action_manager.get_term("joint_pos")
        raw_row = term.raw_actions[0].detach().cpu().tolist()
        raw_by_name = {name: float(raw_row[i]) for i, name in enumerate(term._joint_names)}
        last_action = [raw_by_name.get(name) for name in _HUB_JOINTS]
    except Exception:
        return None
    return {
        # 体座標。前が +x、左が +y、上が +z。直立の z は約 -1。
        "gravity": gravity,
        "ang_vel": ang_vel,
        "phase_sin": float(phase[0]),
        "phase_cos": float(phase[1]),
        "period_s": float(PERIOD_S),
        "vx": float(command[0]),
        "yaw": float(command[1]),
        # 出力 1 が、直立からこのラジアンだけ目標を動かす。画面の度には橋が直す。
        "action_scale": _action_scale(term),
        "last_action": last_action,
    }


def _row3(tensor) -> list[float]:
    """先頭の環境の 3 成分。方策が見ている並びのまま。"""
    row = tensor[0].detach().cpu().tolist()
    return [float(row[0]), float(row[1]), float(row[2])]


def _action_scale(term) -> float:
    """関節目標の倍率。学習の JointPositionActionCfg.scale と同じ 0.25。"""
    scale = getattr(term, "_scale", 0.25)
    if hasattr(scale, "detach"):
        flat = scale.detach().flatten()
        if int(flat.numel()) == 0:
            return 0.25
        return float(flat[0].cpu())
    return float(scale)


def _foot_sample(kg4: list[float] | None, seq: int) -> dict:
    """Hub の足裏1枚。kg は方策が見ている値（2 kg 頭打ち、0.02 kg 未満は 0）。"""
    ok = kg4 is not None and len(kg4) == 4
    values = kg4 if ok else [0.0, 0.0, 0.0, 0.0]
    corners: dict[str, dict] = {}
    total = 0.0
    for key, kg in zip(_CORNER_KEYS, values):
        total += kg
        corners[key] = {
            "force_kg": kg,
            "force_pct": 100.0 * kg / DF9_MAX_KG,
        }
    return {
        "ok": ok,
        "seq": int(seq),
        "mask": 0b1111 if ok else 0,
        "force_kg": total,
        "corners": corners,
    }
