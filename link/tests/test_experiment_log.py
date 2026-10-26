"""実験記録の保存先、take の開閉、閉じたファイルのコピー。"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "py" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    mod = importlib.util.module_from_spec(spec)
    # dataclass が cls.__module__ を引くので、実行前に登録する。
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


logmod = _load("experiment_log")
proto = _load("rt_usb_proto")


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class StorageParseTest(unittest.TestCase):
    def test_reads_two_roots_and_ignores_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "storage.yaml"
            path.write_text(
                '# コメント\ndata_root: "D:/lab-data"\narchive_root: \'Z:/lab\'\n',
                encoding="utf-8",
            )
            got = logmod.load_storage(path)
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(got.data_root, Path("D:/lab-data"))
            self.assertEqual(got.archive_root, Path("Z:/lab"))

    def test_missing_file_is_none(self) -> None:
        self.assertIsNone(logmod.load_storage(Path(tempfile.gettempdir()) / "no-such-storage.yaml"))


class TakeTest(unittest.TestCase):
    def _paths(self, root: Path, archive: Path | None) -> object:
        return logmod.StoragePaths(root, archive)

    def test_hello_repeat_keeps_one_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            archive = Path(tmp) / "nas"
            log = logmod.ExperimentLog(self._paths(root, archive), copy_async=False)
            first = log.begin("COM4", "rt-usb ver=15 lab", 15)
            second = log.begin("COM4", "rt-usb ver=15 lab", 15)
            other = log.begin("COM5", "rt-usb ver=15 lab", 15)
            self.assertTrue(first.ok)
            self.assertEqual(second.reason, "already")
            self.assertEqual(other.reason, "busy")
            log.append_frame("COM4", {"seq": 1, "cmd": [1.0]})
            log.append_frame("COM4", {"seq": 1, "cmd": [9.0]})
            log.append_command("COM4", proto.tx_record(proto.cmd_joint(2, 12.5)))
            log.append_event("COM4", "09:00:00  スキャン 1 ノード")
            log.end("COM9", "関係ない切断")
            self.assertIsNotNone(log._take)
            log.end("COM4", "USB 切断")
            self.assertIsNone(log._take)
            takes = [p for p in root.glob("*/*/*/*") if p.is_dir()]
            self.assertEqual(len(takes), 1)
            self.assertRegex(takes[0].name, r"^001_\d{6}$")
            meta = json.loads((takes[0] / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["day_index"], 1)
            self.assertEqual(meta["take_id"], takes[0].name)
            self.assertFalse(meta["recording"])
            self.assertEqual(meta["sample_count"], 1)
            self.assertEqual(meta["stop_reason"], "USB 切断")
            self.assertEqual(meta["notes"], "")
            self.assertEqual(meta["schema"], "schema.md")
            schema = (takes[0] / "schema.md").read_text(encoding="utf-8")
            self.assertIn("core_take_v1", schema)
            self.assertIn("股ロール", schema)
            self.assertIn("day_index", schema)
            self.assertTrue((archive / takes[0].relative_to(root) / "schema.md").is_file())
            frames = (takes[0] / "sensors" / "part-000.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(frames), 1)
            self.assertEqual(json.loads(frames[0])["cmd"], [1.0])
            command = json.loads(
                (takes[0] / "commands" / "part-000.jsonl").read_text(encoding="utf-8")
            )
            self.assertEqual(command["ch"], 2)
            self.assertEqual(command["deg"], 12.5)
            archived = archive / takes[0].relative_to(root) / "meta.json"
            self.assertTrue(archived.is_file())
            self.assertEqual(list(root.rglob("*.pending")), [])

    def test_rotate_copies_closed_part_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            archive = Path(tmp) / "nas"
            clock = _Clock()
            log = logmod.ExperimentLog(
                self._paths(root, archive),
                flush_sec=10.0,
                rotate_sec=60.0,
                copy_async=False,
                clock=clock,
            )
            log.begin("COM4", "hello", 15)
            clock.t = 61.0
            log.append_event("COM4", "first")
            clock.t = 62.0
            log.append_event("COM4", "second")
            take = log._take
            assert take is not None
            with log._lock:
                log._flush_locked(take)
            first = (take.directory / "events" / "part-000.log").read_text(encoding="utf-8")
            second = (take.directory / "events" / "part-001.log").read_text(encoding="utf-8")
            self.assertIn("first", first)
            self.assertNotIn("second", first)
            self.assertIn("second", second)
            self.assertTrue((archive / take.relative / "events" / "part-000.log").is_file())
            self.assertFalse((archive / take.relative / "events" / "part-001.log").exists())
            log.end("COM4", "USB 切断")
            self.assertTrue((archive / take.relative / "events" / "part-001.log").is_file())

    def test_day_index_increments_and_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            log = logmod.ExperimentLog(logmod.StoragePaths(root, None), copy_async=False)
            try:
                self.assertTrue(log.begin("COM4", "hello", 15).ok)
                assert log._take is not None
                first = log._take.directory
                self.assertRegex(first.name, r"^001_\d{6}$")
                log.end("COM4", "USB 切断")
                self.assertTrue(log.begin("COM4", "hello", 15).ok)
                assert log._take is not None
                second = log._take.directory
                self.assertRegex(second.name, r"^002_\d{6}$")
                log.end("COM4", "USB 切断")
                # フォルダを消しても、発行済みの 002 は戻らない。
                shutil.rmtree(second)
                self.assertTrue(log.begin("COM4", "hello", 15).ok)
                assert log._take is not None
                self.assertRegex(log._take.directory.name, r"^003_\d{6}$")
                self.assertEqual(log._take.meta["day_index"], 3)
            finally:
                log.end("COM4", "test")

    def test_legacy_folder_counts_as_a_taken_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            now = datetime.now().astimezone()
            legacy = (
                root
                / f"{now.year:04d}"
                / f"{now.month:02d}"
                / f"{now.day:02d}"
                / now.strftime("%H%M%S")
            )
            legacy.mkdir(parents=True)
            log = logmod.ExperimentLog(logmod.StoragePaths(root, None), copy_async=False)
            try:
                self.assertTrue(log.begin("COM4", "hello", 15).ok)
                assert log._take is not None
                self.assertRegex(log._take.directory.name, r"^002_\d{6}$")
                self.assertEqual(log._take.meta["day_index"], 2)
                self.assertTrue(legacy.is_dir())
            finally:
                log.end("COM4", "test")

    def test_nas_index_is_continued(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            archive = Path(tmp) / "nas"
            now = datetime.now().astimezone()
            kept = (
                archive
                / f"{now.year:04d}"
                / f"{now.month:02d}"
                / f"{now.day:02d}"
                / "004_120000"
            )
            kept.mkdir(parents=True)
            log = logmod.ExperimentLog(logmod.StoragePaths(root, archive), copy_async=False)
            try:
                self.assertTrue(log.begin("COM4", "hello", 15).ok)
                assert log._take is not None
                self.assertRegex(log._take.directory.name, r"^005_\d{6}$")
                self.assertEqual(log._take.meta["day_index"], 5)
            finally:
                log.end("COM4", "test")

    def test_copy_failure_keeps_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            blocker = Path(tmp) / "not-dir"
            blocker.write_text("x", encoding="utf-8")
            log = logmod.ExperimentLog(
                logmod.StoragePaths(root, blocker / "nas"),
                copy_async=False,
            )
            log.begin("COM4", "hello", 15)
            log.append_event("COM4", "残す")
            log.end("COM4", "USB 切断")
            pending = list(root.rglob("*.pending"))
            self.assertTrue(pending)

    def test_interrupted_take_is_copied_on_next_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ssd"
            archive = Path(tmp) / "nas"
            take = root / "2026" / "10" / "26" / "090312"
            part = take / "sensors" / "part-000.jsonl"
            part.parent.mkdir(parents=True)
            part.write_text('{"seq":1}\n', encoding="utf-8")
            meta = {
                "format_id": "core_take_v1",
                "take_id": "090312",
                "recording": True,
                "sample_count": 1,
                "open_parts": ["sensors/part-000.jsonl"],
                "started_unix": 1.0,
            }
            (take / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            logmod.ExperimentLog(logmod.StoragePaths(root, archive), copy_async=False)
            saved = json.loads((take / "meta.json").read_text(encoding="utf-8"))
            self.assertFalse(saved["recording"])
            self.assertEqual(saved["stop_reason"], "中断")
            self.assertTrue((archive / "2026" / "10" / "26" / "090312" / "sensors" / "part-000.jsonl").is_file())
            self.assertEqual(list(root.rglob("*.pending")), [])

    def test_without_config_does_not_start(self) -> None:
        log = logmod.ExperimentLog(None, copy_async=False)
        got = log.begin("COM4", "hello", 15)
        self.assertEqual(got.reason, "no_config")


class TxRecordTest(unittest.TestCase):
    def test_joint_keeps_channel_and_degrees(self) -> None:
        rec = proto.tx_record(proto.cmd_joint(3, 90.0))
        self.assertEqual(rec["text"], "CMD")
        self.assertEqual(rec["ch"], 3)
        self.assertEqual(rec["deg"], 90.0)

    def test_mode_and_output(self) -> None:
        mode = proto.tx_record(proto.cmd_mode(True))
        out = proto.tx_record(proto.cmd_out(None, False))
        self.assertEqual(mode["mode"], "robot")
        self.assertEqual(out["ch"], 0xFF)
        self.assertEqual(out["on"], False)


if __name__ == "__main__":
    unittest.main()
