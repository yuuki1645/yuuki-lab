#!/usr/bin/env python3
"""Isaac Sim の窓を開き、Hub の指令角で脚を 1 体動かす。

C:\\isaacsim にはパッケージを入れない。このファイルはリポジトリに置き、
Isaac 同梱の Python で起動する。

    C:\\isaacsim\\python.bat Z:\\Projects\\yuuki-lab\\robot_description\\isaac_hub_play.py

先に isaac_hub_bridge.py を起動しておく。橋が無いあいだは再接続しながら、
ロボットは直立のまま物理を進める。

カゴは地面に固定する（fix_base）。バーで関節を動かすための再生であり、
歩行学習の浮動ベースではない。
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

# SimulationApp より前に読んでよいのは、標準ライブラリだけの hub_link。
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from hub_link import ISAAC_TCP_HOST, ISAAC_TCP_PORT, JOINT_COUNT, joint_names
from sole_pressure import PLATE_HALF_X_M, PLATE_HALF_Y_M, sample_from_points

# 直立時、原点から足裏まで 0.622 m。足裏下面を床（z=0）に合わせ、接触が出るようにする。
SPAWN_Z_M = 0.622
# 位置制御。実機の PD そのものではなく、バー操作が追従するための仮のゲイン。
JOINT_STIFFNESS = 80.0
JOINT_DAMPING = 2.0

URDF_PATH = _HERE / "yuuki_biped.urdf"
USD_CACHE = _HERE / ".usd_cache"


def main() -> None:
    from isaacsim import SimulationApp

    # 先に isaac-sim.bat で GUI を開いたままにしない。このプロセスが窓を持つ。
    simulation_app = SimulationApp({"headless": False, "renderer": "RaytracedLighting"})
    try:
        _run(simulation_app)
    finally:
        simulation_app.close()


def _run(simulation_app) -> None:
    import omni.kit.app
    import omni.timeline
    import omni.usd
    from pxr import Gf, UsdGeom, UsdLux, UsdPhysics

    ext = omni.kit.app.get_app().get_extension_manager()
    ext.set_extension_enabled_immediate("omni.scene.optimizer.core", True)
    ext.set_extension_enabled_immediate("isaacsim.robot.schema", True)
    ext.set_extension_enabled_immediate("isaacsim.asset.importer.urdf", True)
    ext.set_extension_enabled_immediate("isaacsim.sensors.experimental.physics", True)

    from isaacsim.asset.importer.urdf.impl import URDFImporter, URDFImporterConfig
    from isaacsim.core.experimental.prims import Articulation

    usd_path = _import_urdf(URDFImporter, URDFImporterConfig)
    _build_stage(usd_path, UsdGeom, UsdLux, UsdPhysics, Gf)
    for _ in range(10):
        simulation_app.update()
    # 再生前に切る。目印の球と、板より下にはみ出す足首サーボが床に当たると、
    # アルミ板の接触にならない。圧力は足板の接触だけを四隅へ分配する。
    _disable_non_plate_collisions(UsdPhysics)

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    for _ in range(5):
        simulation_app.update()

    root = _find_articulation_root()
    print(f"[isaac_hub_play] articulation {root}")
    robot = Articulation(root)
    # 物理テンソルが関節名を返すまで待つ。変換直後は空のことがある。
    names: list[str] = []
    for _ in range(60):
        simulation_app.update()
        try:
            names = [str(n) for n in robot.dof_names]
        except Exception:
            names = []
        if names:
            break
    print(f"[isaac_hub_play] dofs {names}")
    if not names:
        raise SystemExit("関節 DOF が初期化されませんでした")
    dof_index = _dof_index(names)

    soles = _create_sole_sensors()

    link = _TcpClient()
    # PWM OFF のあいだは、その関節の現在角を目標にしてその場に留める。
    hold_rad = [0.0] * len(names)
    sole_seq = 0

    while simulation_app.is_running():
        link.poll()
        for msg in link.take_messages():
            if msg.get("op") != "targets":
                continue
            incoming = msg.get("rad")
            if not isinstance(incoming, list):
                continue
            measured = _read_positions(robot, len(names))
            for ch, dof_i in dof_index.items():
                if ch >= len(incoming) or incoming[ch] is None:
                    hold_rad[dof_i] = measured[dof_i]
                else:
                    hold_rad[dof_i] = float(incoming[ch])
        _apply_targets(robot, hold_rad)
        simulation_app.update()
        if link.connected and link.due():
            measured = _read_positions(robot, len(names))
            rad = []
            for ch in range(JOINT_COUNT):
                dof_i = dof_index.get(ch)
                rad.append(0.0 if dof_i is None else measured[dof_i])
            sole_seq += 1
            link.send(
                {
                    "op": "joints",
                    "rad": rad,
                    "sim_time": time.time(),
                    # 実機の frame.foot は右足。左は foot_left。実機では左が欠ける。
                    "foot": _read_sole(soles.get("right"), sole_seq),
                    "foot_left": _read_sole(soles.get("left"), sole_seq),
                }
            )


def _import_urdf(importer_cls, config_cls) -> str:
    """URDF が USD キャッシュより新しければ変換し、USD のパスを返す。"""
    if not URDF_PATH.is_file():
        raise SystemExit(f"URDF がありません: {URDF_PATH}")
    USD_CACHE.mkdir(parents=True, exist_ok=True)
    # 変換結果はキャッシュ直下とは限らない（yuuki_biped/yuuki_biped.usd など）。
    cached = sorted(USD_CACHE.rglob("yuuki_biped.usd"))
    urdf_mtime = URDF_PATH.stat().st_mtime
    if cached and cached[0].stat().st_mtime >= urdf_mtime:
        print(f"[isaac_hub_play] USD キャッシュを使います: {cached[0]}")
        return str(cached[0])

    config = config_cls()
    config.urdf_path = str(URDF_PATH)
    config.usd_path = str(USD_CACHE)
    # バーで関節を見るあいだ、カゴを世界に固定して転倒させない。
    config.fix_base = True
    config.merge_fixed_joints = False
    config.joint_target_type = "position"
    config.joint_drive_type = "force"
    config.override_joint_stiffness = JOINT_STIFFNESS
    config.override_joint_damping = JOINT_DAMPING
    config.collision_from_visuals = True
    print(f"[isaac_hub_play] URDF を変換します: {URDF_PATH}")
    output = importer_cls(config).import_urdf()
    if not output:
        raise SystemExit("URDF の変換に失敗しました")
    print(f"[isaac_hub_play] USD {output}")
    return str(output)


def _build_stage(usd_path: str, UsdGeom, UsdLux, UsdPhysics, Gf) -> None:
    """床とライトを置き、ロボットを足が床の近くに来る高さで参照する。"""
    import omni.usd

    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    scene = UsdPhysics.Scene.Define(stage, "/World/physicsScene")
    scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
    scene.CreateGravityMagnitudeAttr().Set(9.81)

    ground = UsdGeom.Cube.Define(stage, "/World/ground")
    ground.CreateSizeAttr(1.0)
    xf = UsdGeom.Xformable(ground.GetPrim())
    xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -0.05))
    xf.AddScaleOp().Set(Gf.Vec3d(6.0, 6.0, 0.1))
    UsdPhysics.CollisionAPI.Apply(ground.GetPrim())

    sun = UsdLux.DistantLight.Define(stage, "/World/sun")
    sun.CreateIntensityAttr(4000.0)
    sun.CreateAngleAttr(1.0)

    robot = stage.DefinePrim("/World/yuuki_biped", "Xform")
    robot.GetReferences().AddReference(usd_path)
    UsdGeom.Xformable(robot).AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, SPAWN_Z_M))


def _find_articulation_root() -> str:
    """参照した USD の中で、物理のルートになっている prim を探す。"""
    import omni.usd
    from pxr import UsdPhysics

    stage = omni.usd.get_context().get_stage()
    found: list[str] = []
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            found.append(str(prim.GetPath()))
    if not found:
        raise SystemExit("ArticulationRoot が見つかりません。URDF 変換を確認してください。")
    # 固定ベースだと world 側とロボット側の両方が付くことがある。パスが長い方をロボット本体とみなす。
    found.sort(key=len, reverse=True)
    return found[0]


def _dof_index(names: list[str]) -> dict[int, int]:
    """チャンネル番号 → DOF 番号。URDF の関節名で対応づける。"""
    by_name = {name: i for i, name in enumerate(names)}
    mapping: dict[int, int] = {}
    for ch, name in enumerate(joint_names()):
        if name not in by_name:
            print(f"[isaac_hub_play] 関節が USD にありません: {name}")
            continue
        mapping[ch] = by_name[name]
    if len(mapping) != JOINT_COUNT:
        print(f"[isaac_hub_play] 対応できた関節は {len(mapping)} / {JOINT_COUNT}")
    return mapping


def _read_positions(robot, n_dof: int) -> list[float]:
    data = robot.get_dof_positions()
    array = data.numpy()
    row = array[0] if getattr(array, "ndim", 1) == 2 else array
    return [float(row[i]) for i in range(n_dof)]


def _apply_targets(robot, hold_rad: list[float]) -> None:
    import numpy as np

    robot.set_dof_position_targets(np.asarray(hold_rad, dtype=np.float32)[None, :])


# 足板の衝突ではない。球は下面中心の目印、サーボ箱は仮定の足首高さでは板より下へ出る。
_NON_PLATE_COLLISIONS = (
    "left_sole_sole_marker_0",
    "right_sole_sole_marker_0",
    "left_foot_servo_0",
    "right_foot_servo_0",
)


def _prims_by_name() -> dict[str, str]:
    """ステージ上の prim 名 → パス。同名が複数あるときは先に見つけた方を残す。"""
    import omni.usd

    found: dict[str, str] = {}
    stage = omni.usd.get_context().get_stage()
    for prim in stage.Traverse():
        found.setdefault(prim.GetName(), str(prim.GetPath()))
    return found


def _disable_non_plate_collisions(UsdPhysics) -> None:
    """足裏圧力に使う衝突をアルミ板だけにする。"""
    import omni.usd

    stage = omni.usd.get_context().get_stage()
    by_name = _prims_by_name()
    for name in _NON_PLATE_COLLISIONS:
        path = by_name.get(name)
        if path is None:
            print(f"[isaac_hub_play] 衝突を切る対象がありません: {name}")
            continue
        prim = stage.GetPrimAtPath(path)
        collision = UsdPhysics.CollisionAPI.Apply(prim)
        collision.CreateCollisionEnabledAttr(False)
        print(f"[isaac_hub_play] 足板以外の衝突を切りました: {path}")


def _create_sole_sensors() -> dict[str, dict | None]:
    """左右の足リンクに Contact Sensor を付ける。失敗した足は None。"""
    from isaacsim.sensors.experimental.physics import Contact, ContactSensor

    by_name = _prims_by_name()
    sensors: dict[str, dict | None] = {}
    for side, foot_name, sole_name in (
        ("right", "right_foot", "right_sole"),
        ("left", "left_foot", "left_sole"),
    ):
        foot_path = by_name.get(foot_name)
        sole_path = by_name.get(sole_name)
        if foot_path is None or sole_path is None:
            print(f"[isaac_hub_play] 足の prim がありません: {foot_name} / {sole_name}")
            sensors[side] = None
            continue
        try:
            # 半径 -1 は足リンク全体。板の範囲への絞り込みは読むときに行う。
            sensor = ContactSensor(
                Contact.create(
                    foot_path + "/sole_contact_sensor",
                    min_threshold=0.0,
                    max_threshold=100000.0,
                    radius=-1.0,
                )
            )
        except Exception as exc:
            print(f"[isaac_hub_play] {side} 足の Contact Sensor を作れませんでした: {exc}")
            sensors[side] = None
            continue
        sensors[side] = {"sensor": sensor, "sole": sole_path}
        print(f"[isaac_hub_play] {side} 足裏センサ {foot_path}")
    return sensors


def _read_sole(bundle: dict | None, seq: int) -> dict:
    """1枚の足板の接触を、Hub と同じ四隅の辞書にする。"""
    if bundle is None:
        return sample_from_points([], seq, ok=False)
    try:
        points = _plate_contact_points(bundle["sensor"], bundle["sole"])
    except Exception as exc:
        # 同じ失敗を毎フレーム出すと、原因の行が流れる。文言が変わったときだけ出す。
        text = str(exc)
        if text != getattr(_read_sole, "_last_error", None):
            _read_sole._last_error = text
            print(f"[isaac_hub_play] 足裏の接触を読めませんでした: {text}")
        return sample_from_points([], seq, ok=False)
    return sample_from_points(points, seq, ok=True)


def _plate_contact_points(sensor, sole_path: str) -> list[tuple[float, float, float]]:
    """床と足板の接触を、足裏中心の (x, y, 圧縮[N]) にする。

    力積はどちらの剛体向きか決まらないので、足裏の上向き成分の絶対値を圧縮とする。
    横滑りは法線成分に入らない。サーボ箱など板の外の接触は捨てる。
    """
    import omni.usd
    from pxr import Gf, PhysicsSchemaTools, UsdGeom

    raw = sensor.get_raw_data()
    if not raw:
        return []

    stage = omni.usd.get_context().get_stage()
    sole = stage.GetPrimAtPath(sole_path)
    world = UsdGeom.XformCache().GetLocalToWorldTransform(sole)
    inverse = world.GetInverse()
    # Isaac Sim 6 の pxr は Vec3d * Matrix4d を受け付けない。方向は TransformDir。
    up = world.TransformDir(Gf.Vec3d(0.0, 0.0, 1.0))
    length = (up[0] * up[0] + up[1] * up[1] + up[2] * up[2]) ** 0.5
    if length < 1e-8:
        return []
    zx, zy, zz = up[0] / length, up[1] / length, up[2] / length

    # 接触点は面より少し外に出ることがある。板の外形に 2 cm の余裕を見る。
    margin = 0.02
    points: list[tuple[float, float, float]] = []
    for contact in raw:
        body0 = str(PhysicsSchemaTools.intToSdfPath(int(contact["body0"])))
        body1 = str(PhysicsSchemaTools.intToSdfPath(int(contact["body1"])))
        if "ground" not in body0.lower() and "ground" not in body1.lower():
            continue
        dt = float(contact.get("dt") or 0.0)
        if dt <= 0.0:
            continue
        impulse = contact["impulse"]
        normal_n = abs(
            float(impulse["x"]) * zx + float(impulse["y"]) * zy + float(impulse["z"]) * zz
        ) / dt
        if normal_n <= 0.0:
            continue
        position = contact["position"]
        # ワールドの接触点を、足裏下面中心の座標へ移す。平行移動も含むので Transform。
        local = inverse.Transform(
            Gf.Vec3d(float(position["x"]), float(position["y"]), float(position["z"]))
        )
        if abs(float(local[2])) > margin:
            continue
        if abs(float(local[0])) > PLATE_HALF_X_M + margin:
            continue
        if abs(float(local[1])) > PLATE_HALF_Y_M + margin:
            continue
        points.append((float(local[0]), float(local[1]), normal_n))
    return points


class _TcpClient:
    """橋への TCP。切れていてもシミュレーションは止めない。"""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._buf = b""
        self._inbox: list[dict] = []
        self._next_try = 0.0
        self._next_send = 0.0
        self.connected = False

    def poll(self) -> None:
        now = time.time()
        if self._sock is None:
            if now < self._next_try:
                return
            self._next_try = now + 1.0
            self._connect()
            return
        try:
            chunk = self._sock.recv(65536)
        except BlockingIOError:
            return
        except OSError:
            self._close()
            return
        if not chunk:
            self._close()
            return
        self._buf += chunk
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                self._inbox.append(json.loads(text))
            except json.JSONDecodeError:
                print(f"[isaac_hub_play] 壊れた行を捨てました: {text[:80]}")

    def take_messages(self) -> list[dict]:
        found = self._inbox
        self._inbox = []
        return found

    def due(self) -> bool:
        """Hub へは 20 Hz まで。物理サブステップごとに送らない。"""
        now = time.time()
        if now < self._next_send:
            return False
        self._next_send = now + 0.05
        return True

    def send(self, payload: dict) -> None:
        if self._sock is None:
            return
        data = (json.dumps(payload) + "\n").encode("utf-8")
        try:
            self._sock.sendall(data)
        except OSError:
            self._close()

    def _connect(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.4)
        try:
            sock.connect((ISAAC_TCP_HOST, ISAAC_TCP_PORT))
        except OSError:
            sock.close()
            return
        sock.setblocking(False)
        self._sock = sock
        self.connected = True
        print(f"[isaac_hub_play] 橋へ接続しました {ISAAC_TCP_HOST}:{ISAAC_TCP_PORT}")

    def _close(self) -> None:
        self.connected = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._buf = b""


if __name__ == "__main__":
    # ISAAC_PATH は isaac-lab と同じ環境変数。未設定でも python.bat 経由なら不要。
    if not os.environ.get("ISAAC_PATH"):
        os.environ["ISAAC_PATH"] = r"C:\isaacsim"
    main()
