"""
lab_debug の Tk GUI（ライブラリ。直接起動しない）。

起動は tools/lab_debug.py。タブ・接続・tick は本ファイルの LabApp。
USB 操作は apply_op() に集約する（PC ボタンと iPad が同じ入口）。

Tk 画面は非推奨。操作と今後の UI 改善は robotics-hub の
実機テレメトリ（M5）（/m5-telemetry）。USB 中継のため本プロセスは必要。
"""

from __future__ import annotations

import random
import time
import webbrowser
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import serial.tools.list_ports

from . import cop_ankle_ctrl as copctrl
from . import rt_usb_proto as proto
from .cal_map_io import load_map, save_map
from .lab_const import (
    AMP_COLOR,
    AS_COLOR,
    BAD,
    BG,
    CAL_FIRST_MOVE_S,
    CAL_FRAME_WAIT_S,
    CAL_MAX_DEG,
    CAL_MIN_DEG,
    CAL_MIN_MAP_POINTS,
    CAL_SETTLE_S,
    CARD,
    CARD_HI,
    CMD_COLOR,
    CORR_COLOR,
    FLASH,
    GOOD,
    INA_CHS,
    INA_PLOT_COLORS,
    JOINT_PANELS,
    JOINTS,
    MAG_LABEL,
    METRIC_VALUE_CHARS,
    MONO,
    MONO_LG,
    MONO_MD,
    MUTED,
    PERIOD_COLOR,
    PLOT_INTERVAL_S,
    RAND_HOLD_MAX_S,
    RAND_HOLD_MIN_S,
    RAND_MAX_DEG,
    RAND_MIN_DEG,
    RAND_MIN_JUMP_DEG,
    TARGET_MS,
    TEXT,
    UNWRAP_COLOR,
    VOLT_COLOR,
    WATT_COLOR,
    WARN,
    at,
    fmt,
    fmt_ms,
    mag_color,
)
from .lab_model import (
    FootRoute,
    Frame,
    JointRoute,
    ScanNode,
    default_foot,
    default_routes,
    foot_sample_dict,
    foot_tuple,
    ina_label,
    parse_ina_label,
    route_sig,
    route_tuple,
    scan_node_path,
)
from .lab_pc_cal import (
    PcCalSweep,
    build_cal_map_points,
    cal_sweep_cmds,
    clamp_cal_deg,
)
from .lab_plot import LinePlot
from .lab_usb import (
    AtomSession,
    first_atom_port,
    is_atom_hwid,
    list_ports,
    load_names,
    save_names,
)
from .m5_hub_bridge import (
    EVT_CAL,
    EVT_CONTROL,
    EVT_EVENTS,
    EVT_FRAME,
    EVT_NVS,
    EVT_PROFILE,
    EVT_RECORD,
    EVT_SCAN,
    EVT_STATUS,
    M5HubBridge,
    lan_ipv4,
)
from .m5_record_store import M5RecordStore


def _value_label(parent: tk.Misc, fg: str, font: tuple = MONO, *, anchor: str = "e") -> tk.Label:
    """頻繁更新する数値用。等幅＋固定幅で桁位置とパネル幅を固定する。"""
    return tk.Label(
        parent,
        text="—",
        bg=CARD,
        fg=fg,
        font=font,
        width=METRIC_VALUE_CHARS,
        anchor=anchor,
    )


class LabApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        # Tk 画面は非推奨。操作・改善の本線は robotics-hub の Web UI。
        self.title("yuuki-lab  総合デバッグ（非推奨）")
        self.configure(bg=BG)
        self.geometry("1280x820")
        self.minsize(960, 640)

        self.names = load_names()
        self.sessions: dict[str, AtomSession] = {}
        self.current: str | None = None
        # 先頭 ATOM への自動接続は一度だけ。手動切断後は再開しない
        self._auto_connect_done = False
        self._ports_raw: list[str] = []
        self._last_plot = 0.0
        self._amp_limit = tk.DoubleVar(value=8.0)
        self._auto_scan = tk.BooleanVar(value=False)
        self._scan_job: str | None = None
        self._syncing = False
        self._tree_sig: object = None
        self._evt_sig: object = None
        self._plot_port: str | None = None
        self._last_cmd_t = [0.0] * JOINTS
        self._last_out_reassert = 0.0
        self._last_plot_seq: tuple | None = None
        self._rand_until = [0.0] * JOINTS
        self._rand_target = [135.0] * JOINTS
        # iPad が1台でも繋がったら PC のロボット操作をロックする
        self._ipad_clients = 0
        self._robot_ctrl: list[tuple[tk.Misc, str]] = []
        self._m5_last_seq: tuple | None = None
        self._m5_evt_sig: object = None
        self._m5_scan_sig: object = None
        self._m5_prof_sig: object = None
        self._m5_cal_sig: object = None
        self._m5_nvs_sig: object = None
        self._m5_st_sig: object = None
        # iPad コマンド処理中は PC 操作ガードを外す（同じハンドラを再利用するため）
        self._from_ipad = False
        # 本記録は ATOM 接続 PC のディスク。明示開始まで書かない。
        self._record_store = M5RecordStore()
        self._record_pub_t = 0.0
        # かかとピッチ COP 中心化（PC 閉ループ。再起動で消える）
        self._cop = copctrl.CopCtrl()
        # PC 側サーボ校正（40〜230° PWM）。実行中だけ入る
        self._pc_cal: PcCalSweep | None = None
        self._m5_bridge = M5HubBridge(
            on_command=self._m5_cmd_from_thread,
            on_clients_changed=self._m5_clients_from_thread,
            store=self._record_store,
        )

        self._build()
        self._m5_bridge.set_snapshot(self._m5_snapshot)
        self._m5_bridge.start()
        if self._m5_bridge.enabled:
            local_url, lan_url = self._web_ui_urls()
            print(f"Web UI（推奨）: {local_url}    iPad: {lan_url}  （USB はこのプロセス / ブリッジ :8794）")
        else:
            print("iPad ブリッジ無効。pip install -r tools/requirements.txt")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._tick)
        # ポート列挙後に 1 台目 ATOM へ自動接続する
        self.after(200, self._refresh_ports)

    def _build(self) -> None:
        top = tk.Frame(self, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text="総合デバッグ", bg=CARD, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(
            side="left", padx=12, pady=8
        )
        tk.Label(
            top,
            text="机上: Lab（PWM オフ）  機体: Robot  |  1台目の ATOM に自動接続",
            bg=CARD,
            fg=MUTED,
        ).pack(side="left", padx=8)
        tk.Button(top, text="全停止", command=self._hold_all, bg=BAD, fg=TEXT, relief="flat").pack(
            side="right", padx=8, pady=6
        )
        tk.Button(top, text="全接続", command=self._connect_all, bg=CARD_HI, fg=TEXT, relief="flat").pack(
            side="right", padx=4, pady=6
        )
        tk.Button(top, text="更新", command=self._refresh_ports, bg=CARD_HI, fg=TEXT, relief="flat").pack(
            side="right", padx=4, pady=6
        )
        self._ipad_banner = tk.Label(
            top, text="iPad 未接続  ブリッジ :8794", bg=CARD, fg=MUTED, anchor="e"
        )
        self._ipad_banner.pack(side="right", padx=12)

        # 機能は残すが、今後の UI 改善は Hub（ブラウザ / iPad）側。常に見える誘導。
        self._web_nudge = tk.Frame(self, bg="#3d2e12")
        self._web_nudge.pack(fill="x")
        local_url, lan_url = self._web_ui_urls()
        nudge_text = (
            "この Python GUI は非推奨です。操作と今後の改善は Web UI を使ってください"
            "（機能はまだ使えます）。  "
            f"PC  {local_url}    iPad  {lan_url}    "
            "Hub 未起動なら robotics-hub で  npm run dev:m5"
        )
        self._web_nudge_lbl = tk.Label(
            self._web_nudge,
            text=nudge_text,
            bg="#3d2e12",
            fg=WARN,
            font=("Segoe UI", 10),
            wraplength=1100,
            justify="left",
            anchor="w",
        )
        self._web_nudge_lbl.pack(side="left", fill="x", expand=True, padx=12, pady=6)
        self._web_nudge.bind("<Configure>", self._on_web_nudge_resize)
        tk.Button(
            self._web_nudge,
            text="Web UI を開く",
            command=self._open_web_ui,
            bg=WARN,
            fg=BG,
            relief="flat",
            font=("Segoe UI Semibold", 10),
        ).pack(side="right", padx=10, pady=4)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        left = tk.Frame(body, bg=BG, width=280)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="ATOM（USB）", bg=BG, fg=MUTED).pack(anchor="w")
        self.port_list = tk.Listbox(
            left, bg=CARD, fg=TEXT, selectbackground=CARD_HI, relief="flat",
            font=("Segoe UI", 10), height=8,
        )
        self.port_list.pack(fill="x", pady=(0, 6))
        self.port_list.bind("<<ListboxSelect>>", self._on_select_port)

        name_row = tk.Frame(left, bg=BG)
        name_row.pack(fill="x", pady=2)
        tk.Label(name_row, text="名前", bg=BG, fg=MUTED).pack(side="left")
        self.name_var = tk.StringVar()
        tk.Entry(name_row, textvariable=self.name_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat").pack(
            side="left", fill="x", expand=True, padx=6
        )
        tk.Button(name_row, text="保存", command=self._save_name, bg=CARD_HI, fg=TEXT, relief="flat").pack(side="right")

        btn_row = tk.Frame(left, bg=BG)
        btn_row.pack(fill="x", pady=6)
        tk.Button(btn_row, text="接続", command=self._connect_sel, bg=GOOD, fg=TEXT, relief="flat").pack(
            side="left", expand=True, fill="x", padx=(0, 3)
        )
        tk.Button(btn_row, text="切断", command=self._disconnect_sel, bg=CARD_HI, fg=TEXT, relief="flat").pack(
            side="left", expand=True, fill="x", padx=3
        )
        self.identify_btn = tk.Button(
            btn_row, text="Identify", command=self._identify, bg=FLASH, fg=BG, relief="flat"
        )
        self.identify_btn.pack(side="left", expand=True, fill="x", padx=(3, 0))
        # USB 接続／切断は iPad 接続中も PC 側に残す（COM は PC 専有）

        self.card_host = tk.Frame(left, bg=BG)
        self.card_host.pack(fill="both", expand=True, pady=(8, 0))

        right = tk.Frame(body, bg=BG)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        bar = tk.Frame(right, bg=CARD)
        bar.pack(fill="x")
        self.sel_label = tk.Label(bar, text="未選択", bg=CARD, fg=TEXT, font=("Segoe UI Semibold", 12))
        self.sel_label.pack(side="left", padx=10, pady=6)
        self.hello_label = tk.Label(bar, text="", bg=CARD, fg=MUTED)
        self.hello_label.pack(side="left")
        tk.Label(bar, text="モード", bg=CARD, fg=MUTED).pack(side="left", padx=(16, 4))
        self.mode_var = tk.StringVar(value="lab")
        self.mode_combo = ttk.Combobox(
            bar, textvariable=self.mode_var, values=("lab", "robot"), width=8, state="readonly"
        )
        self.mode_combo.pack(side="left")
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode)
        self.auto_scan_cb = tk.Checkbutton(
            bar, text="自動スキャン 5s", variable=self._auto_scan, command=self._toggle_auto,
            bg=CARD, fg=TEXT, selectcolor=CARD_HI, activebackground=CARD, activeforeground=TEXT,
        )
        self.auto_scan_cb.pack(side="left", padx=10)
        self.scan_btn = tk.Button(bar, text="スキャン", command=self._scan, bg=CARD_HI, fg=TEXT, relief="flat")
        self.scan_btn.pack(side="right", padx=8, pady=4)

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True, pady=(6, 0))
        self.tab_topo = tk.Frame(nb, bg=BG)
        self.tab_prof = tk.Frame(nb, bg=BG)
        self.tab_joint = tk.Frame(nb, bg=BG)
        self.tab_cal = tk.Frame(nb, bg=BG)
        self.tab_pwr = tk.Frame(nb, bg=BG)
        self.tab_time = tk.Frame(nb, bg=BG)
        self.tab_evt = tk.Frame(nb, bg=BG)
        nb.add(self.tab_topo, text=" トポロジ ")
        nb.add(self.tab_prof, text=" 関節プロファイル ")
        nb.add(self.tab_joint, text=" 関節 / 試験 ")
        nb.add(self.tab_cal, text=" 校正 ")
        nb.add(self.tab_pwr, text=" 電源 ")
        nb.add(self.tab_time, text=" 周期 ")
        nb.add(self.tab_evt, text=" イベント / 記録 ")

        self._build_topo()
        self._build_prof()
        self._build_joint()
        self._build_cal()
        self._build_pwr()
        self._build_time()
        self._build_evt()
        self._register_robot_controls()

    def _web_ui_urls(self) -> tuple[str, str]:
        """Hub 実機テレメトリ（M5）の PC 用と LAN 用 URL。"""
        local = "http://127.0.0.1:5173/m5-telemetry"
        lan = lan_ipv4()
        remote = (
            f"http://{lan}:5173/m5-telemetry"
            if lan
            else "http://<PCのLAN IP>:5173/m5-telemetry"
        )
        return local, remote

    def _open_web_ui(self) -> None:
        """既定ブラウザで Web UI を開く。Hub 未起動ならページは繋がらない。"""
        local, _ = self._web_ui_urls()
        webbrowser.open(local)

    def _on_web_nudge_resize(self, ev: tk.Event) -> None:
        """誘導バーの幅に合わせて文言を折り返す。"""
        self._web_nudge_lbl.configure(wraplength=max(400, ev.width - 140))

    def _add_robot_ctrl(self, w: tk.Misc, enabled: str = "normal") -> None:
        """iPad 接続時に無効化するウィジェット。"""
        self._robot_ctrl.append((w, enabled))

    def _register_robot_controls(self) -> None:
        """iPad 接続中に無効化するロボット操作。全停止・USB 接続は対象外。"""
        self._add_robot_ctrl(self.mode_combo, "readonly")
        self._add_robot_ctrl(self.auto_scan_cb)
        self._add_robot_ctrl(self.scan_btn)
        self._add_robot_ctrl(self.identify_btn)
        for w in self.panel_out_cb + self.panel_rand_cb:
            self._add_robot_ctrl(w)
        for w in self.panel_cmd_scale:
            self._add_robot_ctrl(w)
        for w in self.ina_combos:
            self._add_robot_ctrl(w, "readonly")
        for w in getattr(self, "topo_lock_btns", []):
            self._add_robot_ctrl(w)
        if getattr(self, "topo_ina_spin", None) is not None:
            self._add_robot_ctrl(self.topo_ina_spin)
        for w in getattr(self, "prof_lock_btns", []):
            self._add_robot_ctrl(w)
        for w in getattr(self, "prof_entries", []):
            self._add_robot_ctrl(w)
        for w in getattr(self, "cal_lock_btns", []):
            self._add_robot_ctrl(w)
        if getattr(self, "cal_ch_spin", None) is not None:
            self._add_robot_ctrl(self.cal_ch_spin)
        if getattr(self, "amp_entry", None) is not None:
            self._add_robot_ctrl(self.amp_entry)
        for w in getattr(self, "rand_entries", []):
            self._add_robot_ctrl(w)

    def _pc_locked(self) -> bool:
        """iPad が操作権を持っている（iPad 由来の処理中はロックしない）。"""
        if self._from_ipad:
            return False
        return self._ipad_clients > 0

    def _apply_pc_lock_ui(self) -> None:
        """バナーとウィジェット状態。クライアント数で判定（コマンド処理中フラグは見ない）。"""
        locked = self._ipad_clients > 0
        for w, en in self._robot_ctrl:
            try:
                w.configure(state="disabled" if locked else en)
            except tk.TclError:
                pass
        if locked:
            self._ipad_banner.configure(
                text=f"iPad 操作中（{self._ipad_clients}） PC は表示のみ / 全停止のみ",
                fg=WARN,
            )
        else:
            self._ipad_banner.configure(text="iPad 未接続  ブリッジ :8794", fg=MUTED)

    def _m5_clients_from_thread(self, n: int) -> None:
        self.after(0, lambda: self._on_ipad_clients(n))

    def _m5_cmd_from_thread(self, msg: dict) -> None:
        self.after(0, lambda m=dict(msg): self._m5_handle_cmd(m))

    def _on_ipad_clients(self, n: int) -> None:
        prev = self._ipad_clients
        self._ipad_clients = n
        self._apply_pc_lock_ui()
        if n > 0 and prev == 0:
            s = self._m5_sess()
            if s:
                s.note("iPad が操作を開始（PC は表示のみ）")
        if n == 0 and prev > 0:
            s = self._m5_sess()
            if s:
                s.note("iPad 切断。PC 操作を再開")
        self._m5_publish_status()
        self._m5_publish_control()

    def _m5_sess(self) -> AtomSession | None:
        """当面 1 台。選択中が無ければ最初の接続を使う。"""
        s = self._sess()
        if s is not None and s.connected:
            return s
        for x in self.sessions.values():
            if x.connected:
                return x
        return None

    def _m5_snapshot(self) -> dict:
        return {
            "status": self._m5_status_dict(),
            "control": self._m5_control_dict(),
            "frame": self._m5_frame_dict(),
            "scan": self._m5_scan_dict(),
            "profile": self._m5_profile_dict(),
            "events": self._m5_events_list(),
            "cal": self._m5_cal_dict(),
            "nvs": self._m5_nvs_dict(),
            "record": self._record_store.status(),
        }

    def _m5_status_dict(self) -> dict:
        s = self._m5_sess()
        return {
            "ipad_clients": self._ipad_clients,
            "pc_locked": self._ipad_clients > 0,
            "connected": bool(s and s.connected),
            "port": s.port if s else "",
            "name": (s.name or s.port) if s else "",
            "hello": s.hello if s else "",
            "mode": s.mode if s else self.mode_var.get(),
            "bridge_port": 8794,
        }

    def _m5_control_dict(self) -> dict:
        try:
            amp = float(self._amp_limit.get())
        except (tk.TclError, ValueError):
            amp = 8.0
        lo, hi, h0, h1, jump = self._rand_settings()
        return {
            "out": [bool(v.get()) for v in self.out_vars],
            "cmd": [float(v.get()) for v in self.cmd_vars],
            "rand": [bool(v.get()) for v in self.rand_vars],
            "amp_limit": amp,
            "auto_scan": bool(self._auto_scan.get()),
            "rand_min": lo,
            "rand_max": hi,
            "rand_hold_min": h0,
            "rand_hold_max": h1,
            "rand_jump": jump,
            "cop": self._cop.to_dict(),
        }

    def _m5_frame_dict(self) -> dict | None:
        s = self._m5_sess()
        f = s.last_frame if s else None
        if f is None:
            return None
        return {
            "t": f.t,
            "seq": f.seq,
            "period_us": f.period_us,
            "loop_us": f.loop_us,
            "sense_us": f.sense_us,
            "jitter_us": f.jitter_us,
            "overrun": f.overrun,
            "cmd": list(f.cmd),
            "raw": list(f.raw),
            "unwrap": list(f.unwrap),
            "corr": list(f.corr),
            "as_ok": list(f.as_ok),
            "mag": list(f.mag),
            "agc": list(f.agc),
            "volt": list(f.volt),
            "amp": list(f.amp),
            "watt": list(f.watt),
            "ina_ok": list(f.ina_ok),
            "i2c_err": f.i2c_err,
            "servo_ok": f.servo_ok,
            "mode": f.mode,
            "out_mask": f.out_mask,
            "map_ok": list(f.map_ok),
            "foot": foot_sample_dict(f),
        }

    def _m5_scan_dict(self) -> dict:
        s = self._m5_sess()
        nodes = []
        if s:
            for n in s.nodes:
                nodes.append(
                    {
                        "hub": n.hub,
                        "ch": n.ch,
                        "addr": n.addr,
                        "kind": n.kind,
                        "mag": n.mag,
                        "agc": n.agc,
                    }
                )
        return {"nodes": nodes}

    def _m5_profile_dict(self) -> dict:
        s = self._m5_sess()
        routes = s.routes if s else default_routes()
        out = []
        for r in routes[:JOINTS]:
            out.append(
                {
                    "enc_hub": r.enc_hub,
                    "enc_ch": r.enc_ch,
                    "enc_addr": r.enc_addr,
                    "act_hub": r.act_hub,
                    "act_ch": r.act_ch,
                    "act_addr": r.act_addr,
                    "servo_ch": r.servo_ch,
                    "ina_hub": r.ina_hub,
                    "ina_ch": r.ina_ch,
                    "ina_addr": r.ina_addr,
                }
            )
        return {
            "routes": out,
            "ina_options": self._ina_option_list(s) if s else ["なし"],
            "foot": {
                "hub": s.foot.hub if s else default_foot().hub,
                "ch": s.foot.ch if s else default_foot().ch,
                "addr": s.foot.addr if s else default_foot().addr,
            },
            "foot_options": self._foot_option_list(s) if s else ["なし"],
        }

    def _m5_events_list(self) -> list[str]:
        s = self._m5_sess()
        if not s:
            return []
        return list(s.events)

    def _m5_cal_dict(self) -> dict:
        s = self._m5_sess()
        if not s:
            return {"status": "", "map_ch": 0, "map_count": 0}
        return {
            "status": s.cal_status,
            "map_ch": s.map_ch,
            "map_count": len(s.map_points),
        }

    def _m5_nvs_dict(self) -> dict:
        """フラッシュ NVS のキー一覧。未取得なら ok=false。"""
        s = self._m5_sess()
        if not s:
            return {"ok": False, "entries": [], "bytes": 0}
        return {
            "ok": bool(s.nvs_ok),
            "entries": list(s.nvs_entries),
            "bytes": int(s.nvs_bytes),
        }

    def _m5_publish_status(self) -> None:
        self._m5_bridge.publish(EVT_STATUS, self._m5_status_dict())

    def _m5_publish_control(self) -> None:
        self._m5_bridge.publish(EVT_CONTROL, self._m5_control_dict())

    def _m5_publish_record(self) -> None:
        """記録状態を Hub へ。開始・停止・追記中の経過。"""
        self._m5_bridge.publish(EVT_RECORD, self._record_store.status())

    def _record_start(self, name: str = "", notes: str = "") -> dict:
        """明示開始。ATOM が無いときは始めない。"""
        if self._record_store.is_recording():
            return {**self._record_store.status(), "ok": True, "already": True}
        s = self._m5_sess()
        if s is None or not s.connected:
            err = {"ok": False, "error": "ATOM が未接続です", "recording": False, "id": None, "name": "", "sample_count": 0, "elapsed_sec": 0.0}
            self._m5_bridge.publish(EVT_RECORD, err)
            return err
        meta = self._record_store.start(
            name=name,
            notes=notes,
            port=s.port,
            atom_name=s.name or s.port,
            mode=s.mode,
            hello=s.hello,
            profile=self._m5_profile_dict(),
            scan=self._m5_scan_dict(),
            control=self._m5_control_dict(),
        )
        s.note(f"本記録開始  {meta.get('name')}  ({meta.get('id')})")
        self._record_pub_t = 0.0
        self._m5_publish_record()
        self._refresh_record_ui()
        return meta

    def _record_stop(self, reason: str = "") -> dict:
        """明示停止、または切断時のクローズ。"""
        if not self._record_store.is_recording():
            return {"ok": True, "recording": False}
        out = self._record_store.stop(reason=reason)
        s = self._m5_sess()
        if s:
            n = out.get("sample_count", 0)
            s.note(f"本記録停止  {n}点  {reason}".rstrip())
        self._m5_publish_record()
        self._refresh_record_ui()
        return out

    def _refresh_record_ui(self) -> None:
        """PC のイベントタブ表示。"""
        lab = getattr(self, "log_state", None)
        if lab is None:
            return
        st = self._record_store.status()
        if st.get("recording"):
            lab.configure(
                text=f"記録中  {st.get('name')}  {int(st.get('sample_count') or 0)}点",
                fg=GOOD,
            )
        else:
            lab.configure(text="記録オフ（Hub からも開始可）", fg=MUTED)

    def _m5_publish_tick(self) -> None:
        """Tk 周期で iPad へ最新を流す。重い SCAN/PROFILE/CAL は変化時だけ。"""
        s = self._m5_sess()
        # 記録中に ATOM が消えたらファイルを閉じる
        if self._record_store.is_recording() and (s is None or not s.connected):
            self._record_stop(reason="ATOM 切断")
        if not self._m5_bridge.enabled:
            if self._record_store.is_recording():
                frame = self._m5_frame_dict()
                if frame:
                    self._record_store.append(frame)
            return
        f = s.last_frame if s else None
        seq = (s.port, f.seq) if s and f else None
        if seq != self._m5_last_seq:
            self._m5_last_seq = seq
            frame = self._m5_frame_dict()
            self._m5_bridge.publish(EVT_FRAME, frame)
            self._m5_bridge.publish(EVT_CONTROL, self._m5_control_dict())
            if frame and self._record_store.is_recording():
                self._record_store.append(frame)
        if self._record_store.is_recording():
            now = time.time()
            if now - self._record_pub_t >= 0.5:
                self._record_pub_t = now
                self._m5_publish_record()
                self._refresh_record_ui()
        st_sig = (
            s.port if s else "",
            bool(s and s.connected),
            s.mode if s else "",
            s.hello if s else "",
            self._ipad_clients,
        )
        if st_sig != self._m5_st_sig:
            self._m5_st_sig = st_sig
            self._m5_bridge.publish(EVT_STATUS, self._m5_status_dict())
        if s:
            ev_sig = s.events[0] if s.events else ""
            if ev_sig != self._m5_evt_sig:
                self._m5_evt_sig = ev_sig
                self._m5_bridge.publish(EVT_EVENTS, self._m5_events_list())
            scan_sig = tuple((n.hub, n.ch, n.addr, n.kind, n.mag, n.agc) for n in s.nodes)
            if scan_sig != self._m5_scan_sig:
                self._m5_scan_sig = scan_sig
                self._m5_bridge.publish(EVT_SCAN, self._m5_scan_dict())
            prof_sig = route_sig(s.routes)
            if prof_sig != self._m5_prof_sig:
                self._m5_prof_sig = prof_sig
                self._m5_bridge.publish(EVT_PROFILE, self._m5_profile_dict())
            cal_sig = (s.cal_status, s.map_ch, len(s.map_points))
            if cal_sig != self._m5_cal_sig:
                self._m5_cal_sig = cal_sig
                self._m5_bridge.publish(EVT_CAL, self._m5_cal_dict())
            nvs_sig = (
                s.nvs_ok,
                tuple(
                    (e.get("ns"), e.get("key"), e.get("size"), len(str(e.get("data_hex") or "")))
                    for e in s.nvs_entries
                ),
            )
            if nvs_sig != self._m5_nvs_sig:
                self._m5_nvs_sig = nvs_sig
                self._m5_bridge.publish(EVT_NVS, self._m5_nvs_dict())

    def _m5_handle_cmd(self, msg: dict) -> None:
        """iPad からの操作。Tk スレッドで apply_op に渡す。"""
        self._from_ipad = True
        try:
            self.apply_op(msg, sess=self._m5_sess())
        finally:
            self._from_ipad = False

    def apply_op(self, msg: dict, *, sess: AtomSession | None = None) -> None:
        """
        PC ボタンと iPad の共通操作入口。サーボを動かす変更はここを通す。

        sess を省略すると、選択中 COM（_sess）。iPad は _m5_sess を渡す。
        全停止と本記録は iPad 操作中でも PC から残す。
        """
        op = str(msg.get("op") or "")
        if op not in ("hold", "record_start", "record_stop") and self._pc_locked():
            return
        s = sess if sess is not None else self._sess()
        if op == "hold":
            self._hold_all()
            self._m5_publish_control()
            return
        if op == "record_start":
            self._record_start(str(msg.get("name") or ""), str(msg.get("notes") or ""))
            return
        if op == "record_stop":
            self._record_stop()
            return
        if s is None:
            return
        if self._pc_cal is not None and (
            op in ("out", "joint", "random", "mode") or str(op).startswith("cop_")
        ):
            # 校正掃引中は 40〜230° PWM を PC が握る
            return
        if op == "mode":
            robot = bool(msg.get("robot"))
            if robot:
                self._cop_stop("Robot モードへ切替")
            self.mode_var.set("robot" if robot else "lab")
            s.send(proto.cmd_mode(robot))
        elif op == "scan":
            s.send(proto.cmd_scan())
        elif op == "identify":
            s.send(proto.cmd_identify())
        elif op == "auto_scan":
            self._auto_scan.set(bool(msg.get("on")))
            if self._auto_scan.get():
                self._auto_loop()
            elif self._scan_job is not None:
                self.after_cancel(self._scan_job)
                self._scan_job = None
        elif op == "out":
            j = int(msg.get("ch", 0))
            if 0 <= j < JOINTS:
                on = bool(msg.get("on"))
                self.out_vars[j].set(on)
                s.send(proto.cmd_out(j, on))
                if on:
                    # 机上ラボから来た PWM ON は、いまの指令角（40〜230°）を保つ
                    self._send_live_joint(
                        s, j, float(self.cmd_vars[j].get()), wide=bool(msg.get("wide"))
                    )
                else:
                    self.rand_vars[j].set(False)
                    if j == copctrl.HEEL_CH:
                        self._cop_stop("かかとピッチ PWM OFF")
        elif op == "joint":
            j = int(msg.get("ch", 0))
            if 0 <= j < JOINTS:
                if j == copctrl.HEEL_CH and (self._cop.p_on or self._cop.sweep_on):
                    self._cop_stop("手動指令で P/スイープ停止")
                # wide は机上ラボ（1 サーボ）用。ファーム可動域 40〜230° をそのまま使う
                deg = self._clamp_live_deg(float(msg.get("deg", 135.0)), bool(msg.get("wide")))
                self._syncing = True
                try:
                    self.cmd_vars[j].set(round(deg, 1))
                finally:
                    self._syncing = False
                if self.rand_vars[j].get():
                    self.rand_vars[j].set(False)
                now = time.time()
                if self.out_vars[j].get() and now - self._last_cmd_t[j] >= 0.08:
                    self._last_cmd_t[j] = now
                    s.send(proto.cmd_joint(j, deg))
        elif op == "random":
            j = int(msg.get("ch", 0))
            if 0 <= j < JOINTS:
                on = bool(msg.get("on"))
                self.rand_vars[j].set(on)
                if on:
                    if not self.out_vars[j].get():
                        self.out_vars[j].set(True)
                        s.send(proto.cmd_out(j, True))
                        s.send(proto.cmd_joint(j, float(self.cmd_vars[j].get())))
                    self._rand_until[j] = 0.0
                    s.note(f"関節{j} ランダム ON")
                else:
                    s.note(f"関節{j} ランダム OFF")
        elif op == "rand_settings":
            for key, var in (
                ("rand_min", self.rand_min_var),
                ("rand_max", self.rand_max_var),
                ("rand_hold_min", self.rand_hold_min_var),
                ("rand_hold_max", self.rand_hold_max_var),
                ("rand_jump", self.rand_jump_var),
            ):
                if key in msg:
                    try:
                        var.set(float(msg[key]))
                    except (tk.TclError, TypeError, ValueError):
                        pass
        elif op == "amp_limit":
            try:
                self._amp_limit.set(float(msg.get("amp_limit", 8.0)))
            except (tk.TclError, TypeError, ValueError):
                pass
        elif op == "probe":
            hub = str(msg.get("hub") or "root")
            ch = int(msg.get("ch", -1))
            addr = str(msg.get("addr") or "0x36")
            if hub == "root":
                try:
                    a = int(addr, 0) if addr.lower().startswith("0x") else int(addr, 16)
                except ValueError:
                    a = 0x36
                s.send(proto.cmd_probe_root(a))
            else:
                try:
                    hub_n = int(hub, 16)
                except ValueError:
                    hub_n = 0x70
                s.send(proto.cmd_probe_hub(hub_n, ch))
        elif op == "ina_assign":
            j = int(msg.get("ch", 0))
            if 0 <= j < len(s.routes):
                s.routes[j].ina_hub = int(msg.get("ina_hub", 0))
                s.routes[j].ina_ch = int(msg.get("ina_ch", -1))
                s.routes[j].ina_addr = int(msg.get("ina_addr", 0))
                self._send_routes(s, s.routes, f"INA 関節{j} ← iPad")
        elif op == "prof_get":
            s.send(proto.cmd_prof_get())
        elif op == "prof_default":
            s.send(proto.cmd_prof_default())
        elif op == "prof_from_scan":
            self._prof_from_scan()
        elif op == "prof_put":
            raw = msg.get("routes")
            if isinstance(raw, list) and raw:
                routes = default_routes()
                for i, d in enumerate(raw[:JOINTS]):
                    if not isinstance(d, dict):
                        continue
                    routes[i] = JointRoute(
                        enc_hub=int(d.get("enc_hub", 0)),
                        enc_ch=int(d.get("enc_ch", -1)),
                        enc_addr=int(d.get("enc_addr", 0)),
                        act_hub=int(d.get("act_hub", 0)),
                        act_ch=int(d.get("act_ch", -1)),
                        act_addr=int(d.get("act_addr", 0x25)),
                        servo_ch=int(d.get("servo_ch", i)),
                        ina_hub=int(d.get("ina_hub", 0)),
                        ina_ch=int(d.get("ina_ch", -1)),
                        ina_addr=int(d.get("ina_addr", 0)),
                    )
                self._send_routes(s, routes, "プロファイル送信（iPad）", foot=self._foot_from_msg(msg, s.foot))
        elif op == "cal_start":
            ch = int(msg.get("ch", 0))
            self._cal_run(ch, s)
        elif op == "cal_abort":
            self._cal_abort()
        elif op == "map_get":
            ch = int(msg.get("ch", 0))
            s.send(proto.cmd_map_get(ch))
        elif op == "nvs_list":
            s.send(proto.cmd_nvs_list())
        elif op == "nvs_erase":
            ns = str(msg.get("ns") or "")
            if ns in ("cal", "jprof"):
                s.send(proto.cmd_nvs_erase(ns))
        elif op.startswith("cop_"):
            self._m5_handle_cop(s, op, msg)
        self._m5_publish_control()
        self._m5_publish_status()

    def _clamp_live_deg(self, deg: float, wide: bool) -> float:
        """
        ライブ指令のクランプ。

        既定は右脚実験の 100〜170°。wide=True（机上ラボの単軸テスト）だけ
        ファームの可動域 40〜230° をそのまま通す。
        """
        return clamp_cal_deg(deg) if wide else copctrl.clamp_cmd(deg)

    def _send_live_joint(self, s: AtomSession, j: int, deg: float, *, wide: bool = False) -> None:
        """ライブ PWM。既定は 100〜170° へクランプして送る（校正スイープは使わない）。"""
        if self._pc_cal is not None:
            return
        deg = self._clamp_live_deg(deg, wide)
        self._syncing = True
        try:
            if 0 <= j < len(self.cmd_vars):
                self.cmd_vars[j].set(round(deg, 1))
        finally:
            self._syncing = False
        if 0 <= j < len(self.out_vars) and self.out_vars[j].get():
            s.send(proto.cmd_joint(j, deg))
            self._last_cmd_t[j] = time.time()

    def _heel_cmd(self) -> float:
        """かかとピッチの現在指令。Tk 変数が壊れていても 135 に倒す。"""
        try:
            return copctrl.clamp_cmd(float(self.cmd_vars[copctrl.HEEL_CH].get()))
        except (tk.TclError, TypeError, ValueError, IndexError):
            return 135.0

    def _cop_stop(self, reason: str, *, clear_hold: bool = False) -> None:
        """P / スイープだけ止める。PWM と最後の指令は残す。"""
        was = self._cop.p_on or self._cop.sweep_on
        self._cop.stop_motion(reason)
        if clear_hold:
            self._cop.held = False
        if was:
            s = self._m5_sess()
            if s:
                s.note(f"COP  {reason}")

    def _cop_stop_auto_scan(self) -> None:
        """探索中はスキャンで周期が伸びないように止める。"""
        if not self._auto_scan.get():
            return
        self._auto_scan.set(False)
        if self._scan_job is not None:
            self.after_cancel(self._scan_job)
            self._scan_job = None

    def _ensure_lab_for_cop(self, s: AtomSession) -> None:
        """Robot は全軸 135° 固定なので COP 実験は Lab へ戻す。"""
        if s.mode == "robot" or self.mode_var.get() == "robot":
            self.mode_var.set("lab")
            s.send(proto.cmd_mode(False))
            s.note("COP  Lab へ切替")

    def _cop_hold_fixed(self, s: AtomSession) -> None:
        """股・膝・踵ロールを今の指令角で PWM ON。かかとピッチも出す。補正角は使わない。"""
        self._ensure_lab_for_cop(s)
        self._cop_stop_auto_scan()
        for i in (*copctrl.HOLD_CHS, copctrl.HEEL_CH):
            if i < len(self.rand_vars):
                self.rand_vars[i].set(False)
            try:
                deg = copctrl.clamp_cmd(float(self.cmd_vars[i].get()))
            except (tk.TclError, TypeError, ValueError):
                deg = 135.0
            self.out_vars[i].set(True)
            s.send(proto.cmd_out(i, True))
            self._send_live_joint(s, i, deg)
        self._cop.held = True
        self._cop.status = "4軸を指令角で固定"
        s.note("COP  4軸固定（指令角）")

    def _m5_handle_cop(self, s: AtomSession, op: str, msg: dict) -> None:
        """Hub 右脚タブからの COP 作業指令。"""
        if op == "cop_hold_fixed":
            self._cop_hold_fixed(s)
        elif op == "cop_step":
            self._cop.sweep_on = False
            self._cop.p_on = False
            self._cop_hold_fixed(s)
            try:
                delta = float(msg.get("delta", copctrl.STEP_DEG))
            except (TypeError, ValueError):
                delta = copctrl.STEP_DEG
            nxt = copctrl.clamp_cmd(self._heel_cmd() + delta)
            self._send_live_joint(s, copctrl.HEEL_CH, nxt)
            self._cop.update_cop(foot_sample_dict(s.last_frame) if s.last_frame else None)
            self._cop.note_sample(nxt)
            if self._cop.estimated is None:
                self._cop.status = f"手動 {nxt:.1f}°  推定 —"
            else:
                self._cop.status = f"手動 {nxt:.1f}°  推定 {self._cop.estimated:.1f}°"
        elif op == "cop_sweep_start":
            self._cop.p_on = False
            self._cop_hold_fixed(s)
            self._cop.sweep_on = True
            cur = self._heel_cmd()
            # 遠い端へ先に進み、可動域をゆっくり往復する
            self._cop.sweep_dir = 1.0 if cur < 135.0 else -1.0
            self._cop.last_t = None
            self._cop.status = "自動スイープ開始"
            s.note("COP  自動スイープ開始")
        elif op == "cop_sweep_stop":
            self._cop.sweep_on = False
            self._cop.status = "スイープ停止"
            s.note("COP  スイープ停止")
        elif op == "cop_neutral_confirm":
            self._cop.confirm_neutral(self._heel_cmd())
            s.note(f"COP  ニュートラル確定  {self._cop.confirmed:.1f}°")
        elif op == "cop_neutral_clear":
            self._cop.clear_confirmed()
        elif op == "cop_p_on":
            if self._cop.active_neutral() is None:
                self._cop.status = "P制御不可（ニュートラル未確定）"
                return
            self._cop.sweep_on = False
            self._cop_hold_fixed(s)
            self._cop.p_on = True
            self._cop.last_t = None
            self._cop.status = "P制御 ON"
            s.note("COP  P制御 ON")
        elif op == "cop_p_off":
            self._cop.p_on = False
            self._cop.status = "P制御 OFF（PWM 維持）"
            s.note("COP  P制御 OFF")
        elif op == "cop_sign":
            try:
                sgn = float(msg.get("sign", 1))
            except (TypeError, ValueError):
                sgn = 1.0
            self._cop.sign = -1.0 if sgn < 0 else 1.0
            self._cop.status = f"符号 {'+' if self._cop.sign > 0 else '−'}"
        elif op == "cop_kp":
            try:
                self._cop.kp = copctrl.clamp_kp(float(msg.get("kp", copctrl.KP_DEFAULT)))
            except (TypeError, ValueError):
                pass
        else:
            self._cop.status = f"未知の COP 指令  {op}"

    def _update_cop_ctrl(self) -> None:
        """Tk 周期で COP を見て、かかとピッチだけゆっくり指令する。"""
        if self._pc_cal is not None:
            return
        s = self._m5_sess()
        if s is None or not s.connected:
            if self._cop.p_on or self._cop.sweep_on:
                self._cop_stop("ATOM 切断", clear_hold=True)
            return
        f = s.last_frame
        self._cop.update_cop(foot_sample_dict(f) if f else None)
        if not (self._cop.p_on or self._cop.sweep_on):
            return
        nxt = self._cop.tick(time.time(), self._heel_cmd())
        if nxt is None:
            return
        if abs(nxt - self._heel_cmd()) < 0.01:
            return
        self._send_live_joint(s, copctrl.HEEL_CH, nxt)

    def _build_topo(self) -> None:
        hint = tk.Label(
            self.tab_topo,
            text="挿した Unit が木に出ます。ノードを選んで「1回読む」。机ではケーブルを抜き差しして差分を見てください。",
            bg=BG, fg=MUTED, anchor="w",
        )
        hint.pack(fill="x", padx=8, pady=6)
        cols = tk.Frame(self.tab_topo, bg=BG)
        cols.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(cols, columns=("kind", "mag", "agc"), show="tree headings", height=16)
        self.tree.heading("#0", text="場所")
        self.tree.heading("kind", text="種類")
        self.tree.heading("mag", text="磁石")
        self.tree.heading("agc", text="AGC")
        self.tree.column("#0", width=280)
        self.tree.column("kind", width=90)
        self.tree.column("mag", width=90)
        self.tree.column("agc", width=70)
        self.tree.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        side = tk.Frame(cols, bg=BG, width=200)
        side.pack(side="right", fill="y", padx=8)
        self.probe_btn = tk.Button(
            side, text="1回読む (PROBE)", command=self._probe, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.probe_btn.pack(fill="x", pady=4)
        tk.Label(side, text="INA を関節へ", bg=BG, fg=MUTED).pack(anchor="w", pady=(12, 2))
        self.topo_ina_joint = tk.IntVar(value=0)
        self.topo_ina_spin = ttk.Spinbox(
            side, from_=0, to=JOINTS - 1, textvariable=self.topo_ina_joint, width=4
        )
        self.topo_ina_spin.pack(fill="x")
        self.assign_ina_btn = tk.Button(
            side, text="選択ノードを割当", command=self._assign_ina_from_tree,
            bg=GOOD, fg=TEXT, relief="flat",
        )
        self.assign_ina_btn.pack(fill="x", pady=4)
        self.clear_ina_btn = tk.Button(
            side, text="割当を外す", command=self._clear_ina_from_tree,
            bg=CARD_HI, fg=TEXT, relief="flat",
        )
        self.clear_ina_btn.pack(fill="x", pady=2)
        self.topo_lock_btns = [self.probe_btn, self.assign_ina_btn, self.clear_ina_btn]
        tk.Label(
            side,
            text="INA226 を選んで関節番号を指定すると、20 Hz の電源監視がその経路になります。Grove 直結でも Hub 先でも可。",
            bg=BG, fg=MUTED, wraplength=180, justify="left",
        ).pack(anchor="w", pady=8)

    def _build_prof(self) -> None:
        """論理関節 → Hub/サーボ ch の対応表。焼き直しなしで配線を変えられる。"""
        hint = tk.Label(
            self.tab_prof,
            text="hub=0 は Grove 直結。enc=AS5600、act=サーボ、ina=その関節の電源監視。"
            " 変更後「ボードへ送信」で NVS に保存。ina_addr=0 は未割当。",
            bg=BG, fg=MUTED, anchor="w", wraplength=900, justify="left",
        )
        hint.pack(fill="x", padx=8, pady=6)
        btn = tk.Frame(self.tab_prof, bg=BG)
        btn.pack(fill="x", padx=8, pady=4)
        self.prof_get_btn = tk.Button(
            btn, text="ボードから取得", command=self._prof_get, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.prof_get_btn.pack(side="left", padx=(0, 6))
        self.prof_put_btn = tk.Button(
            btn, text="ボードへ送信", command=self._prof_put, bg=GOOD, fg=TEXT, relief="flat"
        )
        self.prof_put_btn.pack(side="left", padx=6)
        self.prof_default_btn = tk.Button(
            btn, text="既定に戻す", command=self._prof_default, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.prof_default_btn.pack(side="left", padx=6)
        self.prof_from_scan_btn = tk.Button(
            btn, text="SCANから仮割当", command=self._prof_from_scan, bg=FLASH, fg=BG, relief="flat"
        )
        self.prof_from_scan_btn.pack(side="left", padx=6)
        self.prof_lock_btns = [
            self.prof_get_btn, self.prof_put_btn, self.prof_default_btn, self.prof_from_scan_btn,
        ]
        self.prof_entries: list[tk.Entry] = []

        self.prof_vars: list[dict[str, tk.StringVar]] = []
        grid = tk.Frame(self.tab_prof, bg=BG)
        grid.pack(fill="x", padx=8, pady=8)
        headers = (
            "関節", "enc_hub", "enc_ch", "enc_addr",
            "act_hub", "act_ch", "act_addr", "servo_ch",
            "ina_hub", "ina_ch", "ina_addr",
        )
        for c, h in enumerate(headers):
            tk.Label(grid, text=h, bg=BG, fg=MUTED).grid(row=0, column=c, padx=4, pady=2)
        for i in range(JOINTS):
            vars_row: dict[str, tk.StringVar] = {}
            tk.Label(grid, text=str(i), bg=BG, fg=TEXT).grid(row=i + 1, column=0, padx=4)
            defaults = default_routes()[i]
            for c, (key, val) in enumerate(
                (
                    ("enc_hub", f"0x{defaults.enc_hub:02X}"),
                    ("enc_ch", str(defaults.enc_ch)),
                    ("enc_addr", f"0x{defaults.enc_addr:02X}"),
                    ("act_hub", str(defaults.act_hub)),
                    ("act_ch", str(defaults.act_ch)),
                    ("act_addr", f"0x{defaults.act_addr:02X}"),
                    ("servo_ch", str(defaults.servo_ch)),
                    ("ina_hub", f"0x{defaults.ina_hub:02X}"),
                    ("ina_ch", str(defaults.ina_ch)),
                    ("ina_addr", f"0x{defaults.ina_addr:02X}"),
                ),
                start=1,
            ):
                var = tk.StringVar(value=val)
                vars_row[key] = var
                ent = tk.Entry(
                    grid, textvariable=var, width=8, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat"
                )
                ent.grid(row=i + 1, column=c, padx=4, pady=2)
                self.prof_entries.append(ent)
            self.prof_vars.append(vars_row)
        foot_row = tk.Frame(self.tab_prof, bg=BG)
        foot_row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(foot_row, text="右足スレーブ", bg=BG, fg=MUTED).pack(side="left", padx=(0, 8))
        self.foot_vars: dict[str, tk.StringVar] = {}
        foot0 = default_foot()
        for key, label, val in (
            ("hub", "hub", f"0x{foot0.hub:02X}"),
            ("ch", "ch", str(foot0.ch)),
            ("addr", "addr", f"0x{foot0.addr:02X}"),
        ):
            tk.Label(foot_row, text=label, bg=BG, fg=MUTED).pack(side="left")
            var = tk.StringVar(value=val)
            self.foot_vars[key] = var
            ent = tk.Entry(
                foot_row, textvariable=var, width=8, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat"
            )
            ent.pack(side="left", padx=(4, 10))
            self.prof_entries.append(ent)
        tk.Label(
            foot_row,
            text="addr=0 で無効。既定は 0x71 CH2 / 0x28",
            bg=BG,
            fg=MUTED,
        ).pack(side="left")
        self._prof_sig: object = None

    def _build_joint(self) -> None:
        self.joint_labs: list[dict[str, tk.Label]] = []
        self.ina_sel_vars: list[tk.StringVar] = []
        self.ina_combos: list[ttk.Combobox] = []
        # 制御状態は論理関節ごと（パネル切替で失わない）
        self.out_vars = [tk.BooleanVar(value=False) for _ in range(JOINTS)]
        self.cmd_vars = [tk.DoubleVar(value=135.0) for _ in range(JOINTS)]
        self.rand_vars = [tk.BooleanVar(value=False) for _ in range(JOINTS)]
        self.panel_joint_vars: list[tk.IntVar] = []
        self.panel_out_cb: list[tk.Checkbutton] = []
        self.panel_cmd_scale: list[tk.Scale] = []
        self.panel_rand_cb: list[tk.Checkbutton] = []
        row = tk.Frame(self.tab_joint, bg=BG)
        row.pack(fill="x", padx=8, pady=6)
        for p in range(JOINT_PANELS):
            card = tk.Frame(row, bg=CARD)
            card.pack(side="left", fill="x", expand=True, padx=4)
            # タイトルを関節番号の選択にする（0〜7）
            head = tk.Frame(card, bg=CARD)
            head.pack(anchor="w", padx=10, pady=(6, 0))
            tk.Label(head, text="関節", bg=CARD, fg=MUTED).pack(side="left")
            jv = tk.IntVar(value=p)
            self.panel_joint_vars.append(jv)
            pick = ttk.Combobox(
                head,
                textvariable=jv,
                values=tuple(range(JOINTS)),
                width=4,
                state="readonly",
            )
            pick.pack(side="left", padx=6)
            pick.bind("<<ComboboxSelected>>", lambda _e, p=p: self._on_panel_joint(p))
            labs: dict[str, tk.Label] = {}
            # 数値を 2 カラムにして縦を短くし、下のグラフへ高さを回す
            metrics = tk.Frame(card, bg=CARD)
            metrics.pack(fill="x", padx=4, pady=2)
            # uniform で左右カラム幅を固定し、数値更新で列幅が再配分されないようにする
            metrics.columnconfigure(0, weight=1, uniform="jointm")
            metrics.columnconfigure(1, weight=1, uniform="jointm")

            def _metric(parent: tk.Frame, r: int, c: int, key: str, title: str, col: str) -> None:
                # 値は等幅＋固定幅＋右寄せ。桁が変わってもセル幅と数字位置が動かない
                cell = tk.Frame(parent, bg=CARD)
                cell.grid(row=r, column=c, sticky="ew", padx=6, pady=0)
                cell.columnconfigure(1, weight=1)
                tk.Label(cell, text=title, bg=CARD, fg=MUTED, font=("Segoe UI", 9)).grid(
                    row=0, column=0, sticky="w"
                )
                lab = _value_label(cell, col)
                lab.grid(row=0, column=1, sticky="e")
                labs[key] = lab

            _metric(metrics, 0, 0, "cmd", "指令", CMD_COLOR)
            _metric(metrics, 1, 0, "raw", "生角", AS_COLOR)
            _metric(metrics, 2, 0, "unw", "unwrap", UNWRAP_COLOR)
            _metric(metrics, 3, 0, "corr", "補正", CORR_COLOR)
            _metric(metrics, 0, 1, "mag", "磁石", GOOD)
            _metric(metrics, 1, 1, "agc", "AGC", MUTED)
            _metric(metrics, 2, 1, "v", "電圧", VOLT_COLOR)
            _metric(metrics, 3, 1, "a", "電流", AMP_COLOR)
            _metric(metrics, 4, 0, "w", "電力", WATT_COLOR)
            ina_cell = tk.Frame(metrics, bg=CARD)
            ina_cell.grid(row=4, column=1, sticky="ew", padx=6, pady=0)
            tk.Label(ina_cell, text="INA226", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
            iv = tk.StringVar(value="なし")
            cb = ttk.Combobox(ina_cell, textvariable=iv, state="readonly", width=14)
            cb.pack(side="right", padx=(4, 0))
            cb.bind("<<ComboboxSelected>>", lambda _e, p=p: self._on_ina_combo(p))
            self.joint_labs.append(labs)
            self.ina_sel_vars.append(iv)
            self.ina_combos.append(cb)
            out_cb = tk.Checkbutton(
                card, text="PWM 出力する（机では必要な軸だけ）", variable=self.out_vars[p],
                command=lambda p=p: self._toggle_out(p),
                bg=CARD, fg=TEXT, selectcolor=CARD_HI, activebackground=CARD, activeforeground=TEXT,
            )
            out_cb.pack(anchor="w", padx=10, pady=(2, 0))
            self.panel_out_cb.append(out_cb)
            # 指令値は上の「指令」ラベルで見えるのでスライダ上の数字は出さない（高さ節約）
            sc = tk.Scale(
                card, from_=40, to=230, orient="horizontal", variable=self.cmd_vars[p], resolution=0.5,
                bg=CARD, fg=TEXT, troughcolor=CARD_HI, highlightthickness=0,
                showvalue=False, sliderlength=16,
                command=lambda _v, p=p: self._cmd_drag(p),
            )
            sc.pack(fill="x", padx=10, pady=(0, 0))
            self.panel_cmd_scale.append(sc)
            rand_cb = tk.Checkbutton(
                card,
                text="ランダム動作",
                variable=self.rand_vars[p],
                command=lambda p=p: self._toggle_random(p),
                bg=CARD,
                fg=WARN,
                selectcolor=CARD_HI,
                activebackground=CARD,
                activeforeground=WARN,
            )
            rand_cb.pack(anchor="w", padx=10, pady=(0, 4))
            self.panel_rand_cb.append(rand_cb)

        # ランダム共通設定（PC 側が Joint 指令を送る。atoms3 の random と同趣旨）
        rand_box = tk.Frame(self.tab_joint, bg=CARD)
        rand_box.pack(fill="x", padx=8, pady=(0, 2))
        tk.Label(rand_box, text="ランダム設定", bg=CARD, fg=MUTED).pack(side="left", padx=10, pady=4)
        self.rand_min_var = tk.DoubleVar(value=RAND_MIN_DEG)
        self.rand_max_var = tk.DoubleVar(value=RAND_MAX_DEG)
        self.rand_hold_min_var = tk.DoubleVar(value=RAND_HOLD_MIN_S)
        self.rand_hold_max_var = tk.DoubleVar(value=RAND_HOLD_MAX_S)
        self.rand_jump_var = tk.DoubleVar(value=RAND_MIN_JUMP_DEG)
        self.rand_entries: list[tk.Entry] = []
        for label, var, width in (
            ("最小°", self.rand_min_var, 5),
            ("最大°", self.rand_max_var, 5),
            ("保持min秒", self.rand_hold_min_var, 5),
            ("保持max秒", self.rand_hold_max_var, 5),
            ("最小ジャンプ°", self.rand_jump_var, 5),
        ):
            tk.Label(rand_box, text=label, bg=CARD, fg=MUTED).pack(side="left", padx=(8, 2))
            ent = tk.Entry(
                rand_box, textvariable=var, width=width, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, relief="flat"
            )
            ent.pack(side="left")
            self.rand_entries.append(ent)
        tk.Label(
            rand_box,
            text="PWM ON の軸だけ動く。スライダ操作でその軸のランダムはオフ",
            bg=CARD,
            fg=MUTED,
        ).pack(side="left", padx=12)

        # 角度グラフ: 表示する関節を選び、各系列をトグル
        plot_bar = tk.Frame(self.tab_joint, bg=BG)
        plot_bar.pack(fill="x", padx=8, pady=(4, 0))
        tk.Label(plot_bar, text="グラフ関節", bg=BG, fg=MUTED).pack(side="left")
        self.plot_joint_var = tk.IntVar(value=0)
        joint_box = ttk.Combobox(
            plot_bar,
            textvariable=self.plot_joint_var,
            values=tuple(range(JOINTS)),
            width=4,
            state="readonly",
        )
        joint_box.pack(side="left", padx=6)
        joint_box.bind("<<ComboboxSelected>>", self._on_plot_joint)

        # 角度は左軸（0–360°）。電源は右軸（見える系列で自動スケール）
        self.plot_line_vars: dict[str, tk.BooleanVar] = {
            "cmd": tk.BooleanVar(value=True),
            "raw": tk.BooleanVar(value=False),
            "unw": tk.BooleanVar(value=False),
            "corr": tk.BooleanVar(value=True),
            "v": tk.BooleanVar(value=False),
            "a": tk.BooleanVar(value=True),
            "w": tk.BooleanVar(value=False),
        }
        for key, title, col in (
            ("cmd", "指令", CMD_COLOR),
            ("raw", "生角", AS_COLOR),
            ("unw", "unwrap", UNWRAP_COLOR),
            ("corr", "補正", CORR_COLOR),
        ):
            tk.Checkbutton(
                plot_bar,
                text=title,
                variable=self.plot_line_vars[key],
                command=self._on_plot_lines,
                bg=BG,
                fg=col,
                selectcolor=CARD_HI,
                activebackground=BG,
                activeforeground=col,
            ).pack(side="left", padx=6)
        tk.Label(plot_bar, text="|", bg=BG, fg=MUTED).pack(side="left", padx=4)
        for key, title, col in (
            ("v", "電圧", VOLT_COLOR),
            ("a", "電流", AMP_COLOR),
            ("w", "電力", WATT_COLOR),
        ):
            tk.Checkbutton(
                plot_bar,
                text=title,
                variable=self.plot_line_vars[key],
                command=self._on_plot_lines,
                bg=BG,
                fg=col,
                selectcolor=CARD_HI,
                activebackground=BG,
                activeforeground=col,
            ).pack(side="left", padx=6)

        self.plot_ang = LinePlot(self.tab_joint, "関節0  左:°  右:電源", 0, 360, "°")
        self.plot_ang.add_series("cmd", CMD_COLOR)
        self.plot_ang.add_series("raw", AS_COLOR)
        self.plot_ang.add_series("unw", UNWRAP_COLOR)
        self.plot_ang.add_series("corr", CORR_COLOR)
        self.plot_ang.add_series("v", VOLT_COLOR, axis="right", unit="V")
        self.plot_ang.add_series("a", AMP_COLOR, axis="right", unit="A")
        self.plot_ang.add_series("w", WATT_COLOR, axis="right", unit="W")
        # 電源系列は既定で電流だけ出す（電圧と同時だと電流が潰れる）
        self.plot_ang.set_visible("raw", False)
        self.plot_ang.set_visible("unw", False)
        self.plot_ang.set_visible("v", False)
        self.plot_ang.set_visible("w", False)
        # パネルを縮めた分、グラフの希望高さを上げて下側を広く取る
        self.plot_ang.configure(height=220)
        self.plot_ang.pack(fill="both", expand=True, padx=8, pady=(4, 6))

    def _plot_joint_index(self) -> int:
        try:
            j = int(self.plot_joint_var.get())
        except (tk.TclError, ValueError):
            return 0
        return max(0, min(JOINTS - 1, j))

    def _panel_joint(self, panel: int) -> int:
        """パネル panel が今表示している論理関節番号。"""
        if panel < 0 or panel >= len(self.panel_joint_vars):
            return 0
        try:
            j = int(self.panel_joint_vars[panel].get())
        except (tk.TclError, ValueError):
            return panel
        return max(0, min(JOINTS - 1, j))

    def _bind_panel_joint_widgets(self, panel: int) -> None:
        """パネルのチェック／スライダを、選択中の関節の変数に付け替える。"""
        j = self._panel_joint(panel)
        if panel < len(self.panel_out_cb):
            self.panel_out_cb[panel].configure(variable=self.out_vars[j])
        if panel < len(self.panel_cmd_scale):
            self.panel_cmd_scale[panel].configure(variable=self.cmd_vars[j])
        if panel < len(self.panel_rand_cb):
            self.panel_rand_cb[panel].configure(variable=self.rand_vars[j])

    def _on_panel_joint(self, panel: int, _evt: object = None) -> None:
        """パネルの関節番号が変わったら、操作対象と表示を付け替える。"""
        self._bind_panel_joint_widgets(panel)
        s = self._sess()
        if s:
            self._refresh_ina_combos(s)
            if s.last_frame is not None:
                self._fill_joint_panel(s.last_frame, panel)

    def _on_plot_joint(self, _evt: object = None) -> None:
        j = self._plot_joint_index()
        self.plot_ang.clear()
        self.plot_ang.set_title(f"関節{j}  左:°  右:電源")
        self.plot_ang.redraw()

    def _on_plot_lines(self) -> None:
        for key, var in self.plot_line_vars.items():
            self.plot_ang.set_visible(key, bool(var.get()))
        self.plot_ang.redraw()

    def _build_cal(self) -> None:
        """サーボ↔AS5600 の 1° マップ校正。PC が 40〜230° の PWM を出す。"""
        hint = tk.Label(
            self.tab_cal,
            text="周囲を空けてから実行。PC がサーボ PWM を 40→230→40°（1°・静止待ち）で掃引し、"
            "AS5600 と組んだマップを NVS へ送ります。所要約 2 分。中断は「中止」または全停止。"
            " ライブ実験の 100〜170° 制限は校正には使いません。",
            bg=BG, fg=MUTED, anchor="w", wraplength=900, justify="left",
        )
        hint.pack(fill="x", padx=8, pady=6)

        row = tk.Frame(self.tab_cal, bg=BG)
        row.pack(fill="x", padx=8, pady=4)
        tk.Label(row, text="関節", bg=BG, fg=MUTED).pack(side="left")
        self.cal_ch_var = tk.IntVar(value=0)
        self.cal_ch_spin = ttk.Spinbox(row, from_=0, to=JOINTS - 1, textvariable=self.cal_ch_var, width=4)
        self.cal_ch_spin.pack(side="left", padx=8)
        self.cal_start_btn = tk.Button(
            row, text="校正開始", command=self._cal_start, bg=WARN, fg=BG, relief="flat"
        )
        self.cal_start_btn.pack(side="left", padx=6)
        # 中止は全停止と同様に PC からも残す
        tk.Button(row, text="中止", command=self._cal_abort, bg=BAD, fg=TEXT, relief="flat").pack(
            side="left", padx=6
        )

        self.cal_status_lab = tk.Label(self.tab_cal, text="状態: —", bg=BG, fg=TEXT, anchor="w")
        self.cal_status_lab.pack(fill="x", padx=8, pady=4)
        self.cal_map_lab = tk.Label(self.tab_cal, text="マップ: （未受信）", bg=BG, fg=MUTED, anchor="w")
        self.cal_map_lab.pack(fill="x", padx=8, pady=2)

        io = tk.Frame(self.tab_cal, bg=BG)
        io.pack(fill="x", padx=8, pady=10)
        self.map_get_btn = tk.Button(
            io, text="ボードからマップ取得", command=self._map_get, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.map_get_btn.pack(side="left", padx=(0, 6))
        self.map_save_btn = tk.Button(
            io, text="JSON に保存", command=self._map_save_json, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.map_save_btn.pack(side="left", padx=6)
        self.map_load_btn = tk.Button(
            io, text="JSON を開いて送信", command=self._map_load_json, bg=GOOD, fg=TEXT, relief="flat"
        )
        self.map_load_btn.pack(side="left", padx=6)
        self.cal_lock_btns = [
            self.cal_start_btn, self.map_get_btn, self.map_save_btn, self.map_load_btn,
        ]
        self._cal_status_sig = ""
        self._cal_map_sig: object = None

    def _cal_start(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        ch = int(self.cal_ch_var.get())
        if not messagebox.askokcancel(
            "校正",
            f"関節 {ch} を PWM 40→230→40° で動かします。\n"
            "干渉・配線を確認しましたか？\n（約 2 分かかります）",
        ):
            return
        self._cal_run(ch)

    def _cal_run(self, ch: int, s: AtomSession | None = None) -> None:
        """校正開始。Lab で当該軸の PWM を 40〜230° 掃引する。"""
        if s is None:
            s = self._sess()
        if not s or not s.connected:
            self.cal_status_lab.configure(text="状態: ATOM が未接続です")
            return
        if ch < 0 or ch >= JOINTS:
            self.cal_status_lab.configure(text=f"状態: 関節番号が不正 ch{ch}")
            return
        if self._pc_cal is not None:
            self.cal_status_lab.configure(text="状態: 校正中です")
            return
        self._cop_stop("校正開始")
        if ch < len(self.rand_vars):
            self.rand_vars[ch].set(False)
        if self._auto_scan.get():
            self._auto_scan.set(False)
            self._toggle_auto()
            s.note("校正のため自動スキャンを停止")
        # Robot だと PC の関節指令が 135° 固定になるので Lab にする
        self.mode_var.set("lab")
        s.send(proto.cmd_mode(False))
        cmds = cal_sweep_cmds()
        prev_out = bool(ch < len(self.out_vars) and self.out_vars[ch].get())
        seq = s.last_frame.seq if s.last_frame is not None else None
        self._pc_cal = PcCalSweep(
            port=s.port,
            ch=ch,
            cmds=cmds,
            wait_until=time.time() + CAL_FIRST_MOVE_S,
            seq_at_cmd=seq,
            prev_out=prev_out,
        )
        self._send_cal_pwm(s, ch, cmds[0])
        msg = f"校正開始  ch{ch}  PWM {CAL_MIN_DEG:.0f}→{CAL_MAX_DEG:.0f}→{CAL_MIN_DEG:.0f}°"
        s.cal_status = msg
        s.note(msg)
        self.cal_status_lab.configure(text=f"状態: {msg}")

    def _send_cal_pwm(self, s: AtomSession, ch: int, deg: float) -> None:
        """校正専用の PWM。40〜230° をそのまま Joint 指令する。"""
        deg = clamp_cal_deg(deg)
        self._syncing = True
        try:
            if 0 <= ch < len(self.cmd_vars):
                self.cmd_vars[ch].set(round(deg, 1))
            if 0 <= ch < len(self.out_vars):
                self.out_vars[ch].set(True)
        finally:
            self._syncing = False
        s.send(proto.cmd_out(ch, True))
        s.send(proto.cmd_joint(ch, deg))

    def _cal_abort(self) -> None:
        s = self._sess()
        if s:
            s.send(proto.cmd_cal_abort())
        self._pc_cal_stop("中止", restore=True)

    def _pc_cal_stop(self, reason: str, *, restore: bool = True, ok: bool = False) -> None:
        """掃引を終えて PWM を元に戻す。ok ならマップ送信済み。"""
        cal = self._pc_cal
        self._pc_cal = None
        if cal is None:
            return
        s = self.sessions.get(cal.port)
        if s is None:
            return
        if restore:
            # 掃引後は 135° に戻し、開始前の PWM ON/OFF を復元する
            s.send(proto.cmd_joint(cal.ch, 135.0))
            s.send(proto.cmd_out(cal.ch, cal.prev_out))
            self._syncing = True
            try:
                if cal.ch < len(self.cmd_vars):
                    self.cmd_vars[cal.ch].set(135.0)
                if cal.ch < len(self.out_vars):
                    self.out_vars[cal.ch].set(cal.prev_out)
            finally:
                self._syncing = False
        status = f"校正完了  ch{cal.ch}  {len(s.map_points)}点" if ok else f"校正終了  {reason}"
        s.cal_status = status
        s.note(status)
        self.cal_status_lab.configure(text=f"状態: {status}")
        self._refresh_cal_labels(s)

    def _update_pc_cal(self) -> None:
        """毎 tick。静止待ちのあと AS5600 を取り、次の PWM 角へ進める。"""
        cal = self._pc_cal
        if cal is None:
            return
        if cal.abort:
            self._pc_cal_stop("中止")
            return
        s = self.sessions.get(cal.port)
        if s is None or not s.connected:
            self._pc_cal_stop("ATOM 切断")
            return
        now = time.time()
        if now < cal.wait_until:
            return
        f = s.last_frame
        if f is None:
            if now > cal.wait_until + CAL_FRAME_WAIT_S:
                self._pc_cal_stop("テレメトリなし")
            return
        if cal.seq_at_cmd is not None and f.seq == cal.seq_at_cmd:
            if now > cal.wait_until + CAL_FRAME_WAIT_S:
                self._pc_cal_stop("テレメトリ待ちタイムアウト")
            return
        cmd = cal.cmds[cal.index]
        if not (0 <= cal.ch < len(f.as_ok) and f.as_ok[cal.ch]):
            self._pc_cal_stop("AS5600 欠測")
            return
        unw = f.unwrap[cal.ch] if cal.ch < len(f.unwrap) else None
        if unw is None:
            self._pc_cal_stop("unwrap なし")
            return
        cal.samples.append((float(unw), cmd))
        total = len(cal.cmds)
        pct = int((cal.index + 1) * 100 / total) if total else 100
        status = f"校正  ch{cal.ch}  {pct}%  {cmd:.0f}°"
        s.cal_status = status
        self.cal_status_lab.configure(text=f"状態: {status}")
        cal.index += 1
        if cal.index >= total:
            points = build_cal_map_points(cal.samples)
            if points is None:
                self._pc_cal_stop(
                    f"マップ失敗  {len(cal.samples)}サンプル（{CAL_MIN_MAP_POINTS}点以上必要）"
                )
                return
            s.map_ch = cal.ch
            s.map_points = points
            s.send_map(cal.ch, points)
            s.note(f"マップ送信  ch{cal.ch}  {len(points)}点")
            self._pc_cal_stop("完了", ok=True)
            return
        nxt = cal.cmds[cal.index]
        cal.seq_at_cmd = f.seq
        cal.wait_until = now + CAL_SETTLE_S
        self._send_cal_pwm(s, cal.ch, nxt)

    def _map_get(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        ch = int(self.cal_ch_var.get())
        s.send(proto.cmd_map_get(ch))
        s.note(f"マップ取得  ch{ch}")

    def _map_save_json(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s or len(s.map_points) < 2:
            messagebox.showinfo("マップ", "先にボードからマップを取得するか、校正を完了してください。")
            return
        path = filedialog.asksaveasfilename(
            title="校正マップを保存",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"cal_map_ch{s.map_ch}.json",
        )
        if not path:
            return
        save_map(path, s.map_ch, s.map_points)
        s.note(f"マップ保存  {path}  {len(s.map_points)}点")

    def _map_load_json(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        path = filedialog.askopenfilename(
            title="校正マップを開く",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            file_ch, points = load_map(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("マップ", str(exc))
            return
        if len(points) < 2:
            messagebox.showerror("マップ", "点が足りません")
            return
        ch = int(self.cal_ch_var.get())
        # ファイルの channel と UI が違うときは UI（送信先）を優先
        if self._auto_scan.get():
            self._auto_scan.set(False)
            self._toggle_auto()
            s.note("マップ送信のため自動スキャンを停止")
        s.map_ch = ch
        s.map_points = points
        s.send_map(ch, points)
        s.note(f"マップ送信  ch{ch}  {len(points)}点  (file ch={file_ch})")
        self._refresh_cal_labels(s)

    def _refresh_cal_labels(self, s: AtomSession) -> None:
        if s.cal_status:
            self.cal_status_lab.configure(text=f"状態: {s.cal_status}")
        if s.map_points:
            self.cal_map_lab.configure(
                text=f"マップ: ch{s.map_ch}  {len(s.map_points)}点",
                fg=GOOD,
            )
        else:
            self.cal_map_lab.configure(text="マップ: （未受信）", fg=MUTED)

    def _build_pwr(self) -> None:
        lim = tk.Frame(self.tab_pwr, bg=BG)
        lim.pack(fill="x", padx=8, pady=6)
        tk.Label(lim, text="PC 側電流監視 [A]（超えたら HOLD）", bg=BG, fg=MUTED).pack(side="left")
        self.amp_entry = tk.Entry(
            lim, textvariable=self._amp_limit, width=6, bg=CARD, fg=TEXT, insertbackground=TEXT
        )
        self.amp_entry.pack(side="left", padx=8)
        self.ina_labs: list[dict[str, tk.Label]] = []
        grid = tk.Frame(self.tab_pwr, bg=BG)
        grid.pack(fill="x", padx=8)
        for i in range(INA_CHS):
            card = tk.Frame(grid, bg=CARD)
            card.grid(row=i // 4, column=i % 4, sticky="nsew", padx=4, pady=4)
            grid.columnconfigure(i % 4, weight=1)
            tk.Label(card, text=f"関節 {i} の電源", bg=CARD, fg=MUTED).pack(anchor="w", padx=10, pady=(8, 2))
            labs = {}
            for key, title, col in (("v", "電圧", VOLT_COLOR), ("a", "電流", AMP_COLOR), ("w", "電力", WATT_COLOR)):
                r = tk.Frame(card, bg=CARD)
                r.pack(fill="x", padx=10, pady=2)
                tk.Label(r, text=title, bg=CARD, fg=MUTED).pack(side="left")
                # 等幅＋固定幅。電圧・電流・電力の桁が変わっても行幅が動かない
                lab = _value_label(r, col, MONO_LG)
                lab.pack(side="right")
                labs[key] = lab
            self.ina_labs.append(labs)
        self.plot_pwr = LinePlot(self.tab_pwr, "電力 [W]", 0, 40, "W")
        self.plot_v = LinePlot(self.tab_pwr, "電圧 [V]", 0, 16, "V")
        for i in range(INA_CHS):
            col = INA_PLOT_COLORS[i % len(INA_PLOT_COLORS)]
            self.plot_pwr.add_series(f"w{i}", col)
            self.plot_v.add_series(f"v{i}", col)
        self.plot_pwr.pack(fill="both", expand=True, padx=8, pady=6)
        self.plot_v.pack(fill="both", expand=True, padx=8, pady=6)

    def _build_time(self) -> None:
        self.time_labs: dict[str, tk.Label] = {}
        card = tk.Frame(self.tab_time, bg=CARD)
        card.pack(fill="x", padx=8, pady=6)
        for key, title in (("period", "周期"), ("loop", "ループ"), ("sense", "センサ"), ("jitter", "ジッタ"), ("i2c", "I2C累計"), ("servo", "8Servos")):
            r = tk.Frame(card, bg=CARD)
            r.pack(side="left", padx=12, pady=8)
            tk.Label(r, text=title, bg=CARD, fg=MUTED).pack()
            # 各列の数値幅を固定し、周期が変わっても列が左右に揺れないようにする
            lab = _value_label(r, PERIOD_COLOR, MONO_MD, anchor="center")
            lab.pack()
            self.time_labs[key] = lab
        self.plot_time = LinePlot(self.tab_time, "時間 [ms]  灰点線＝50ms", 0, 80, "ms")
        self.plot_time.add_series("period", PERIOD_COLOR)
        self.plot_time.add_series("loop", CMD_COLOR)
        self.plot_time.add_series("sense", AS_COLOR)
        self.plot_time.add_guide(TARGET_MS, MUTED)
        self.plot_time.pack(fill="both", expand=True, padx=8, pady=4)

    def _build_evt(self) -> None:
        row = tk.Frame(self.tab_evt, bg=BG)
        row.pack(fill="x", padx=8, pady=6)
        tk.Label(row, text="データ名", bg=BG, fg=MUTED).pack(side="left")
        self.rec_name_var = tk.StringVar()
        tk.Entry(
            row, textvariable=self.rec_name_var, width=22, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat"
        ).pack(side="left", padx=6)
        tk.Button(row, text="記録開始", command=self._pc_record_start, bg=GOOD, fg=TEXT, relief="flat").pack(
            side="left"
        )
        tk.Button(row, text="記録停止", command=self._pc_record_stop, bg=CARD_HI, fg=TEXT, relief="flat").pack(
            side="left", padx=6
        )
        self.log_state = tk.Label(row, text="記録オフ（Hub からも開始可）", bg=BG, fg=MUTED)
        self.log_state.pack(side="left", padx=8)
        self.evt_text = tk.Text(
            self.tab_evt, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
            font=("Consolas", 9), wrap="none", height=18,
        )
        self.evt_text.pack(fill="both", expand=True, padx=8, pady=4)

    # ----- ポート / セッション -----
    def _refresh_ports(self) -> None:
        found = list_ports()
        self.port_list.delete(0, "end")
        for dev, desc in found:
            label = self.names.get(dev, "")
            extra = f"  [{label}]" if label else ""
            mark = " ●" if dev in self.sessions and self.sessions[dev].connected else ""
            self.port_list.insert("end", f"{dev}{extra}  {desc}{mark}")
        self._ports_raw = [p[0] for p in found]
        if self.current and self.current in self._ports_raw:
            idx = self._ports_raw.index(self.current)
            self.port_list.selection_set(idx)
        # 未接続なら、見つかった 1 台目の ATOM を開く
        self._maybe_auto_connect_first()
        self.after(2500, self._refresh_ports)

    def _select_port_in_list(self, port: str) -> None:
        """左の COM 一覧で port を選択し、current と名前欄を合わせる。"""
        self.current = port
        self.name_var.set(self.names.get(port, ""))
        if port not in self._ports_raw:
            return
        idx = self._ports_raw.index(port)
        self.port_list.selection_clear(0, "end")
        self.port_list.selection_set(idx)
        self.port_list.activate(idx)
        self.port_list.see(idx)

    def _session_opening(self) -> bool:
        """ワーカー起動中または接続済みのセッションがあるか。"""
        return any(s.worker is not None or s.connected for s in self.sessions.values())

    def _maybe_auto_connect_first(self) -> None:
        """1 台目の ATOM（VID 303A）へ自動接続する。

        起動直後や、起動時にまだ COM が見えていない場合に使う。
        手動で接続／切断したあとは再実行しない。
        """
        if self._auto_connect_done or self._session_opening():
            self._auto_connect_done = True
            return
        port = first_atom_port()
        if not port:
            return
        self._auto_connect_done = True
        self._select_port_in_list(port)
        self._ensure(port).connect()

    def _sel_port(self) -> str | None:
        sel = self.port_list.curselection()
        if not sel:
            return self.current
        idx = int(sel[0])
        if 0 <= idx < len(self._ports_raw):
            return self._ports_raw[idx]
        return self.current

    def _on_select_port(self, _evt: object = None) -> None:
        port = self._sel_port()
        if port:
            self.current = port
            self.name_var.set(self.names.get(port, ""))
            self._sync_detail()

    def _sess(self) -> AtomSession | None:
        if self.current is None:
            return None
        return self.sessions.get(self.current)

    def _ensure(self, port: str) -> AtomSession:
        if port not in self.sessions:
            s = AtomSession(port)
            s.name = self.names.get(port, "")
            self.sessions[port] = s
        return self.sessions[port]

    def _connect_sel(self) -> None:
        port = self._sel_port()
        if not port:
            return
        # 手動接続したあとは自動接続を再開しない
        self._auto_connect_done = True
        self.current = port
        self._ensure(port).connect()

    def _disconnect_sel(self) -> None:
        # 切断は意図的なので、次のポート更新で自動再接続しない
        self._auto_connect_done = True
        s = self._sess()
        if s:
            s.disconnect()

    def _connect_all(self) -> None:
        """Espressif(303A) の COM だけ開く。机の USB ハブ向け。"""
        self._auto_connect_done = True
        for p in serial.tools.list_ports.comports():
            if not is_atom_hwid(p.hwid):
                continue
            s = self._ensure(p.device)
            if not s.connected:
                s.connect()

    def _save_name(self) -> None:
        port = self._sel_port()
        if not port:
            return
        self.names[port] = self.name_var.get().strip()
        save_names(self.names)
        if port in self.sessions:
            self.sessions[port].name = self.names[port]

    def _identify(self) -> None:
        self.apply_op({"op": "identify"})

    def _scan(self) -> None:
        self.apply_op({"op": "scan"})

    def _prof_get(self) -> None:
        self.apply_op({"op": "prof_get"})

    def _prof_default(self) -> None:
        self.apply_op({"op": "prof_default"})

    @staticmethod
    def _parse_int_field(text: str) -> int:
        text = text.strip().lower()
        if text.startswith("0x"):
            return int(text, 16)
        return int(text)

    def _routes_from_form(self) -> list[JointRoute] | None:
        routes: list[JointRoute] = []
        try:
            for row in self.prof_vars:
                routes.append(
                    JointRoute(
                        enc_hub=self._parse_int_field(row["enc_hub"].get()),
                        enc_ch=self._parse_int_field(row["enc_ch"].get()),
                        enc_addr=self._parse_int_field(row["enc_addr"].get()),
                        act_hub=self._parse_int_field(row["act_hub"].get()),
                        act_ch=self._parse_int_field(row["act_ch"].get()),
                        act_addr=self._parse_int_field(row["act_addr"].get()),
                        servo_ch=self._parse_int_field(row["servo_ch"].get()),
                        ina_hub=self._parse_int_field(row["ina_hub"].get()),
                        ina_ch=self._parse_int_field(row["ina_ch"].get()),
                        ina_addr=self._parse_int_field(row["ina_addr"].get()),
                    )
                )
        except ValueError as exc:
            messagebox.showerror("プロファイル", f"数値の形式が不正です: {exc}")
            return None
        return routes

    def _foot_from_form(self) -> FootRoute | None:
        """プロファイルタブの右足経路。失敗時は None。"""
        try:
            return FootRoute(
                hub=self._parse_int_field(self.foot_vars["hub"].get()),
                ch=self._parse_int_field(self.foot_vars["ch"].get()),
                addr=self._parse_int_field(self.foot_vars["addr"].get()),
            )
        except (KeyError, ValueError) as exc:
            messagebox.showerror("プロファイル", f"足経路の数値が不正です: {exc}")
            return None

    def _foot_from_msg(self, msg: dict, fallback: FootRoute) -> FootRoute:
        """iPad の prof_put に載る foot 辞書。無ければ現状を残す。"""
        raw = msg.get("foot")
        if not isinstance(raw, dict):
            return fallback
        try:
            return FootRoute(
                hub=int(raw.get("hub", fallback.hub)),
                ch=int(raw.get("ch", fallback.ch)),
                addr=int(raw.get("addr", fallback.addr)),
            )
        except (TypeError, ValueError):
            return fallback

    def _prof_put(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        routes = self._routes_from_form()
        foot = self._foot_from_form()
        if routes is None or foot is None:
            return
        self._send_routes(s, routes, "プロファイル送信", foot=foot)

    def _prof_from_scan(self) -> None:
        """スキャン結果の AS5600 を関節 0.. に仮割当（Hub CH 順）。サーボは手前 ch=i。"""
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        as_nodes = [n for n in s.nodes if n.kind == "as5600"]
        as_nodes.sort(key=lambda n: (n.hub, n.ch))
        if not as_nodes:
            messagebox.showinfo("プロファイル", "AS5600 がスキャン結果にありません。先に SCAN してください。")
            return
        routes = default_routes()
        for i, n in enumerate(as_nodes[:JOINTS]):
            if n.hub == "root":
                hub, ch = 0, -1
            else:
                try:
                    hub = int(str(n.hub), 16)
                except ValueError:
                    hub = 0x70
                ch = n.ch
            try:
                addr = int(str(n.addr), 0) if str(n.addr).lower().startswith("0x") else int(str(n.addr), 16)
            except ValueError:
                addr = 0x36
            routes[i] = JointRoute(
                enc_hub=hub,
                enc_ch=ch,
                enc_addr=addr,
                act_hub=0,
                act_ch=-1,
                act_addr=0x25,
                servo_ch=i,
                ina_hub=routes[i].ina_hub,
                ina_ch=routes[i].ina_ch,
                ina_addr=routes[i].ina_addr,
            )
        ina_nodes = [n for n in s.nodes if n.kind == "ina226"]
        ina_nodes.sort(key=lambda n: (n.hub, n.ch))
        for i, n in enumerate(ina_nodes[:JOINTS]):
            ih, ic, ia = scan_node_path(n)
            routes[i].ina_hub = ih
            routes[i].ina_ch = ic
            routes[i].ina_addr = ia
        s.routes = routes
        foot_nodes = [n for n in s.nodes if n.kind == "foot"]
        foot = s.foot
        if foot_nodes:
            fh, fc, fa = scan_node_path(foot_nodes[0])
            foot = FootRoute(hub=fh, ch=fc, addr=fa)
        s.foot = foot
        self._fill_prof_form(routes, foot)
        s.note(
            f"SCANから仮割当  AS5600 {min(len(as_nodes), JOINTS)} 軸  "
            f"INA {min(len(ina_nodes), JOINTS)} 台  "
            f"足 {'あり' if foot_nodes else 'なし'}"
        )

    def _fill_prof_form(self, routes: list[JointRoute], foot: FootRoute | None = None) -> None:
        self._syncing = True
        try:
            for i, r in enumerate(routes[:JOINTS]):
                row = self.prof_vars[i]
                row["enc_hub"].set(f"0x{r.enc_hub:02X}" if r.enc_hub else "0")
                row["enc_ch"].set(str(r.enc_ch))
                row["enc_addr"].set(f"0x{r.enc_addr:02X}")
                row["act_hub"].set(f"0x{r.act_hub:02X}" if r.act_hub else "0")
                row["act_ch"].set(str(r.act_ch))
                row["act_addr"].set(f"0x{r.act_addr:02X}")
                row["servo_ch"].set(str(r.servo_ch))
                row["ina_hub"].set(f"0x{r.ina_hub:02X}" if r.ina_hub else "0")
                row["ina_ch"].set(str(r.ina_ch))
                row["ina_addr"].set(f"0x{r.ina_addr:02X}" if r.ina_addr else "0")
            fr = foot if foot is not None else default_foot()
            if getattr(self, "foot_vars", None):
                self.foot_vars["hub"].set(f"0x{fr.hub:02X}" if fr.hub else "0")
                self.foot_vars["ch"].set(str(fr.ch))
                self.foot_vars["addr"].set(f"0x{fr.addr:02X}" if fr.addr else "0")
        finally:
            self._syncing = False
        self._prof_sig = route_sig(routes, foot)

    def _on_mode(self, _evt: object = None) -> None:
        self.apply_op({"op": "mode", "robot": self.mode_var.get() == "robot"})

    def _toggle_out(self, panel: int) -> None:
        if self._syncing:
            return
        j = self._panel_joint(panel)
        self.apply_op({"op": "out", "ch": j, "on": bool(self.out_vars[j].get())})

    def _toggle_random(self, panel: int) -> None:
        """軸ごとのランダム ON/OFF。ON 時はすぐ次ターゲットを選ぶ。"""
        j = self._panel_joint(panel)
        self.apply_op({"op": "random", "ch": j, "on": bool(self.rand_vars[j].get())})

    def _rand_settings(self) -> tuple[float, float, float, float, float]:
        """@return (min_deg, max_deg, hold_min_s, hold_max_s, min_jump)"""
        try:
            lo = float(self.rand_min_var.get())
            hi = float(self.rand_max_var.get())
            h0 = float(self.rand_hold_min_var.get())
            h1 = float(self.rand_hold_max_var.get())
            jump = float(self.rand_jump_var.get())
        except (tk.TclError, ValueError):
            return RAND_MIN_DEG, RAND_MAX_DEG, RAND_HOLD_MIN_S, RAND_HOLD_MAX_S, RAND_MIN_JUMP_DEG
        if hi < lo:
            lo, hi = hi, lo
        lo = max(40.0, min(230.0, lo))
        hi = max(40.0, min(230.0, hi))
        if h1 < h0:
            h0, h1 = h1, h0
        h0 = max(0.1, h0)
        h1 = max(h0, h1)
        jump = max(0.0, jump)
        return lo, hi, h0, h1, jump

    def _next_random_target(self, current: float) -> float:
        lo, hi, _h0, _h1, jump = self._rand_settings()
        if hi - lo < 1.0:
            return (lo + hi) * 0.5
        target = current
        for _ in range(12):
            target = random.uniform(lo, hi)
            if abs(target - current) >= min(jump, (hi - lo) * 0.5):
                break
        return target

    def _update_random(self) -> None:
        """保持時間が切れた軸に新しい Joint 指令を送る（PC 側ランダム）。"""
        s = self._sess()
        if not s or not s.connected:
            return
        now = time.time()
        _lo, _hi, hold_min, hold_max, _jump = self._rand_settings()
        for i in range(JOINTS):
            if i >= len(self.rand_vars) or not self.rand_vars[i].get():
                continue
            if not self.out_vars[i].get():
                continue
            # 校正掃引中の軸はランダムしない
            if self._pc_cal is not None and i == self._pc_cal.ch:
                continue
            # COP 実験中は固定軸とかかとピッチをランダムから外す
            if self._cop.held and i in copctrl.HOLD_CHS:
                continue
            if (self._cop.p_on or self._cop.sweep_on or self._cop.held) and i == copctrl.HEEL_CH:
                continue
            if now < self._rand_until[i]:
                continue
            cur = float(self.cmd_vars[i].get())
            tgt = copctrl.clamp_cmd(self._next_random_target(cur))
            hold = random.uniform(hold_min, hold_max)
            self._rand_until[i] = now + hold
            self._rand_target[i] = tgt
            self._syncing = True
            try:
                self.cmd_vars[i].set(round(tgt, 1))
            finally:
                self._syncing = False
            s.send(proto.cmd_joint(i, tgt))

    def _cmd_drag(self, panel: int) -> None:
        if self._syncing:
            return
        j = self._panel_joint(panel)
        self.apply_op({"op": "joint", "ch": j, "deg": float(self.cmd_vars[j].get())})

    def _hold_all(self) -> None:
        self._pc_cal_stop("全停止", restore=False)
        self._cop_stop("全停止", clear_hold=True)
        for s in self.sessions.values():
            s.send(proto.cmd_hold())
        for v in self.out_vars:
            v.set(False)
        for v in self.rand_vars:
            v.set(False)

    def _probe(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        sel = self.tree.selection()
        if not sel:
            s.send(proto.cmd_scan())
            return
        iid = sel[0]
        # values stored as hub|ch|addr
        tags = self.tree.item(iid, "tags")
        if not tags:
            return
        meta = tags[0]
        hub, ch, addr = meta.split("|")
        if hub == "root":
            try:
                a = int(str(addr), 0) if str(addr).lower().startswith("0x") else int(str(addr), 16)
            except ValueError:
                a = 0x36
            s.send(proto.cmd_probe_root(a))
        else:
            try:
                hub_n = int(str(hub), 16)
            except ValueError:
                hub_n = 0x70
            s.send(proto.cmd_probe_hub(hub_n, int(ch)))

    def _tree_selected_node(self, s: AtomSession) -> ScanNode | None:
        sel = self.tree.selection()
        if not sel:
            return None
        tags = self.tree.item(sel[0], "tags")
        if not tags:
            return None
        hub, ch, addr = str(tags[0]).split("|")
        for n in s.nodes:
            if n.hub == hub and str(n.ch) == str(ch) and n.addr == addr:
                return n
        return None

    def _send_routes(
        self,
        s: AtomSession,
        routes: list[JointRoute],
        note: str,
        foot: FootRoute | None = None,
    ) -> None:
        s.routes = routes
        if foot is not None:
            s.foot = foot
        s.send(proto.cmd_prof_put([route_tuple(r) for r in routes], foot_tuple(s.foot)))
        self._fill_prof_form(s.routes, s.foot)
        self._ina_ui_sig = None
        self._refresh_ina_combos(s)
        s.note(note)

    def _assign_ina_from_tree(self) -> None:
        """トポロジで選んだ INA226 を指定関節の電源監視にする。"""
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        n = self._tree_selected_node(s)
        if n is None or n.kind != "ina226":
            messagebox.showinfo("INA", "トポロジで INA226 ノードを選んでください。")
            return
        joint = int(self.topo_ina_joint.get())
        if joint < 0 or joint >= JOINTS:
            return
        if joint >= len(s.routes):
            messagebox.showinfo("INA", f"このボードのプロファイルは関節 0〜{max(0, len(s.routes) - 1)} までです。")
            return
        hub, ch, addr = scan_node_path(n)
        routes = list(s.routes)
        while len(routes) < JOINTS:
            routes.append(default_routes()[len(routes)])
        routes[joint].ina_hub = hub
        routes[joint].ina_ch = ch
        routes[joint].ina_addr = addr
        self._send_routes(s, routes, f"INA 関節{joint} ← {ina_label(hub, ch, addr)}")

    def _clear_ina_from_tree(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        joint = int(self.topo_ina_joint.get())
        if joint < 0 or joint >= JOINTS:
            return
        if joint >= len(s.routes):
            messagebox.showinfo("INA", f"このボードのプロファイルは関節 0〜{max(0, len(s.routes) - 1)} までです。")
            return
        routes = list(s.routes)
        while len(routes) < JOINTS:
            routes.append(default_routes()[len(routes)])
        routes[joint].ina_hub = 0
        routes[joint].ina_ch = -1
        routes[joint].ina_addr = 0
        self._send_routes(s, routes, f"INA 関節{joint} を未割当")

    def _ina_option_list(self, s: AtomSession) -> list[str]:
        opts = ["なし"]
        seen: set[str] = set()
        for n in s.nodes:
            if n.kind != "ina226":
                continue
            hub, ch, addr = scan_node_path(n)
            lab = ina_label(hub, ch, addr)
            if lab not in seen:
                opts.append(lab)
                seen.add(lab)
        for r in s.routes[:JOINTS]:
            lab = ina_label(r.ina_hub, r.ina_ch, r.ina_addr)
            if lab not in seen:
                opts.append(lab)
                seen.add(lab)
        return opts

    def _foot_option_list(self, s: AtomSession) -> list[str]:
        """スキャンで見えた足スレーブ + 現在の割当。"""
        opts = ["なし"]
        seen: set[str] = set()
        for n in s.nodes:
            if n.kind != "foot":
                continue
            hub, ch, addr = scan_node_path(n)
            lab = ina_label(hub, ch, addr)
            if lab not in seen:
                opts.append(lab)
                seen.add(lab)
        lab = ina_label(s.foot.hub, s.foot.ch, s.foot.addr)
        if lab not in seen:
            opts.append(lab)
        return opts

    def _refresh_ina_combos(self, s: AtomSession) -> None:
        if self._syncing or not getattr(self, "ina_combos", None):
            return
        opts = self._ina_option_list(s)
        self._syncing = True
        try:
            for p in range(len(self.ina_combos)):
                j = self._panel_joint(p)
                self.ina_combos[p]["values"] = opts
                if j >= len(s.routes):
                    self.ina_sel_vars[p].set("なし")
                    continue
                want = ina_label(s.routes[j].ina_hub, s.routes[j].ina_ch, s.routes[j].ina_addr)
                if want not in opts:
                    opts2 = list(opts) + [want]
                    self.ina_combos[p]["values"] = opts2
                self.ina_sel_vars[p].set(want)
        finally:
            self._syncing = False

    def _on_ina_combo(self, panel: int) -> None:
        if self._syncing or self._pc_locked():
            return
        s = self._sess()
        j = self._panel_joint(panel)
        if not s or j >= len(s.routes):
            return
        parsed = parse_ina_label(self.ina_sel_vars[panel].get())
        if parsed is None:
            return
        hub, ch, addr = parsed
        routes = list(s.routes)
        routes[j].ina_hub = hub
        routes[j].ina_ch = ch
        routes[j].ina_addr = addr
        self._send_routes(s, routes, f"INA 関節{j} ← {ina_label(hub, ch, addr)}")

    def _toggle_auto(self) -> None:
        self.apply_op({"op": "auto_scan", "on": bool(self._auto_scan.get())})

    def _auto_loop(self) -> None:
        if self._auto_scan.get():
            s = self._sess()
            if s and s.connected:
                s.send(proto.cmd_scan())
            self._scan_job = self.after(5000, self._auto_loop)

    def _pc_record_start(self) -> None:
        """PC GUI からの本記録開始。保存先は data/recordings（ダイアログなし）。"""
        out = self._record_start(self.rec_name_var.get().strip(), "")
        if not out.get("ok", True) and out.get("error"):
            messagebox.showerror("記録", str(out["error"]))

    def _pc_record_stop(self) -> None:
        self._record_stop()

    def _on_close(self) -> None:
        self._pc_cal_stop("ツール終了", restore=False)
        self._record_stop(reason="ツール終了")
        for s in self.sessions.values():
            s.disconnect()
        self.destroy()

    # ----- 描画 -----
    def _tick(self) -> None:
        for s in self.sessions.values():
            s.pump()
            f = s.last_frame
            if f is not None:
                try:
                    lim = float(self._amp_limit.get())
                except (tk.TclError, ValueError):
                    lim = 8.0
                assigned = [i for i, r in enumerate(s.routes[:JOINTS]) if r.ina_addr]
                over = bool(assigned) and any(
                    f.ina_ok[i] and a is not None and abs(a) > lim
                    for i, a in enumerate(f.amp)
                    if i < len(s.routes) and s.routes[i].ina_addr
                )
                if over and not s.amp_tripped:
                    s.amp_tripped = True
                    self._pc_cal_stop("過電流で停止", restore=False)
                    self._cop_stop("過電流で停止", clear_hold=True)
                    s.send(proto.cmd_hold())
                    for v in self.rand_vars:
                        v.set(False)
                    for v in self.out_vars:
                        v.set(False)
                    s.note(f"PC監視 電流が {lim} A を超えた")
                elif not over:
                    s.amp_tripped = False
        self._update_random()
        self._update_pc_cal()
        self._update_cop_ctrl()
        self._sync_detail()
        self._draw_cards()
        self._m5_publish_tick()
        self.after(50, self._tick)

    def _card_text(self, s: AtomSession) -> tuple[str, str, str]:
        """カード表示用 (text, bg, fg)。"""
        bg = CARD_HI if time.time() < s.flash_until else CARD
        fg = GOOD if s.connected else BAD
        title = s.name or s.port
        f = s.last_frame
        extra = f"  {f.mode}  out={f.out_mask}" if f else ""
        if f is not None and f.foot_ok:
            extra += f"  足 {sum(f.foot_mv)}mV"
        text = f"{title}\n{s.port}  {'接続' if s.connected else '切断'}{extra}"
        return text, bg, fg

    def _draw_cards(self) -> None:
        # 毎 tick の destroy/再生成は Tk を詰まらせキュー溢れの原因になるので、構成が変わったときだけ作る。
        ports = tuple(self.sessions.keys())
        if getattr(self, "_card_ports", None) != ports or not getattr(self, "_card_labs", None):
            for w in self.card_host.winfo_children():
                w.destroy()
            self._card_labs = {}
            self._card_ports = ports
            for port, s in self.sessions.items():
                text, bg, fg = self._card_text(s)
                lab = tk.Label(
                    self.card_host,
                    text=text,
                    bg=bg, fg=fg, justify="left", anchor="w",
                )
                lab.pack(fill="x", pady=3)
                lab.bind("<Button-1>", lambda _e, p=port: self._click_card(p))
                self._card_labs[port] = lab
            return
        for port, s in self.sessions.items():
            lab = self._card_labs.get(port)
            if lab is None:
                continue
            text, bg, fg = self._card_text(s)
            lab.configure(text=text, bg=bg, fg=fg)

    def _click_card(self, port: str) -> None:
        self.current = port
        if port in getattr(self, "_ports_raw", []):
            self.port_list.selection_clear(0, "end")
            self.port_list.selection_set(self._ports_raw.index(port))
        self.name_var.set(self.names.get(port, ""))
        self._sync_detail()

    def _sync_detail(self) -> None:
        s = self._sess()
        if s is None:
            self.sel_label.configure(text="未選択")
            self.hello_label.configure(text="")
            return
        title = s.name or s.port
        self.sel_label.configure(text=title)
        self.hello_label.configure(text=s.hello)
        if s.mode in ("lab", "robot") and self.mode_var.get() != s.mode:
            self.mode_var.set(s.mode)
        self._fill_tree(s)
        if self._prof_sig != route_sig(s.routes, s.foot):
            self._fill_prof_form(s.routes, s.foot)
        ina_sig = (tuple(self._ina_option_list(s)), route_sig(s.routes, s.foot))
        if ina_sig != getattr(self, "_ina_ui_sig", None):
            self._ina_ui_sig = ina_sig
            self._refresh_ina_combos(s)
        f = s.last_frame
        if f is not None:
            self._apply_frame(s, f)
        if getattr(self, "cal_status_lab", None) is not None:
            ui_sig = (s.cal_status, s.map_ch, len(s.map_points))
            if ui_sig != getattr(self, "_cal_ui_sig", None):
                self._cal_ui_sig = ui_sig
                self._refresh_cal_labels(s)
        sig = s.events[0] if s.events else ""
        if sig != self._evt_sig:
            self._evt_sig = sig
            lines = "\n".join(s.events)
            self.evt_text.delete("1.0", "end")
            self.evt_text.insert("1.0", lines)

    def _fill_tree(self, s: AtomSession) -> None:
        sig = (s.port, tuple((n.hub, n.ch, n.addr, n.kind, n.mag, n.agc) for n in s.nodes))
        if sig == self._tree_sig:
            return
        self._tree_sig = sig
        self.tree.delete(*self.tree.get_children())
        root_id = self.tree.insert("", "end", text=f"{s.port}  Grove I2C", values=("", "", ""))
        hubs: dict[str, str] = {}
        for n in s.nodes:
            mag = MAG_LABEL.get(n.mag, str(n.mag)) if n.kind == "as5600" else ""
            agc = "" if n.agc == 255 else str(n.agc)
            tag = f"{n.hub}|{n.ch}|{n.addr}"
            if n.hub == "root":
                if n.kind == "pahub":
                    hid = self.tree.insert(
                        root_id, "end", text=f"PaHub {n.addr}",
                        values=(n.kind, "", ""), tags=(tag,),
                    )
                    hubs[n.addr.replace("0x", "").replace("0X", "").upper()] = hid
                    hubs[n.addr] = hid
                else:
                    self.tree.insert(
                        root_id, "end", text=n.addr,
                        values=(n.kind, mag, agc), tags=(tag,),
                    )
            else:
                parent = hubs.get(n.hub.upper()) or hubs.get(n.hub) or root_id
                self.tree.insert(
                    parent, "end", text=f"CH{n.ch}  {n.addr}",
                    values=(n.kind, mag, agc), tags=(tag,),
                )
        self.tree.item(root_id, open=True)
        for hid in hubs.values():
            try:
                self.tree.item(hid, open=True)
            except tk.TclError:
                pass

    def _fill_joint_panel(self, f: Frame, panel: int) -> None:
        """1 枚の関節パネルを、選択中の論理関節のテレメトリで更新する。"""
        if panel < 0 or panel >= len(self.joint_labs):
            return
        j = self._panel_joint(panel)
        labs = self.joint_labs[panel]
        cmd = at(f.cmd, j)
        raw = at(f.raw, j)
        unw = at(f.unwrap, j)
        corr = at(f.corr, j)
        mag = at(f.mag, j, 255)
        agc = at(f.agc, j, 255)
        volt = at(f.volt, j)
        amp = at(f.amp, j)
        watt = at(f.watt, j)
        labs["cmd"].configure(text=fmt(cmd, "°"))
        labs["raw"].configure(text=fmt(raw, "°"))
        labs["unw"].configure(text=fmt(unw, "°"))
        labs["corr"].configure(text=fmt(corr, "°"), fg=CORR_COLOR)
        labs["mag"].configure(text=MAG_LABEL.get(mag, str(mag)), fg=mag_color(mag))
        labs["agc"].configure(text="—" if agc == 255 else f"{agc:3d}")
        labs["v"].configure(text=fmt(volt, "V"))
        labs["a"].configure(text=fmt(amp, "A"))
        labs["w"].configure(text=fmt(watt, "W"))

    def _apply_frame(self, s: AtomSession, f: Frame) -> None:
        # out_vars はユーザー操作の意図。テレメトリの out_mask で上書きするとチェックが勝手に外れる。
        for p in range(len(self.joint_labs)):
            self._fill_joint_panel(f, p)

        # チェック ON なのにボード側がオフなら、短周期で再送（校正終了・取りこぼし対策）
        # 校正掃引中は PC が PWM を握るので再送しない
        now = time.time()
        if self._pc_cal is None and now - self._last_out_reassert >= 0.4:
            resent = False
            for i in range(JOINTS):
                if self.out_vars[i].get() and not (f.out_mask & (1 << i)):
                    s.send(proto.cmd_out(i, True))
                    s.send(proto.cmd_joint(i, float(self.cmd_vars[i].get())))
                    resent = True
            if resent:
                self._last_out_reassert = now

        for i in range(INA_CHS):
            self.ina_labs[i]["v"].configure(text=fmt(f.volt[i], "V"))
            self.ina_labs[i]["a"].configure(text=fmt(f.amp[i], "A"))
            self.ina_labs[i]["w"].configure(text=fmt(f.watt[i], "W"))
        self.time_labs["period"].configure(text=fmt_ms(f.period_us))
        self.time_labs["loop"].configure(text=fmt_ms(f.loop_us))
        self.time_labs["sense"].configure(text=fmt_ms(f.sense_us))
        self.time_labs["jitter"].configure(text=fmt_ms(f.jitter_us))
        self.time_labs["i2c"].configure(text=f"{f.i2c_err:6d}")
        self.time_labs["servo"].configure(text="OK" if f.servo_ok else "なし", fg=GOOD if f.servo_ok else BAD)

        if self._plot_port != s.port:
            self.plot_ang.clear()
            self.plot_pwr.clear()
            self.plot_v.clear()
            self.plot_time.clear()
            self._plot_port = s.port
            self._last_plot_seq = None

        if self._last_plot_seq != (s.port, f.seq):
            self._last_plot_seq = (s.port, f.seq)
            j = self._plot_joint_index()
            self.plot_ang.push("cmd", f.t, at(f.cmd, j))
            self.plot_ang.push("raw", f.t, at(f.raw, j))
            self.plot_ang.push("unw", f.t, at(f.unwrap, j))
            self.plot_ang.push("corr", f.t, at(f.corr, j))
            self.plot_ang.push("v", f.t, at(f.volt, j))
            self.plot_ang.push("a", f.t, at(f.amp, j))
            self.plot_ang.push("w", f.t, at(f.watt, j))
            for i in range(INA_CHS):
                self.plot_pwr.push(f"w{i}", f.t, at(f.watt, i))
                self.plot_v.push(f"v{i}", f.t, at(f.volt, i))
            self.plot_time.push("period", f.t, f.period_us / 1000.0)
            self.plot_time.push("loop", f.t, f.loop_us / 1000.0)
            self.plot_time.push("sense", f.t, f.sense_us / 1000.0)

        if now - self._last_plot < PLOT_INTERVAL_S:
            return
        self._last_plot = now
        self.plot_ang.redraw()
        self.plot_pwr.redraw()
        self.plot_v.redraw()
        self.plot_time.redraw()

