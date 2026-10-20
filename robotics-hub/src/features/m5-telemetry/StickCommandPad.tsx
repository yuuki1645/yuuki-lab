import type { M5Stick } from "./types";

type Props = {
  stick: M5Stick;
};

function clampUnit(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(-1, value));
}

/**
 * 歩行再生の左スティック。
 * 円の点は指の位置（奥が上）。横棒は方策が受け取っている前進だけ。
 * 手前と左右は点は動いても、横棒は 0 のまま。
 */
export function StickCommandPad({ stick }: Props) {
  const x = clampUnit(stick.x);
  const y = clampUnit(stick.y);
  const dead = Math.min(0.95, Math.max(0, Number(stick.dead_zone) || 0));
  const maxVx = stick.max_vx > 1e-6 ? stick.max_vx : 0.2;
  const vx = Math.min(maxVx, Math.max(0, Number(stick.vx) || 0));
  const radius = 78;
  const center = 96;
  const travel = radius - 10;
  const dotX = center + x * travel;
  const dotY = center - y * travel;
  const deadR = dead * travel;
  const filled = (vx / maxVx) * 100;
  const pulled = y < -dead;
  const sideways = Math.abs(x) > dead;

  return (
    <section className="m5-stick" aria-label="左スティックの操作">
      <header className="m5-stick__head">
        <h2>左スティック</h2>
        <p>点は指の位置。棒は方策への前進です。</p>
      </header>
      <div className="m5-stick__body">
        <svg className="m5-stick__pad" viewBox="0 0 192 192" role="img" aria-hidden="true">
          <circle className="m5-stick__well" cx={center} cy={center} r={radius} />
          <circle className="m5-stick__dead" cx={center} cy={center} r={deadR} />
          <line className="m5-stick__axis" x1={center} y1={center - radius} x2={center} y2={center + radius} />
          <line className="m5-stick__axis" x1={center - radius} y1={center} x2={center + radius} y2={center} />
          <text className="m5-stick__cap" x={center} y={16} textAnchor="middle">
            奥
          </text>
          <text className="m5-stick__cap" x={center} y={186} textAnchor="middle">
            手前
          </text>
          <circle className="m5-stick__dot" cx={dotX} cy={dotY} r={8} />
        </svg>
        <div className="m5-stick__readout">
          <div className="m5-stick__vx-label">方策への前進</div>
          <div className="m5-stick__vx-value">
            {vx.toFixed(2)}
            <span> / {maxVx.toFixed(2)} m/s</span>
          </div>
          <div className="m5-stick__track" aria-hidden="true">
            <div className="m5-stick__fill" style={{ width: `${filled}%` }} />
          </div>
          <p className="m5-stick__note">
            {[
              pulled ? "手前に倒しています。方策へは 0 です。" : null,
              sideways ? "左右は方策へ渡しません。" : null,
              !pulled && !sideways && vx <= 1e-4 ? "中央です。方策へは 0 です。" : null,
              !pulled && !sideways && vx > 1e-4 ? "奥への倒し量が、この前進です。" : null,
            ]
              .filter((line) => line)
              .join(" ")}
          </p>
        </div>
      </div>
    </section>
  );
}
