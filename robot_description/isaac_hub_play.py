#!/usr/bin/env python3
"""Isaac Sim の窓を開き、Hub の指令角で脚を 1 体動かす。

C:\\isaacsim にはパッケージを入れない。このファイルはリポジトリに置き、
Isaac 同梱の Python で起動する。

    C:\\isaacsim\\python.bat Z:\\Projects\\yuuki-lab\\robot_description\\isaac_hub_play.py

既定は Fusion から書き出した BipedAssembly.urdf である。箱モデルで
今までどおり見るときは --box を付ける。学習タスクの URDF は変えない。

先に isaac_hub_bridge.py を起動しておく。橋が無いあいだは再接続しながら、
ロボットは直立のまま物理を進める。Hub のバーが関節目標になる。
RDS は 135°、ひざとかかとピッチは真下 0° が URDF の 0。
今の関節角は橋を通して画面の「補正（シミュ）」へ戻る。

根は地面に固定する（fix_base）。バーで関節を見るための再生であり、
歩行学習の浮動ベースではない。
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# SimulationApp より前に読んでよいのは、標準ライブラリだけの hub_link。
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from hub_link import ISAAC_TCP_HOST, ISAAC_TCP_PORT, JOINT_COUNT, joint_names
from sole_pressure import PLATE_HALF_X_M, PLATE_HALF_Y_M, sample_from_points

from model_size import SOLE_BELOW_ORIGIN_M

# 箱モデルの直立。原点から足裏まで。高さは yaml から読む。
# Fusion 版の根はカゴ底ではないので、この値は --box のときだけ使う。
BOX_SPAWN_Z_M = SOLE_BELOW_ORIGIN_M
# Fusion の書き出しで、base_link から足首関節までが約 0.83 m。
# 足板と出力ホーンの厚みを足して、足裏が床の少し上に来る高さ。
# 正確な足裏距離はまだ測っていない。根は固定なので、少しくらい浮いても関節は見える。
FUSION_SPAWN_Z_M = 0.90
# 位置制御。実機の PD そのものではなく、バー操作が追従するための仮のゲイン。
JOINT_STIFFNESS = 80.0
JOINT_DAMPING = 2.0

_REPO = _HERE.parent
_FUSION_DESCRIPTION = _REPO / "fusion-urdf-export" / "BipedAssembly_description"
# 箱モデルの .usd_cache とは分ける。同じフォルダだと yuuki_biped.usd を
# 掴んだまま、Fusion のメッシュを読まない。
_FUSION_USD_CACHE = _HERE / ".usd_fusion_hub"
_BOX_USD_CACHE = _HERE / ".usd_cache"


@dataclass(frozen=True)
class _PlayModel:
    """この窓が動かす URDF と、変換時に変える当たり判定。"""

    label: str
    urdf: Path
    usd_cache: Path
    # 変換結果のファイル名。ロボット名 + 拡張子。箱は .usd、Fusion は .usda。
    usd_names: tuple[str, ...]
    spawn_z_m: float
    collision_from_visuals: bool
    allow_self_collision: bool
    # (画面の左右, センサを付けるリンク, 足裏平面に使うリンク)
    feet: tuple[tuple[str, str, str], ...]
    # package:// を解決する ROS パッケージ。箱モデルはメッシュを持たない。
    package_name: str
    package_path: Path | None


def _fusion_model() -> _PlayModel:
    """CAD の URDF。自己衝突は切る。股のホーンと骨盤が重なって跳ねるため。"""
    return _PlayModel(
        label="Fusion BipedAssembly",
        urdf=_FUSION_DESCRIPTION / "urdf" / "BipedAssembly.urdf",
        usd_cache=_FUSION_USD_CACHE,
        usd_names=("BipedAssembly.usda", "BipedAssembly.usd"),
        spawn_z_m=FUSION_SPAWN_Z_M,
        collision_from_visuals=False,
        allow_self_collision=False,
        # 足裏の参照リンクは無い。足リンク自身を平面の原点にする。
        feet=(("right", "R_FOOT", "R_FOOT"), ("left", "L_FOOT", "L_FOOT")),
        package_name="BipedAssembly_description",
        package_path=_FUSION_DESCRIPTION,
    )


def _box_model() -> _PlayModel:
    """yaml から作った箱。当たり箱は離してあるので、見た目からの衝突と自己衝突を残す。"""
    return _PlayModel(
        label="yuuki_biped box",
        urdf=_HERE / "yuuki_biped.urdf",
        usd_cache=_BOX_USD_CACHE,
        usd_names=("yuuki_biped.usd", "yuuki_biped.usda"),
        spawn_z_m=BOX_SPAWN_Z_M,
        collision_from_visuals=True,
        allow_self_collision=True,
        feet=(("right", "right_foot", "right_sole"), ("left", "left_foot", "left_sole")),
        package_name="",
        package_path=None,
    )


def _configure(argv: list[str]) -> _PlayModel:
    """--box なら箱モデル。それ以外は Fusion 版。"""
    if "--box" in argv:
        return _box_model()
    return _fusion_model()


def _self_check() -> None:
    """Isaac を開かずに、既定の読み込み先と当たり判定だけ確かめる。"""
    fusion = _configure(["isaac_hub_play.py"])
    box = _configure(["isaac_hub_play.py", "--box"])
    if fusion.urdf.name != "BipedAssembly.urdf":
        raise SystemExit(f"既定の URDF が Fusion 版ではありません: {fusion.urdf}")
    if not fusion.urdf.is_file():
        raise SystemExit(f"Fusion の URDF がありません: {fusion.urdf}")
    if fusion.collision_from_visuals or fusion.allow_self_collision:
        raise SystemExit("Fusion 版は自己衝突と、見た目からの衝突を切ります")
    if fusion.usd_cache == box.usd_cache:
        raise SystemExit("Fusion の USD キャッシュが箱モデルと同じです")
    if box.urdf.name != "yuuki_biped.urdf" or not box.collision_from_visuals:
        raise SystemExit("--box が箱モデルの設定になっていません")
    if fusion.feet[0][1] != "R_FOOT" or box.feet[0][1] != "right_foot":
        raise SystemExit("足リンク名がモデルと合っていません")
    print("isaac_hub_play self-check: OK")
    print(f"  fusion {fusion.urdf}")
    print(f"  box    {box.urdf}")


def main() -> None:
    model = _configure(sys.argv)
    # Kit は知らない引数で起動に失敗する。こちらのフラグは渡す前に外す。
    sys.argv = [arg for arg in sys.argv if arg not in ("--box", "--self-check")]
    from isaacsim import SimulationApp

    # 先に isaac-sim.bat で GUI を開いたままにしない。このプロセスが窓を持つ。
    simulation_app = SimulationApp({"headless": False, "renderer": "RaytracedLighting"})
    try:
        _run(simulation_app, model)
    finally:
        simulation_app.close()


def _run(simulation_app, model: _PlayModel) -> None:
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

    print(f"[isaac_hub_play] モデル {model.label}")
    usd_path = _import_urdf(URDFImporter, URDFImporterConfig, model)
    _build_stage(usd_path, UsdGeom, UsdLux, UsdPhysics, Gf, model)
    for _ in range(10):
        simulation_app.update()
    # 箱モデルは見た目から衝突を作るので、足裏の目印球が床に当たる。
    # Fusion 版はその球が無く、衝突は URDF のメッシュのまま使う。
    if model.collision_from_visuals:
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

    soles = _create_sole_sensors(model)

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


def _import_urdf(importer_cls, config_cls, model: _PlayModel) -> str:
    """URDF が USD キャッシュより新しければ変換し、USD のパスを返す。

    キャッシュはモデルごとのファイル名だけを見る。箱の yuuki_biped.usd が
    残っていても、Fusion の変換結果にはしない。
    """
    if not model.urdf.is_file():
        raise SystemExit(f"URDF がありません: {model.urdf}")
    model.usd_cache.mkdir(parents=True, exist_ok=True)
    # 変換結果はキャッシュ直下とは限らない（BipedAssembly/BipedAssembly.usda など）。
    cached = [
        path
        for name in model.usd_names
        for path in model.usd_cache.rglob(name)
    ]
    urdf_mtime = model.urdf.stat().st_mtime
    fresh = [path for path in cached if path.stat().st_mtime >= urdf_mtime]
    if fresh:
        chosen = max(fresh, key=lambda path: path.stat().st_mtime)
        print(f"[isaac_hub_play] USD キャッシュを使います: {chosen}")
        return str(chosen)

    config = config_cls()
    config.urdf_path = str(model.urdf)
    config.usd_path = str(model.usd_cache)
    # バーで関節を見るあいだ、根を世界に固定して転倒させない。
    config.fix_base = True
    config.merge_fixed_joints = False
    config.joint_target_type = "position"
    config.joint_drive_type = "force"
    config.override_joint_stiffness = JOINT_STIFFNESS
    config.override_joint_damping = JOINT_DAMPING
    # Fusion は URDF の衝突メッシュを使う。見た目の DAE から作ると、
    # 重なった股のホーンまで床や隣のリンクに当たる。
    config.collision_from_visuals = model.collision_from_visuals
    config.allow_self_collision = model.allow_self_collision
    if model.package_path is not None:
        # package://BipedAssembly_description/meshes/... を、
        # package.xml があるディレクトリへ解決する。
        config.ros_package_paths = [
            {"name": model.package_name, "path": str(model.package_path)}
        ]
    print(f"[isaac_hub_play] URDF を変換します: {model.urdf}")
    output = importer_cls(config).import_urdf()
    if not output:
        raise SystemExit("URDF の変換に失敗しました")
    print(f"[isaac_hub_play] USD {output}")
    return str(output)


def _build_stage(usd_path: str, UsdGeom, UsdLux, UsdPhysics, Gf, model: _PlayModel) -> None:
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

    robot = stage.DefinePrim("/World/robot", "Xform")
    robot.GetReferences().AddReference(usd_path)
    UsdGeom.Xformable(robot).AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, model.spawn_z_m))


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


# 足裏中心の球。見た目から衝突を作る変換だと、この球が床に当たる。
# 足サーボは板の上にあるので切らない。反対の脚に当たる必要がある。
_NON_PLATE_COLLISIONS = (
    "left_sole_sole_marker_0",
    "right_sole_sole_marker_0",
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


def _create_sole_sensors(model: _PlayModel) -> dict[str, dict | None]:
    """左右の足リンクに Contact Sensor を付ける。失敗した足は None。

    箱モデルは right_sole / left_sole を足裏平面にする。Fusion 版には
    そのリンクが無いので、R_FOOT / L_FOOT 自身を平面にする。関節角の
    返信はこのセンサが無くても続く。
    """
    from isaacsim.sensors.experimental.physics import Contact, ContactSensor

    by_name = _prims_by_name()
    sensors: dict[str, dict | None] = {}
    for side, foot_name, sole_name in model.feet:
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
    if "--self-check" in sys.argv:
        _self_check()
        raise SystemExit(0)
    # ISAAC_PATH は isaac-lab と同じ環境変数。未設定でも python.bat 経由なら不要。
    if not os.environ.get("ISAAC_PATH"):
        os.environ["ISAAC_PATH"] = r"C:\isaacsim"
    main()
