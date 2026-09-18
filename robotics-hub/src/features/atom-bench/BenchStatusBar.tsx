/**
 * 机上ラボの固定ステータスバー。
 *
 * 画面下に張り付き、20 Hz のフレームが来るたびに更新する。
 * 「いまボードと何が繋がっていて、何が動いていて、どこが壊れているか」だけを載せる。
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { UiHelp } from "@/shared/components/UiHelp";
import { at } from "@/features/m5-telemetry/m5Widgets";
import { MAG_LABEL, type M5Control, type M5Frame, type M5Status } from "@/features/m5-telemetry/types";
import type { M5WsStatus } from "@/features/m5-telemetry/useM5TelemetryStream";

type Props = {
  wsStatus: M5WsStatus;
  status: M5Status | null;
  frame: M5Frame | null;
  control: M5Control | null;
  /** いま机上で触っている軸 */
  ch: number;
};

/** 1 秒あたりの増分。フレームの seq と i2c_err から出す */
type Rates = { fps: number; i2cPerSec: number };

function useRates(frame: M5Frame | null): Rates {
  const [rates, setRates] = useState<Rates>({ fps: 0, i2cPerSec: 0 });
  const last = useRef<{ t: number; seq: number; err: number } | null>(null);

  useEffect(() => {
    if (!frame) {
      last.current = null;
      setRates({ fps: 0, i2cPerSec: 0 });
      return;
    }
    const now = performance.now();
    const prev = last.current;
    if (!prev) {
      last.current = { t: now, seq: frame.seq, err: frame.i2c_err };
      return;
    }
    const dt = (now - prev.t) / 1000;
    if (dt < 0.5) {
      return;
    }
    // seq / i2c_err はボード側の累計。巻き戻り（再起動・16bit 折返し）は 0 扱い
    const dSeq = Math.max(0, frame.seq - prev.seq);
    const dErr = Math.max(0, frame.i2c_err - prev.err);
    last.current = { t: now, seq: frame.seq, err: frame.i2c_err };
    setRates({ fps: dSeq / dt, i2cPerSec: dErr / dt });
  }, [frame]);

  // フレームが途切れたら古い Hz を出し続けないよう 0 に落とす
  useEffect(() => {
    const timer = window.setInterval(() => {
      const prev = last.current;
      if (!prev || performance.now() - prev.t < 1500) return;
      setRates((r) => (r.fps === 0 && r.i2cPerSec === 0 ? r : { fps: 0, i2cPerSec: 0 }));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  return rates;
}

function num(v: number | null | undefined, frac: number, unit: string): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return `—${unit}`;
  return `${v.toFixed(frac)}${unit}`;
}

function ms(us: number | null | undefined): string {
  if (typeof us !== "number" || !Number.isFinite(us)) return "—ms";
  return `${(us / 1000).toFixed(1)}ms`;
}

/** out_mask の立っているビットを ch 名で並べる */
function outList(control: M5Control | null): string {
  const on = (control?.out ?? []).map((v, i) => (v ? i : -1)).filter((i) => i >= 0);
  return on.length ? on.map((i) => `ch${i}`).join(" ") : "なし";
}

/**
 * NVS blob "en" を PUT 後に readback してから ProfOk を返す版。
 * これ未満は RAM だけ変わり、抜き差しで無効化が消える。
 * atom-rt の kUsbFwVer / FW_VER と揃える。
 */
const USB_FW_EN_MASK = 13;

/** HELLO の fw_ver（status.fw_ver）。有効マスクは 13 以上、いまの正本は 14 */
function usbFwVer(status: M5Status | null): number | null {
  const n = status?.fw_ver;
  if (typeof n === "number" && n > 0) return n;
  const m = /ver=(\d+)/.exec(status?.hello ?? "");
  if (!m) return null;
  const v = Number(m[1]);
  return Number.isFinite(v) && v > 0 ? v : null;
}

export function BenchStatusBar({ wsStatus, status, frame, control, ch }: Props) {
  const { fps, i2cPerSec } = useRates(frame);

  const linked = wsStatus === "connected";
  const atomOk = Boolean(status?.connected);
  // 切断後に残った HELLO 文字列で版を出し続けない
  const fwVer = atomOk ? usbFwVer(status) : null;
  const fwOk = fwVer != null && fwVer >= USB_FW_EN_MASK;
  const isRobot = status?.mode === "robot";
  const pwmOn = Boolean(at(control?.out, ch));
  const encOk = Boolean(at(frame?.as_ok, ch));
  const inaOk = Boolean(at(frame?.ina_ok, ch));
  const magCode = at(frame?.mag, ch) ?? 255;
  const anyPwm = (control?.out ?? []).some(Boolean);

  return (
    <footer className="bench-sb" aria-label="机上ラボ ステータス">
      <Cell
        label="ブリッジ"
        help="Hub と lab_debug.py の Socket.IO（既定 :8794）です。ブラウザは ATOM の COM を直接開きません。ここが切れていると、ボードが動いていても画面の値は止まります。"
      >
        <Dot tone={linked ? "ok" : "bad"} pulse={linked} />
        <b>{linked ? "接続" : wsStatus === "connecting" ? "接続中" : "切断"}</b>
      </Cell>

      <Cell
        label="ATOM"
        help="Python が掴んでいる仮想 COM です。未接続ならボードの電源・データ線のあるケーブル・lab_debug.py が起動しているかを見てください。COM は 1 プロセス専有です。"
      >
        <Dot tone={atomOk ? "ok" : "bad"} />
        <b>{atomOk ? status?.name || status?.port || "接続" : "未接続"}</b>
      </Cell>

      <Cell
        label="USB"
        help="HELLO で届くプロトコル番号です。関節の有効マスクは ver 13 以上、いまの正本は 14 です。「要更新」ならファームと Python の FW_VER を揃えて焼き直してください。"
      >
        <Dot tone={!atomOk ? "idle" : fwOk ? "ok" : fwVer != null ? "warn" : "idle"} />
        <b className={"bench-sb__val" + (atomOk && fwVer != null && !fwOk ? " bench-sb__hot" : "")}>
          {fwVer != null ? `ver ${fwVer}` : "—"}
        </b>
        <span className="bench-sb__sub">
          {!atomOk ? "未接続" : fwVer == null ? "未受信" : fwOk ? "rt-usb" : "要更新"}
        </span>
      </Cell>

      <Cell
        label="モード"
        help="Lab は机上用で、PWM は明示するまで出ません。Robot は全軸オンで 135° に保持します。机では Lab に戻してください。rt_monitor.py は開くだけで Robot になります。"
      >
        <b className={isRobot ? "bench-sb__hot" : "bench-sb__cool"}>{status?.mode || "—"}</b>
      </Cell>

      <Cell
        label="PWM"
        help="選択中の軸にパルスが出ているかです。右の「出力」は out_mask でオンの軸です。プロファイルで無効にした軸には出ません。黄色の点はどこかの軸が動いている印です。"
      >
        <Dot tone={anyPwm ? "warn" : "idle"} pulse={anyPwm} />
        <b className={pwmOn ? "bench-sb__hot" : ""}>{pwmOn ? `ch${ch} ON` : "OFF"}</b>
        <span className="bench-sb__sub">出力 {outList(control)}</span>
      </Cell>

      <Cell
        label={`ch${ch} 指令`}
        help="ファームへ送っている指令角です。下の「補正」は校正マップを通したあとの角で、マップが無いときは指令と同じか欠測です。机上ラボは 40〜230° を通します。"
      >
        <b className="bench-sb__val">{num(at(control?.cmd, ch), 1, "°")}</b>
        <span className="bench-sb__sub">補正 {num(at(frame?.corr, ch), 1, "°")}</span>
      </Cell>

      <Cell
        label="AS5600"
        help="エンコーダの生角（0〜360°）と磁石 STATUS です。なし・遠い・弱いときは磁石の向きと隙間を見てください。関節が無効、または経路のアドレスが 0 なら読みに行きません。"
      >
        <Dot tone={encOk ? "ok" : "idle"} />
        <b className="bench-sb__val">{num(at(frame?.raw, ch), 1, "°")}</b>
        <span className="bench-sb__sub">{MAG_LABEL[magCode] ?? String(magCode)}</span>
      </Cell>

      <Cell
        label="電源"
        help="この軸に割り当てた INA226 の電圧・電流・電力です。欠測は未配線か、有効オフか、割当が「なし」です。約 8 A を超えるとファームが全 PWM を止めます。"
      >
        <Dot tone={inaOk ? "ok" : "idle"} />
        <b className="bench-sb__val">{num(at(frame?.volt, ch), 2, "V")}</b>
        <span className="bench-sb__sub">
          {num(at(frame?.amp, ch), 2, "A")} / {num(at(frame?.watt, ch), 1, "W")}
        </span>
      </Cell>

      <Cell
        label="周期"
        help="制御ループの周期です。20 Hz なら約 50 ms。loop が period に近づくと overrun します。自動 SCAN や欠測デバイスのリトライで伸びます。"
      >
        <b className="bench-sb__val">{ms(frame?.period_us)}</b>
        <span className="bench-sb__sub">
          loop {ms(frame?.loop_us)} / {fps ? `${fps.toFixed(1)}Hz` : "—Hz"}
        </span>
      </Cell>

      <Cell
        label="I2C err"
        help="ボード起動からの I2C 失敗累計です。+N/s が赤いときは、有効なのに応答しないデバイスを毎周期叩いています。机ならプロファイルでその軸を無効にしてください。"
      >
        <Dot tone={i2cPerSec > 0 ? "bad" : "ok"} pulse={i2cPerSec > 0} />
        <b className={"bench-sb__val" + (i2cPerSec > 0 ? " bench-sb__hot" : "")}>
          {frame ? frame.i2c_err : "—"}
        </b>
        <span className="bench-sb__sub">{i2cPerSec > 0 ? `+${i2cPerSec.toFixed(0)}/s` : "増加なし"}</span>
      </Cell>

      <Cell
        label="8Servos"
        help="Grove 直結の Unit 8Servos（既定 0x25）です。なしなら PWM は出せません。seq はテレメトリの連番。overrun は 20 Hz 周期を超過した印です。"
      >
        <Dot tone={frame?.servo_ok ? "ok" : "bad"} />
        <b>{frame?.servo_ok ? "OK" : "なし"}</b>
        <span className="bench-sb__sub">{frame?.overrun ? "overrun" : `seq ${frame?.seq ?? "—"}`}</span>
      </Cell>
    </footer>
  );
}

function Cell({ label, help, children }: { label: string; help: string; children: ReactNode }) {
  return (
    <div className="bench-sb__cell">
      <span className="bench-sb__lab">
        {label}
        <UiHelp title={label} placement="top" size="sm" wide>
          {help}
        </UiHelp>
      </span>
      <span className="bench-sb__body">{children}</span>
    </div>
  );
}

function Dot({ tone, pulse }: { tone: "ok" | "warn" | "bad" | "idle"; pulse?: boolean }) {
  return (
    <i
      className={"bench-sb__dot bench-sb__dot--" + tone + (pulse ? " bench-sb__dot--pulse" : "")}
      aria-hidden="true"
    />
  );
}
