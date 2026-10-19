"""カゴと両脚だけの歩行用アーティキュレーション。

形状の正本は `robot_description/yuuki_biped.urdf`。ここにある古い
`yuuki_biped`（バランス棒つき 12 関節）は使わない。USD は直立確認と同じ
`.usd_float` にキャッシュし、カゴは地面へ固定しない。
"""

from __future__ import annotations

from pathlib import Path

from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.sim.converters import UrdfConverterCfg
from isaaclab.sim.spawners.from_files import UrdfFileCfg

# リポジトリ直下の robot_description。yuuki_legs → robots → assets →
# パッケージ → 拡張 → source → isaac-lab → リポジトリ。
_REPO_ROOT = Path(__file__).resolve().parents[7]
_URDF_PATH = _REPO_ROOT / "robot_description" / "yuuki_biped.urdf"
# Hub 再生の .usd_cache（カゴ固定）とは別。
_USD_DIR = _REPO_ROOT / "robot_description" / ".usd_float"

# 直立時、カゴ底から足裏まで 0.622 m。1 cm 上から落として板を床に乗せる。
SOLE_BELOW_ORIGIN_M = 0.622
SPAWN_CLEARANCE_M = 0.01
# 直立確認で板が床に乗った仮の位置ゲイン。実機の PD ではない。
JOINT_STIFFNESS = 80.0
JOINT_DAMPING = 2.0
# サーボのトルク上限。無限トルクで姿勢を保たせない。
EFFORT_LIMIT_NM = 14.7


def _spawn_yuuki_legs(prim_path: str, cfg: UrdfFileCfg, translation=None, orientation=None, **kwargs):
    """URDF を置いたあと、接触報告と、左右の足裏板だけの衝突を仕込む。

    標準の接触報告は最初の剛体（カゴ）で子の探索を止める。足はカゴの子なので、
    ここで足裏まで付けないと ContactSensor はカゴしか見ない。
    足裏どうしの衝突は、環境の複製が終わったあとでないと全ロボットに付かない。
    spawn_from_urdf は USD を読むので、シミュレータ起動前の設定読み込みでは呼ばない。
    """
    from isaaclab.sim.spawners.from_files.from_files import spawn_from_urdf

    prim = spawn_from_urdf(prim_path, cfg, translation=translation, orientation=orientation, **kwargs)
    _enable_nested_contact_report(prim_path)
    # この時点では env_0 だけにロボットがある。複製の直後に板の衝突を組む。
    _install_sole_collision_after_clone()
    return prim


def _enable_nested_contact_report(prim_path: str) -> None:
    """prim_path に合うロボット以下の、すべての剛体へ接触報告 API を付ける。"""
    from pxr import UsdPhysics

    from isaaclab.sim.utils.prims import safe_set_attribute_on_usd_prim
    from isaaclab.sim.utils.queries import find_matching_prims
    from isaaclab.sim.utils.stage import get_current_stage

    roots = [prim.GetPath().pathString for prim in find_matching_prims(prim_path)]
    stage = get_current_stage()
    for prim in stage.Traverse():
        path = prim.GetPath().pathString
        under_robot = False
        for root in roots:
            if path == root or path.startswith(root + "/"):
                under_robot = True
                break
        if not under_robot or not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        applied = prim.GetAppliedSchemas()
        if "PhysxRigidBodyAPI" not in applied:
            prim.AddAppliedSchema("PhysxRigidBodyAPI")
        # 眠ると接触が欠けるので、しきい値は 0。
        safe_set_attribute_on_usd_prim(prim, "physxRigidBody:sleepThreshold", 0.0, camel_case=False)
        if "PhysxContactReportAPI" not in applied:
            prim.AddAppliedSchema("PhysxContactReportAPI")
        safe_set_attribute_on_usd_prim(prim, "physxContactReport:threshold", 0.0, camel_case=False)


# 複製フックはプロセス内で一度だけ差し替える。
_SOLE_COLLISION_HOOKED = False
_SOLE_COLLISION_DONE = False


def _install_sole_collision_after_clone() -> None:
    """環境複製の直後に、足裏板の衝突設定を走らせる。

    学習は env_0 だけに URDF を置き、残りはそこから複製する。
    複製より前にペアを書くと、コピー先の経路が env_0 のまま残る。
    物理の読み込みより後だと、自己衝突の有無はもう決まっている。
    """
    global _SOLE_COLLISION_HOOKED
    if _SOLE_COLLISION_HOOKED:
        return
    _SOLE_COLLISION_HOOKED = True

    import isaaclab.cloner as cloner

    original = cloner.usd_replicate

    def _replicate_then_filter(*args, **kwargs):
        # 空の環境を広げる最初の複製は、ロボットを置く前なので何もしない。
        result = original(*args, **kwargs)
        _enable_sole_plate_collision()
        return result

    cloner.usd_replicate = _replicate_then_filter


# 足裏板が当たってよい、反対側の脚。サーボ箱どうしはここに入れない。
_OPPOSITE_LEG_LINKS = {
    "left": ("right_thigh", "right_shin"),
    "right": ("left_thigh", "left_shin"),
}


def _enable_sole_plate_collision() -> None:
    """足裏板を、反対の板と、反対のすね・ももに当てる。

    板どうしだけだと、板は厚さ 2 mm しかなく、反対のすねをすり抜けて
    足を重ねられる。サーボ箱どうしは形が重なるので、当たる組に入れない。
    自分のすねとももにも当てない。関節で隣り合う部品は PhysX がもともと無視する。
    """
    global _SOLE_COLLISION_DONE
    if _SOLE_COLLISION_DONE:
        return

    # シミュレータ起動前に読まれるモジュールなので、pxr はここで読む。
    from pxr import PhysxSchema, Sdf, Usd, UsdPhysics

    from isaaclab.sim.utils.stage import get_current_stage

    stage = get_current_stage()
    robots = _robot_prims(stage)
    if not robots:
        return

    plate_count = 0
    leg_count = 0
    # 当たる組は先に決める。書き込みの途中で経路の比較が崩れると、すねまで除外される。
    planned: list[tuple] = []
    for robot in robots:
        colliders = [prim for prim in Usd.PrimRange(robot) if prim.HasAPI(UsdPhysics.CollisionAPI)]
        left = [prim for prim in colliders if _is_foot_plate(prim, "left")]
        right = [prim for prim in colliders if _is_foot_plate(prim, "right")]
        if not left or not right:
            names = ", ".join(prim.GetName() for prim in colliders)
            raise RuntimeError(
                f"{robot.GetPath()} に左右の足裏板の衝突形状がありません。見つかった衝突: {names}"
            )
        _allow_articulation_self_collision(robot)
        plate_count += len(left) + len(right)
        robot_plan, robot_legs = _plan_plate_filters(colliders, left, right)
        planned.extend(robot_plan)
        leg_count += robot_legs
    with Sdf.ChangeBlock():
        for prim, block in planned:
            pairs = UsdPhysics.FilteredPairsAPI.Apply(prim)
            pairs.CreateFilteredPairsRel().SetTargets(block)

    _SOLE_COLLISION_DONE = True
    print(
        "[biped_walk] 足裏板は、反対の板と反対のすね・ももに当たるようにしました。"
        f"ロボット {len(robots)} 体、板 {plate_count} 個、脚の部品 {leg_count} 個"
    )


def _robot_prims(stage) -> list:
    """`/World/envs/env_* /Robot` を、環境番号の順で返す。"""
    envs = stage.GetPrimAtPath("/World/envs")
    if not envs.IsValid():
        return []
    robots = []
    for env in envs.GetChildren():
        robot = env.GetChild("Robot")
        if robot.IsValid():
            robots.append(robot)
    return robots


def _is_foot_plate(prim, side: str) -> bool:
    """アルミ板の衝突プリムか。すねの板やサーボ箱は含めない。"""
    # 変換後は名前が left_foot_foot_plate_1_1 になり、displayName が元の名前になる。
    blob = f"{prim.GetName()} {prim.GetDisplayName() or ''}"
    return side in blob and "foot_plate" in blob


def _allow_articulation_self_collision(robot) -> None:
    """このロボットの自己衝突を許可する。当たらない組は別で除外する。"""
    from pxr import PhysxSchema, Sdf, Usd, UsdPhysics

    found = 0
    for prim in Usd.PrimRange(robot):
        has_physx_root = prim.HasAPI(UsdPhysics.ArticulationRootAPI)
        has_newton_root = prim.HasAPI("NewtonArticulationRootAPI")
        if not has_physx_root and not has_newton_root:
            continue
        PhysxSchema.PhysxArticulationAPI.Apply(prim)
        PhysxSchema.PhysxArticulationAPI(prim).CreateEnabledSelfCollisionsAttr().Set(True)
        # 変換器は Newton 側の旗を False で書く。PhysX は上の属性を見る。
        if has_newton_root or prim.GetAttribute("newton:selfCollisionEnabled"):
            attr = prim.GetAttribute("newton:selfCollisionEnabled")
            if not attr:
                attr = prim.CreateAttribute("newton:selfCollisionEnabled", Sdf.ValueTypeNames.Bool)
            attr.Set(True)
        found += 1
    if found == 0:
        raise RuntimeError(f"{robot.GetPath()} にアーティキュレーションの根がありません")


def _body_link_name(prim) -> str | None:
    """衝突形状が属すリンク名。変換後は子プリムになるので、親を辿る。"""
    current = prim
    while current.IsValid():
        name = current.GetName()
        if name in ("left_thigh", "left_shin", "right_thigh", "right_shin", "left_foot", "right_foot"):
            return name
        current = current.GetParent()
    return None


def _plan_plate_filters(colliders, left: list, right: list) -> tuple[list[tuple], int]:
    """各衝突形状について、同じロボット内で当たらない相手の経路を決める。

    除外は両側に書く。片方だけが相手を残しても、相手側の除外が残ると当たらない。
    経路は文字列で比べる。Sdf.Path のまま集合に入れると、同一視に失敗することがある。
    """
    left_paths = {str(prim.GetPath()) for prim in left}
    right_paths = {str(prim.GetPath()) for prim in right}
    link_of = {str(prim.GetPath()): _body_link_name(prim) for prim in colliders}
    # 右脚のすね・もも。左の板が当たる相手。
    right_leg = {path for path, link in link_of.items() if link in _OPPOSITE_LEG_LINKS["left"]}
    left_leg = {path for path, link in link_of.items() if link in _OPPOSITE_LEG_LINKS["right"]}
    if not right_leg or not left_leg:
        raise RuntimeError("反対側のすね・ももの衝突形状が見つかりません")

    planned: list[tuple] = []
    for prim in colliders:
        path = str(prim.GetPath())
        link = link_of[path]
        if path in left_paths:
            keep = right_paths | right_leg
        elif path in right_paths:
            keep = left_paths | left_leg
        elif link in _OPPOSITE_LEG_LINKS["left"]:
            # 右のすね・ももは、左の板に当たる。
            keep = left_paths
        elif link in _OPPOSITE_LEG_LINKS["right"]:
            keep = right_paths
        else:
            keep = set()
        block = [other.GetPath() for other in colliders if str(other.GetPath()) != path and str(other.GetPath()) not in keep]
        planned.append((prim, block))
    return planned, len(left_leg) + len(right_leg)


YUUKI_LEGS_CFG = ArticulationCfg(
    prim_path="{ENV_REGEX_NS}/Robot",
    spawn=UrdfFileCfg(
        func=_spawn_yuuki_legs,
        asset_path=str(_URDF_PATH),
        usd_dir=str(_USD_DIR),
        fix_base=False,
        # 足裏リンクを残し、足首サーボの衝突プリムを名前で切れるようにする。
        merge_fixed_joints=False,
        # URDF に衝突形状がある。見た目から作ると目印の球まで床に当たる。
        collision_from_visuals=False,
        # 足裏の接触を ContactSensor が読めるようにする。
        activate_contact_sensors=True,
        # 変換時は切ったままにする。入れるとサーボ箱どうしも当たる USD がキャッシュされる。
        # 板と、反対の板・すね・ももだけは、複製の直後に有効にする。
        self_collision=False,
        joint_drive=UrdfConverterCfg.JointDriveCfg(
            drive_type="force",
            target_type="position",
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(
                stiffness=JOINT_STIFFNESS,
                damping=JOINT_DAMPING,
            ),
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, SOLE_BELOW_ORIGIN_M + SPAWN_CLEARANCE_M),
        joint_pos={".*": 0.0},
    ),
    actuators={
        "legs": ImplicitActuatorCfg(
            joint_names_expr=[".*"],
            stiffness=JOINT_STIFFNESS,
            damping=JOINT_DAMPING,
            effort_limit_sim=EFFORT_LIMIT_NM,
        ),
    },
)
