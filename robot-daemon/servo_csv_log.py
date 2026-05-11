# type: ignore

"""サーボ指令をメモリに溜め、一定間隔で CSV に追記する（IMU CSV と別ファイル）。"""

from __future__ import annotations

import csv
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)

SERVO_CSV_COLUMNS = [
    "wall_unix",
    "endpoint",
    "mode",
    "ch",
    "angle_in",
    "logical_deg",
    "physical_deg",
    "extra_json",
]


class ServoCsvLog:
    """バッファリング後に CSV へ追記。スレッドセーフ。"""

    def __init__(self, *, log_dir: Path | None) -> None:
        self._log_dir = log_dir
        self._lock = threading.Lock()
        self._buffer: list[list[Any]] = []
        self._file_path: Path | None = None
        self._header_written = False

    @property
    def enabled(self) -> bool:
        return self._log_dir is not None

    def is_recording(self) -> bool:
        with self._lock:
            return self._file_path is not None

    def begin_session(self) -> None:
        self.flush()
        if not self.enabled:
            return
        with self._lock:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            name = time.strftime("servo_%Y%m%d_%H%M%S.csv")
            self._file_path = self._log_dir / name
            self._header_written = False
        # IMU と違い指令は疎なので、開始時点でヘッダだけ書いてファイルを必ず作る
        self._write_csv_header_if_new_file()

    def end_session(self) -> None:
        self.flush()
        with self._lock:
            self._file_path = None
            self._header_written = False

    def record_set(
        self,
        *,
        mode: str,
        ch: int,
        angle_in: float,
        logical_deg: float,
        physical_deg: float,
    ) -> None:
        self._record_row(
            [
                time.time(),
                "set",
                mode,
                ch,
                angle_in,
                logical_deg,
                physical_deg,
                "",
            ]
        )

    def record_set_multiple(
        self,
        *,
        mode: str,
        angles_dict: dict[int, float],
        results: dict[str, Any],
    ) -> None:
        extra = json.dumps(
            {
                "angles": {str(k): v for k, v in angles_dict.items()},
                "results": results,
            },
            ensure_ascii=False,
        )
        self._record_row(
            [time.time(), "set_multiple", mode, -1, "", "", "", extra]
        )

    def record_transition(
        self,
        *,
        mode: str,
        angles_dict: dict[int, float],
        duration_sec: float,
    ) -> None:
        extra = json.dumps(
            {
                "angles": {str(k): v for k, v in angles_dict.items()},
                "duration_sec": duration_sec,
            },
            ensure_ascii=False,
        )
        self._record_row(
            [time.time(), "transition", mode, -1, "", "", "", extra]
        )

    def _record_row(self, row: list[Any]) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._file_path is None:
                return
            self._buffer.append(row)
        # 指令は Hz が低いので毎回 flush（バッチ間隔で気づかず「書かれない」と見えるのを防ぐ）
        self.flush()

    def flush(self) -> None:
        rows_to_write: list[list[Any]] | None = None
        with self._lock:
            if self._buffer:
                rows_to_write = self._buffer
                self._buffer = []
        if rows_to_write:
            self._append_rows_unlocked(rows_to_write)

    def _write_csv_header_if_new_file(self) -> None:
        """セッション開始直後に空ファイル＋ヘッダだけ出力する。"""
        need_header = False
        path: Path | None = None
        with self._lock:
            path = self._file_path
            if path is None:
                return
            if self._header_written:
                return
            self._header_written = True
            need_header = True
        if not need_header or path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(SERVO_CSV_COLUMNS)
        except OSError as e:
            _LOG.warning("サーボ CSV ヘッダ書き込みに失敗しました: %s", e)
            with self._lock:
                self._header_written = False

    def _append_rows_unlocked(self, rows: list[list[Any]]) -> None:
        if not rows:
            return
        with self._lock:
            path = self._file_path
            if path is None:
                return
            need_header = not self._header_written
            if need_header:
                self._header_written = True
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if need_header:
                    w.writerow(SERVO_CSV_COLUMNS)
                w.writerows(rows)
        except OSError as e:
            _LOG.warning("サーボ CSV 書き込みに失敗しました: %s", e)


def servo_csv_log_from_env() -> ServoCsvLog:
    """
    環境変数から ``ServoCsvLog`` を構築する。

    IMU CSV と同じトグル・ディレクトリを使う（別ファイル名 ``servo_*.csv``）。

    - ``IMU_LOG_DISABLE`` … 1/true/on なら ``log_dir=None``
    - ``IMU_LOG_DIR`` … 出力ディレクトリ（未設定または空なら ``./imu_logs``）

    サーボ CSV は指令のたびにディスクへ flush します（``IMU_LOG_FLUSH_SEC`` は IMU 用のみ）。
    """
    val = os.environ.get("IMU_LOG_DISABLE", "").lower()
    if val in ("1", "true", "yes", "on"):
        return ServoCsvLog(log_dir=None)

    raw_dir = os.environ.get("IMU_LOG_DIR", "./imu_logs").strip()
    if not raw_dir:
        return ServoCsvLog(log_dir=None)

    return ServoCsvLog(log_dir=Path(raw_dir).resolve())
