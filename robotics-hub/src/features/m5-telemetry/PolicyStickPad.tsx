import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  POLICY_ENVELOPE_VX,
  POLICY_STICK_DEAD_ZONE,
  POLICY_STICK_MAX_VX,
  policyStickCommand,
  quantizePolicyVx,
} from "./policyStick";

type Props = {
  /** 方策が入っていて、実機へ指令を出せるときだけ倒せる。 */
  armed: boolean;
  /** 量化した前進。指を離すと 0。 */
  onVx: (vx: number) => void;
};

/**
 * 実機テレメトリの右下。右手の親指で、シミュの左スティックと同じ前進を出す。
 * 再生の StickCommandPad は表示専用のまま。こちらは触って速度を送る。
 */
export function PolicyStickPad({ armed, onVx }: Props) {
  const padRef = useRef<HTMLDivElement | null>(null);
  const pointerRef = useRef<number | null>(null);
  const sentRef = useRef(0);
  const onVxRef = useRef(onVx);
  onVxRef.current = onVx;
  const [place, setPlace] = useState({ x: 0, y: 0 });

  const sendVx = (vx: number) => {
    const next = quantizePolicyVx(vx);
    if (Math.abs(next - sentRef.current) < 0.005) return;
    sentRef.current = next;
    onVxRef.current(next);
  };

  const release = () => {
    pointerRef.current = null;
    setPlace({ x: 0, y: 0 });
    sendVx(0);
  };

  // 方策を切る、再生に入る、実機が切れる。点を中央へ戻し、まだ出ている前進は 0 にする。
  // 方策がすでに切れているときは、橋がこの 0 を無視する。
  useEffect(() => {
    if (armed) return;
    pointerRef.current = null;
    setPlace({ x: 0, y: 0 });
    if (sentRef.current <= 0) return;
    sentRef.current = 0;
    onVxRef.current(0);
  }, [armed]);

  // 画面を隠す、閉じる、この部品が外れるときは、倒したままにしない。
  useEffect(() => {
    const drop = () => {
      if (sentRef.current <= 0) return;
      pointerRef.current = null;
      setPlace({ x: 0, y: 0 });
      sendVx(0);
    };
    const onHide = () => {
      if (document.visibilityState === "hidden") drop();
    };
    window.addEventListener("pagehide", drop);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      window.removeEventListener("pagehide", drop);
      document.removeEventListener("visibilitychange", onHide);
      drop();
    };
  }, []);

  const moveTo = (event: ReactPointerEvent<HTMLDivElement>) => {
    const pad = padRef.current;
    if (!pad) return;
    const rect = pad.getBoundingClientRect();
    const radius = rect.width / 2;
    if (radius < 1) return;
    let x = (event.clientX - (rect.left + radius)) / radius;
    let y = (rect.top + radius - event.clientY) / radius;
    const mag = Math.hypot(x, y);
    if (mag > 1) {
      x /= mag;
      y /= mag;
    }
    setPlace({ x, y });
    sendVx(policyStickCommand(x, y).vx);
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!armed || pointerRef.current !== null) return;
    event.preventDefault();
    pointerRef.current = event.pointerId;
    event.currentTarget.setPointerCapture(event.pointerId);
    moveTo(event);
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!armed || pointerRef.current !== event.pointerId) return;
    event.preventDefault();
    moveTo(event);
  };

  const onPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (pointerRef.current !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    release();
  };

  const command = policyStickCommand(place.x, place.y);
  const travel = 58;
  const dotX = 72 + command.x * travel;
  const dotY = 72 - command.y * travel;
  const deadR = POLICY_STICK_DEAD_ZONE * travel;
  let note = "方策を入れると、奥への倒しが前進になります。";
  if (armed && command.envelopeOff) {
    note = "包絡は外れています。指を離すと戻ります。";
  } else if (armed && command.vx > 1e-4) {
    note = "包絡はオンです。0.02 m/s を超えると外れます。";
  } else if (armed) {
    note = "中央です。奥だけが前進、手前と左右は 0 です。";
  }

  return (
    <section
      className={"m5-policy-stick" + (command.envelopeOff ? " m5-policy-stick--open" : "")}
      aria-label="前進スティック"
    >
      <div
        ref={padRef}
        className={"m5-policy-stick__pad" + (armed ? "" : " m5-policy-stick__pad--off")}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <svg viewBox="0 0 144 144" role="img" aria-hidden="true">
          <circle className="m5-policy-stick__well" cx={72} cy={72} r={68} />
          <circle className="m5-policy-stick__dead" cx={72} cy={72} r={deadR} />
          <text className="m5-policy-stick__cap" x={72} y={16} textAnchor="middle">
            奥
          </text>
          <circle className="m5-policy-stick__dot" cx={dotX} cy={dotY} r={10} />
        </svg>
      </div>
      <p className="m5-policy-stick__vx">
        {command.vx.toFixed(2)}
        <span> / {POLICY_STICK_MAX_VX.toFixed(2)} m/s</span>
      </p>
      <p className="m5-policy-stick__note">{note}</p>
      <p className="m5-policy-stick__limit">包絡 {POLICY_ENVELOPE_VX.toFixed(2)} m/s まで</p>
    </section>
  );
}
