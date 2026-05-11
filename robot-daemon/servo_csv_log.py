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

    def __init__(
        self,
        *,
        log_dir: Path | None,
        flush_interval_sec: float = 10.0,
    ) -> None:
        self._log_dir = log_dir
        self._flush_interval_sec = max(0.5, float(flush_interval_sec))
        self._lock = threading.Lock()
        self._buffer: list[list[Any]] = []
        self._file_path: Path | None = None
        self._header_written = False
        self._last_flush_monotonic = 0.0

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
            self._last_flush_monotonic = time.monotonic()

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
        rows_to_write: list[list[Any]] | None = None
        with self._lock:
            if self._file_path is None:
                return
            self._buffer.append(row)
            now = time.monotonic()
            if now - self._last_flush_monotonic >= self._flush_interval_sec:
                rows_to_write = self._buffer
                self._buffer = []
                self._last_flush_monotonic = now
        if rows_to_write:
            self._append_rows_unlocked(rows_to_write)

    def flush(self) -> None:
        rows_to_write: list[list[Any]] | None = None
        with self._lock:
            if self._buffer:
                rows_to_write = self._buffer
                self._buffer = []
        if rows_to_write:
            self._append_rows_unlocked(rows_to_write)

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
    - ``IMU_LOG_FLUSH_SEC`` … フラッシュ間隔（秒、既定 10）
    """
    val = os.environ.get("IMU_LOG_DISABLE", "").lower()
    if val in ("1", "true", "yes", "on"):
        return ServoCsvLog(log_dir=None)

    raw_dir = os.environ.get("IMU_LOG_DIR", "./imu_logs").strip()
    if not raw_dir:
        return ServoCsvLog(log_dir=None)

    flush_raw = os.environ.get("IMU_LOG_FLUSH_SEC", "10").strip()
    try:
        flush_sec = float(flush_raw) if flush_raw else 10.0
    except ValueError:
        flush_sec = 10.0

    return ServoCsvLog(log_dir=Path(raw_dir).resolve(), flush_interval_sec=flush_sec)
