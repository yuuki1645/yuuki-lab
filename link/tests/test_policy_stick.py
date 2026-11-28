"""画面スティックが腰へ渡す前進の範囲と、包絡の境界ログ。"""

from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "py" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


stick = _load("policy_stick")


class PolicyStickTest(unittest.TestCase):
    def test_clamp_keeps_forward_inside_servo_command_range(self) -> None:
        self.assertEqual(stick.clamp_policy_vx(0.05), 0.05)
        self.assertEqual(stick.clamp_policy_vx(-0.4), 0.0)
        self.assertEqual(stick.clamp_policy_vx(3.0), 0.2)
        self.assertIsNone(stick.clamp_policy_vx("0.1"))
        self.assertIsNone(stick.clamp_policy_vx(True))
        self.assertIsNone(stick.clamp_policy_vx(float("nan")))
        self.assertIsNone(stick.clamp_policy_vx(None))

    def test_note_only_when_the_envelope_boundary_changes(self) -> None:
        # 0.02 以下は包絡が残る。0.03 で外れる。
        self.assertIsNone(stick.policy_stick_note(0.0, 0.02))
        off = stick.policy_stick_note(0.02, 0.03)
        self.assertIsNotNone(off)
        self.assertIn("外れ", off or "")
        # 倒しているあいだの小さな変化はノートにしない。
        self.assertIsNone(stick.policy_stick_note(0.05, 0.08))
        back = stick.policy_stick_note(0.08, 0.01)
        self.assertIsNotNone(back)
        self.assertIn("戻", back or "")
        center = stick.policy_stick_note(0.01, 0.0)
        self.assertEqual(center, "スティック  中央  vx=0")
        self.assertFalse(math.isnan(stick.POLICY_VX_STAND_MPS))
