"""再生の方策ステップを、ローカルへ書き、閉じた断片だけを NAS へ送る。"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
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


play = _load("sim_play_log")
import policy_trace as trace


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class _Names:
    def __init__(self, value: str = "直立") -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def _row(seq: int, action: list[float], cmd: list[float]) -> dict:
    obs = [0.0] * 38
    obs[0] = float(seq)
    return {
        "seq": seq,
        "t_period_us": 33333,
        "obs": obs,
        "action": action,
        "cmd_rad": cmd,
        "joint_flag": [0] * 10,
        "safety": 0,
        "foot_bearing": True,
    }


class SimPlayLogTest(unittest.TestCase):
    def _log(self, root: Path, archive: Path | None, clock: _Clock, names: _Names):
        paths = play._real.StoragePaths(root, archive)
        return play.SimPlayLog(
            paths,
            copy_async=False,
            clock=clock,
            name_of=names,
        )

    def test_closed_part_is_archived_with_unclamped_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            archive = Path(tmp) / "nas"
            clock = _Clock()
            names = _Names("直立")
            log = self._log(root, archive, clock, names)
            action = [1.0, -2.0] + [0.0] * 8
            cmd = [1.5, -0.5] + [0.0] * 8
            log.write(_row(1, action, cmd))
            assert log._take is not None
            take = log._take.directory
            # 開いている断片は、保管先にまだ無い。
            self.assertFalse((archive / take.relative_to(root) / "policy" / "part-000.jsonl").is_file())
            self.assertTrue((archive / take.relative_to(root) / "context.json").is_file())
            log.close()
            archived = archive / take.relative_to(root)
            self.assertTrue((archived / "policy" / "part-000.jsonl").is_file())
            self.assertTrue((archived / "meta.json").is_file())
            self.assertEqual(list(root.rglob("*.pending")), [])
            body = json.loads((take / "policy" / "part-000.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(body["action_rad"][0], 0.25)
            self.assertEqual(body["action_rad"][1], -0.5)
            # 再生の cmd_rad は、渡した目標のまま。包絡では切らない。
            self.assertEqual(body["cmd_rad"][0], 1.5)
            context = json.loads((take / "context.json").read_text(encoding="utf-8"))
            self.assertEqual(context["format_id"], "sim_play_v1")
            self.assertEqual(context["experiment"], "直立")
            self.assertEqual(context["project"]["task"], "YuukiLab-BipedWalk-Play-v0")
            self.assertEqual(context["policy"]["action_scale"], 0.25)
            self.assertIn("包絡", context["policy"]["cmd_rad"])
            schema = (take / "schema.md").read_text(encoding="utf-8")
            self.assertIn("sim_play_v1", schema)
            meta = json.loads((take / "meta.json").read_text(encoding="utf-8"))
            self.assertFalse(meta["recording"])
            self.assertEqual(meta["sample_count"], 1)
            found = play.find_play_take(meta["id"], [root / "sim"])
            self.assertEqual(found, take)
            summary = trace.summarize_file(take)
            self.assertEqual(summary["rows"], 1)
            self.assertAlmostEqual(summary["dims"][0]["mean"], 1.0)

    def test_rotate_archives_only_the_closed_part(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            archive = Path(tmp) / "nas"
            clock = _Clock()
            log = self._log(root, archive, clock, _Names())
            log.write(_row(1, [0.0] * 10, [0.0] * 10))
            clock.t = 60.0
            log.write(_row(2, [0.0] * 10, [0.0] * 10))
            log.write(_row(3, [0.0] * 10, [0.0] * 10))
            assert log._take is not None
            take = log._take.directory
            rel = take.relative_to(root)
            self.assertTrue((archive / rel / "policy" / "part-000.jsonl").is_file())
            self.assertFalse((archive / rel / "policy" / "part-001.jsonl").is_file())
            closed = (take / "policy" / "part-000.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual([json.loads(line)["seq"] for line in closed], [1, 2])
            log.close()
            rows = list(trace.iter_source(take))
            self.assertEqual([row["seq"] for row in rows], [1, 2, 3])
            self.assertTrue((archive / rel / "policy" / "part-001.jsonl").is_file())

    def test_experiment_name_starts_a_new_take(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            archive = Path(tmp) / "nas"
            names = _Names("直立")
            log = self._log(root, archive, _Clock(), names)
            log.write(_row(1, [0.0] * 10, [0.0] * 10))
            names.value = "1関節"
            log.write(_row(1, [0.0] * 10, [0.0] * 10))
            log.close()
            takes = [p for p in (root / "sim").glob("*/*/*/*") if p.is_dir() and (p / "meta.json").is_file()]
            self.assertEqual(len(takes), 2)
            labels = set()
            for take in takes:
                meta = json.loads((take / "meta.json").read_text(encoding="utf-8"))
                labels.add(meta["name"])
                self.assertFalse(meta["recording"])
            self.assertEqual(labels, {"直立", "1関節"})
            listed = play.list_play_takes([root / "sim"])
            self.assertEqual({row["name"] for row in listed}, {"直立", "1関節"})

    def test_without_storage_writes_under_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fallback = Path(tmp) / "repo"
            log = play.SimPlayLog(
                None,
                fallback_root=fallback,
                copy_async=False,
                clock=_Clock(),
                name_of=_Names("直立"),
            )
            log.write(_row(1, [0.0] * 10, [0.0] * 10))
            log.close()
            takes = [
                path
                for path in (fallback / "sim").glob("*/*/*/*")
                if path.is_dir() and (path / "meta.json").is_file()
            ]
            self.assertEqual(len(takes), 1)
            self.assertTrue((takes[0] / "policy" / "part-000.jsonl").is_file())

    def test_interrupted_take_is_sealed_on_next_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            archive = Path(tmp) / "nas"
            log = self._log(root, archive, _Clock(), _Names())
            log.write(_row(4, [0.0] * 10, [0.0] * 10))
            assert log._take is not None
            take = log._take.directory
            log._take.policy.close()
            log._take.policy = None
            log._take = None
            play.SimPlayLog(play._real.StoragePaths(root, archive), copy_async=False, clock=_Clock(), name_of=_Names())
            meta = json.loads((take / "meta.json").read_text(encoding="utf-8"))
            self.assertFalse(meta["recording"])
            self.assertEqual(meta["stop_reason"], "中断")
            rel = take.relative_to(root)
            self.assertTrue((archive / rel / "policy" / "part-000.jsonl").is_file())
            self.assertEqual(list(root.rglob("*.pending")), [])


if __name__ == "__main__":
    unittest.main()
