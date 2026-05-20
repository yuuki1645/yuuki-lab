"""MuJoCo 接触の読み取り（報酬・終了判定で共有）。"""

import mujoco
import numpy as np

# mj_contactForce の出力先（ループ内で再利用）
_CONTACT_WRENCH = np.zeros(6)


def max_normal_force_between_geoms(
  model: mujoco.MjModel,
  data: mujoco.MjData,
  geom_a_id: int,
  geom_b_id: int,
) -> float:
  """2 geom 間の接触のうち、法線力 |force[0]| の最大値 [N]。接触なしなら 0。"""
  peak_normal_force_n = 0.0
  for contact_index in range(data.ncon):
    contact = data.contact[contact_index]
    if not _is_geom_pair(contact, geom_a_id, geom_b_id):
      continue
    mujoco.mj_contactForce(model, data, contact_index, _CONTACT_WRENCH)
    peak_normal_force_n = max(peak_normal_force_n, abs(float(_CONTACT_WRENCH[0])))
  return peak_normal_force_n


def has_contact_between_geoms(
  data: mujoco.MjData,
  geom_a_id: int,
  geom_b_id: int,
) -> bool:
  """2 geom 間に接触が1つでもあるか。"""
  for contact_index in range(data.ncon):
    if _is_geom_pair(data.contact[contact_index], geom_a_id, geom_b_id):
      return True
  return False


def _is_geom_pair(contact: mujoco.MjContact, geom_a_id: int, geom_b_id: int) -> bool:
  """geom1/geom2 の順序は MuJoCo が入れ替えることがある。"""
  return (contact.geom1 == geom_a_id and contact.geom2 == geom_b_id) or (
    contact.geom1 == geom_b_id and contact.geom2 == geom_a_id
  )
