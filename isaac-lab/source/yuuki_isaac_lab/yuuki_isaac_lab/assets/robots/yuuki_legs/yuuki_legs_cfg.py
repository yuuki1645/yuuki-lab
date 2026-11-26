"""カゴと両脚のアーティキュレーション。

歩行の学習は Fusion の BipedAssembly.urdf を読む。箱の yuuki_biped.urdf は、
手動の踵操作がまだ逆運動学を箱の寸法で解いているので、こちらに残す。

Fusion の USD は、再生用の固定カゴキャッシュとも、箱の .usd_float とも別にする。
カゴは地面へ固定しない。自己衝突は切る。股のホーンと骨盤が重なって跳ねるため。
"""

from __future__ import annotations

import math
from pathlib import Path

from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.sim.converters import UrdfConverterCfg
from isaaclab.sim.spawners.from_files import UrdfFileCfg

from yuuki_isaac_lab.assets.robots.yuuki_legs.fusion_size import (
    SOLE_BELOW_ORIGIN_M as FUSION_SOLE_BELOW_ORIGIN_M,
)
from yuuki_isaac_lab.assets.robots.yuuki_legs.model_size import (
    HIP_SEPARATION_M,
    LEG_LENGTH_HIP_TO_ANKLE_M,
    PLATE_WIDTH_Y_M,
    SOLE_BELOW_ORIGIN_M,
)

# 箱モデルだけ。板の内側 4 cm を空ける股ロール。歩行報酬の開脚角とは別。
_BOX_INNER_CLEARANCE_M = 0.04
_BOX_OPEN_STANCE_ROLL_RAD = math.asin(
    (PLATE_WIDTH_Y_M + _BOX_INNER_CLEARANCE_M - HIP_SEPARATION_M) / (2.0 * LEG_LENGTH_HIP_TO_ANKLE_M)
)

# リポジトリ直下の robot_description。yuuki_legs → robots → assets →
# パッケージ → 拡張 → source → isaac-lab → リポジトリ。
_REPO_ROOT = Path(__file__).resolve().parents[7]
_URDF_PATH = _REPO_ROOT / "robot_description" / "yuuki_biped.urdf"
# Hub 再生の .usd_cache（カゴ固定）とは別。
_USD_DIR = _REPO_ROOT / "robot_description" / ".usd_float"

# 1 cm 上から落として、足裏板を床に乗せる。高さ自体は yaml の足裏距離。
SPAWN_CLEARANCE_M = 0.01
# 直立確認で板が床に乗った仮の位置ゲイン。実機の PD ではない。
JOINT_STIFFNESS = 80.0
JOINT_DAMPING = 2.0
# サーボのトルク上限。無限トルクで姿勢を保たせない。
EFFORT_LIMIT_NM = 14.7


def _spawn_yuuki_legs(prim_path: str, cfg: UrdfFileCfg, translation=None, orientation=None, **kwargs):
    """URDF を置き、足までの接触報告を付ける。

    標準の接触報告は最初の剛体（カゴ）で子の探索を止める。足はカゴの子なので、
    ここで足裏まで付けないと ContactSensor はカゴしか見ない。
    自己衝突は、変換済み USD が 0 でもここで 1 にする。左右の板は隣り合うリンクではない。
    箱の重なりは URDF 生成側で止めてある。
    spawn_from_urdf は USD を読むので、シミュレータ起動前の設定読み込みでは呼ばない。
    """
    from isaaclab.sim.spawners.from_files.from_files import spawn_from_urdf

    prim = spawn_from_urdf(prim_path, cfg, translation=translation, orientation=orientation, **kwargs)
    _enable_nested_contact_report(prim_path)
    _enable_self_collision(prim_path)
    return prim


def _applied_api_known(schema_name: str) -> bool:
    """この Kit に、その Applied API の定義があるか。"""
    from pxr import Usd

    try:
        return bool(Usd.SchemaRegistry.IsAppliedAPISchema(schema_name))
    except Exception:
        return False


def _enable_self_collision(prim_path: str) -> None:
    """関節の根に自己衝突を付ける。

    URDF 取り込みは allow_self_collision を渡しても、保存された
    newton:selfCollisionEnabled が 0 のままになることがある。
    0 のままだと左右のアルミ板がすり抜ける。物理が始まる前に 1 にする。
    """
    from pxr import Sdf

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
        if not under_robot:
            continue
        schemas = set(prim.GetAppliedSchemas())
        has_physx_root = "PhysicsArticulationRootAPI" in schemas
        has_newton_root = "NewtonArticulationRootAPI" in schemas
        if not has_physx_root and not has_newton_root:
            continue
        # Isaac Sim 6 は Newton。スキーマが無い Kit で ApplyAPI すると、その場で落ちる。
        if has_newton_root or _applied_api_known("NewtonArticulationRootAPI"):
            if not has_newton_root:
                prim.ApplyAPI("NewtonArticulationRootAPI")
            attr = prim.GetAttribute("newton:selfCollisionEnabled")
            if not attr or not attr.IsValid():
                attr = prim.CreateAttribute("newton:selfCollisionEnabled", Sdf.ValueTypeNames.Bool)
            attr.Set(True)
        # Isaac Sim 5.1 は PhysX。URDF 取り込みが自己衝突を 0 のまま残すことがある。
        if has_physx_root:
            physx_attr = prim.GetAttribute("physxArticulation:enabledSelfCollisions")
            if not physx_attr or not physx_attr.IsValid():
                from pxr import PhysxSchema

                PhysxSchema.PhysxArticulationAPI.Apply(prim)
                physx_attr = prim.GetAttribute("physxArticulation:enabledSelfCollisions")
            if physx_attr and physx_attr.IsValid():
                physx_attr.Set(True)


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


YUUKI_LEGS_CFG = ArticulationCfg(
    prim_path="{ENV_REGEX_NS}/Robot",
    spawn=UrdfFileCfg(
        func=_spawn_yuuki_legs,
        asset_path=str(_URDF_PATH),
        usd_dir=str(_USD_DIR),
        fix_base=False,
        # 足裏の参照リンクを残す。固定関節をまとめると、足裏の球まで親に吸収される。
        merge_fixed_joints=False,
        # URDF に衝突形状がある。見た目から作ると目印の球まで床に当たる。
        collision_from_visuals=False,
        # 足裏の接触を ContactSensor が読めるようにする。
        activate_contact_sensors=True,
        # 関節の隣以外は全部当たる。箱の食い込みは URDF 生成時に止めてある。
        # URDF の中身が変わると変換キャッシュのハッシュも変わるので、古い USD は作り直される。
        self_collision=True,
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
        # ピッチは 0 のまま。ロールだけ、板の内側が約 4 cm 空く角度にする。
        # 正の股ロールは左右とも開く。足首は逆にして、板を床と平行に戻す。
        # 「.*」と併用すると同じ関節が二度一致して初期化に失敗する。
        joint_pos={
            ".*_pitch": 0.0,
            "left_hip_roll": _BOX_OPEN_STANCE_ROLL_RAD,
            "right_hip_roll": _BOX_OPEN_STANCE_ROLL_RAD,
            "left_ankle_roll": -_BOX_OPEN_STANCE_ROLL_RAD,
            "right_ankle_roll": -_BOX_OPEN_STANCE_ROLL_RAD,
        },
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


def _spawn_fusion_biped(prim_path: str, cfg: UrdfFileCfg, translation=None, orientation=None, **kwargs):
    """Fusion の URDF を置き、足までの接触報告だけを付ける。

    自己衝突は付けない。股のホーンと骨盤のメッシュが重なって、立ち始めに跳ねる。
    再生スクリプトと同じ判断。接触報告は足がカゴの子でも読めるように、剛体すべてへ付ける。
    """
    from isaaclab.sim.spawners.from_files.from_files import spawn_from_urdf

    prim = spawn_from_urdf(prim_path, cfg, translation=translation, orientation=orientation, **kwargs)
    _enable_nested_contact_report(prim_path)
    return prim


# 1 cm 上から落として、Fusion の足裏を床に乗せる。
_FUSION_SPAWN_CLEARANCE_M = 0.01
# RDS51150。12 V の堵転 165 kg·cm と、無負荷 0.21 秒/60°。
_RDS_EFFORT_NM = 16.2
_RDS_VELOCITY_RAD_S = 5.0
# SM105BL。定格 50 kg·cm。堵転 150 kg·cm を歩きの上限にしない。無負荷 0.167 秒/60°。
_SM105_EFFORT_NM = 4.9
_SM105_VELOCITY_RAD_S = 6.3

_FUSION_DESCRIPTION = _REPO_ROOT / "fusion-urdf-export" / "BipedAssembly_description"
_FUSION_URDF = _FUSION_DESCRIPTION / "urdf" / "BipedAssembly.urdf"
# 再生の .usd_fusion_hub はカゴ固定。学習用は浮いたベースで別にキャッシュする。
_FUSION_USD_DIR = _REPO_ROOT / "fusion-urdf-export" / ".usd_walk"

FUSION_LEGS_CFG = ArticulationCfg(
    prim_path="{ENV_REGEX_NS}/Robot",
    spawn=UrdfFileCfg(
        func=_spawn_fusion_biped,
        asset_path=str(_FUSION_URDF),
        usd_dir=str(_FUSION_USD_DIR),
        # package://BipedAssembly_description/meshes/... を、書き出しディレクトリで解く。
        ros_package_paths=[
            {"name": "BipedAssembly_description", "path": str(_FUSION_DESCRIPTION)},
        ],
        fix_base=False,
        # 足リンクを親へ吸収しない。接触は L_FOOT / R_FOOT を名指しで読む。
        merge_fixed_joints=False,
        # URDF に衝突 STL がある。見た目の DAE から作ると、重なったホーンまで床に当たる。
        collision_from_visuals=False,
        activate_contact_sensors=True,
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
        pos=(0.0, 0.0, FUSION_SOLE_BELOW_ORIGIN_M + _FUSION_SPAWN_CLEARANCE_M),
        # 関節 0 が直立。股の間隔が既に板幅 + 4 cm なので、ロールは開かない。
        joint_pos={".*": 0.0},
    ),
    actuators={
        # 股ロール、股ピッチ、かかとロール。URDF の effort 100 / velocity 1 は使わない。
        "rds51150": ImplicitActuatorCfg(
            joint_names_expr=[".*_hip_roll", ".*_hip_pitch", ".*_ankle_roll"],
            stiffness=JOINT_STIFFNESS,
            damping=JOINT_DAMPING,
            effort_limit_sim=_RDS_EFFORT_NM,
            velocity_limit_sim=_RDS_VELOCITY_RAD_S,
        ),
        # ひざ、かかとピッチ。
        "sm105bl": ImplicitActuatorCfg(
            joint_names_expr=[".*_knee_pitch", ".*_ankle_pitch"],
            stiffness=JOINT_STIFFNESS,
            damping=JOINT_DAMPING,
            effort_limit_sim=_SM105_EFFORT_NM,
            velocity_limit_sim=_SM105_VELOCITY_RAD_S,
        ),
    },
)
