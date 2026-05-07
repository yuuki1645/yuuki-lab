from __future__ import annotations
import json
from typing import Any, Dict, Optional
import threading
import time

class StateManager:
    """状態管理クラス"""

    def __init__(self, state_path: str = "./state.json", idle_save_delay: float = 0.5):
        self.state_path = state_path
        self._state: Dict[str, Any] = {}
        self._lock = threading.Lock()  # スレッドセーフのためのロック
        self._last_update_time: float = 0.0
        self._idle_save_delay = idle_save_delay # 操作停止検知の待機時間（秒）
        self._save_timer: Optional[threading.Timer] = None

        # 起動時にファイルから読み込む
        self._load_from_file()

    def _load_from_file(self) -> None:
        """ファイルから直接読み込む（キャッシュを使わない）"""
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                self._state = json.load(f)
        except FileNotFoundError:
            self._state = {}
        except json.JSONDecodeError:
            self._state = {}

    def _save_to_file(self) -> None:
        """ファイルに状態を保存する"""
        with self._lock:
            state_to_save = self._state.copy()

        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(state_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[WARN] failed to save state: {e}")

    def _schedule_idle_save(self) -> None:
        """操作が止まったら保存するようにスケジュールする"""
        # 既存のタイマーをキャンセル
        if self._save_timer is not None:
            self._save_timer.cancel()
        
        # 新しいタイマーを設定
        self._save_timer = threading.Timer(self._idle_save_delay, self._save_to_file)
        self._save_timer.daemon = True
        self._save_timer.start()

    def set(self, key: str, value: Any) -> None:
        """状態を設定する（操作停止検知による自動保存をスケジュール）"""
        with self._lock:
            self._state[key] = value
            self._last_update_time = time.time()

        # 操作が止まったら保存するようにスケジュール
        self._schedule_idle_save()

    def get_all(self) -> Dict[str, Any]:
        """全ての状態を取得する（常に最新の状態を返す）"""
        with self._lock:
            return self._state.copy()

    def flush(self) -> None:
        """明示的に保存する（タイマーをキャンセルして即座に保存）"""
        if self._save_timer is not None:
            self._save_timer.cancel()
            self._save_timer = None
        self._save_to_file()