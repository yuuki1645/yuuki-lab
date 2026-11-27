import type { M5Frame, M5PolicyObs } from "./types";
import { LEG_ROWS, isSm105Channel, jointAngleWindow, legJoint } from "./rightLeg";

type Props = {
  frame: M5Frame;
};

/** 体座標の水平成分を、円の縁まで使う傾きの大きさ。1 なら真横。 */
const GRAVITY_RIM = 1;
/** 角速度バーの端。歩き始めの揺れが見える幅。 */
const ANG_FULL_SCALE = 2;
/** この範囲なら、画面上は直立とみなす。 */
const UPRIGHT_DEG = 0.5;

function num(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

function fmtDeg(value: number | null): string {
  if (value == null) return "—";
  const text = `${Math.abs(value).toFixed(1)}°`;
  return value < 0 ? `−${text}` : text;
}

function fmtSigned(value: number | null, digits: number): string {
  if (value == null) return "—";
  const text = Math.abs(value).toFixed(digits);
  if (value > 0) return `+${text}`;
  if (value < 0) return `−${text}`;
  return text;
}

function at(values: Array<number | null> | undefined, index: number): number | null {
  if (!values || index < 0 || index >= values.length) return null;
  return num(values[index]);
}

/**
 * 方策の 0 rad は、橋がすでに画面の度へ直して cmd / corr に入れている。
 * RDS51150 の直立は 135°、SM105BL の直立は 0°。ここでは足し引きしない。
 */
function fromNeutral(ch: number, deg: number | null): string {
  if (deg == null) return "—";
  const delta = deg - jointAngleWindow(ch).neutral;
  if (Math.abs(delta) < 0.05) return "直立";
  const sign = delta > 0 ? "+" : "−";
  return `直立 ${sign}${Math.abs(delta).toFixed(1)}°`;
}

function upright(ch: number, deg: number | null): boolean {
  if (deg == null) return false;
  return Math.abs(deg - jointAngleWindow(ch).neutral) <= UPRIGHT_DEG;
}

/**
 * 歩行再生で、方策が見ている量を脚タブに出す。
 * 関節のプラスは画面のバーと同じ。股ロールは外側、股ピッチは前、
 * ひざは後ろ、かかとピッチはつま先を上げる、かかとロールは内側が下がる。
 */
export function PolicyObservePanel({ frame }: Props) {
  const policy = frame.policy;
  if (!policy) return null;
  return (
    <section className="m5-pol" aria-label="方策が見ている観測">
      <header className="m5-pol__head">
        <h2>方策が見ている量</h2>
        <p>
          体の前が +x、左が +y、上が +z です。関節は方策の中では直立が 0 rad
          で、画面では RDS51150 を 135°、ひざとかかとピッチを 0° にしています。プラスの向きは関節バーと同じです。
        </p>
      </header>
      <div className="m5-pol__grid">
        <GravityCard policy={policy} />
        <AngVelCard policy={policy} />
        <PhaseCard policy={policy} />
        <TargetCard frame={frame} policy={policy} />
      </div>
    </section>
  );
}

function GravityCard({ policy }: { policy: M5PolicyObs }) {
  const gx = num(policy.gravity[0]) ?? 0;
  const gy = num(policy.gravity[1]) ?? 0;
  const gz = num(policy.gravity[2]);
  const radius = 62;
  const center = 78;
  // 点は、体から見た重力の水平成分。前が上、左が左。縁が真横。
  const reach = radius - 8;
  const flat = Math.hypot(gx, gy);
  const limit = flat > GRAVITY_RIM ? GRAVITY_RIM / flat : 1;
  const dotX = center - gy * limit * reach;
  const dotY = center - gx * limit * reach;
  const level =
    gz != null && gz < -0.95 && Math.abs(gx) < 0.05 && Math.abs(gy) < 0.05
      ? "直立です。z が約 −1 です。"
      : "中心から外れているほど、その向きへ傾いています。";
  return (
    <article className="m5-pol__card" aria-label="IMU の重力">
      <h3>IMU 重力</h3>
      <div className="m5-pol__split">
        <svg className="m5-pol__dial" viewBox="0 0 156 156" role="img" aria-hidden="true">
          <circle className="m5-pol__well" cx={center} cy={center} r={radius} />
          <line className="m5-pol__axis" x1={center} y1={center - radius} x2={center} y2={center + radius} />
          <line className="m5-pol__axis" x1={center - radius} y1={center} x2={center + radius} y2={center} />
          <text className="m5-pol__cap" x={center} y={12} textAnchor="middle">
            前 +x
          </text>
          <text className="m5-pol__cap" x={14} y={center + 4} textAnchor="start">
            左
          </text>
          <circle className="m5-pol__dot" cx={dotX} cy={dotY} r={7} />
        </svg>
        <dl className="m5-pol__nums">
          <div>
            <dt>x 前</dt>
            <dd>{fmtSigned(num(policy.gravity[0]), 2)}</dd>
          </div>
          <div>
            <dt>y 左</dt>
            <dd>{fmtSigned(num(policy.gravity[1]), 2)}</dd>
          </div>
          <div>
            <dt>z 上</dt>
            <dd>{fmtSigned(gz, 2)}</dd>
          </div>
        </dl>
      </div>
      <p className="m5-pol__note">{level}</p>
    </article>
  );
}

function AngVelCard({ policy }: { policy: M5PolicyObs }) {
  const axes = [
    { key: "x", label: "ロール x" },
    { key: "y", label: "ピッチ y" },
    { key: "z", label: "ヨー z" },
  ] as const;
  const still = policy.ang_vel.every((value) => {
    const v = num(value);
    return v != null && Math.abs(v) < 0.05;
  });
  return (
    <article className="m5-pol__card" aria-label="角速度">
      <h3>角速度</h3>
      <ul className="m5-pol__rates">
        {axes.map((axis, index) => {
          const value = num(policy.ang_vel[index]);
          const fraction = value == null ? 0 : Math.max(-1, Math.min(1, value / ANG_FULL_SCALE));
          return (
            <li key={axis.key}>
              <span className="m5-pol__rate-name">{axis.label}</span>
              <span className="m5-pol__rate-track" aria-hidden="true">
                <span className="m5-pol__rate-zero" />
                <span
                  className="m5-pol__rate-fill"
                  style={{
                    left: fraction >= 0 ? "50%" : `${50 + fraction * 50}%`,
                    width: `${Math.abs(fraction) * 50}%`,
                  }}
                />
              </span>
              <span className="m5-pol__rate-value">{fmtSigned(value, 2)}</span>
            </li>
          );
        })}
      </ul>
      <p className="m5-pol__note">
        {still ? "ほぼ止まっています。" : "単位は rad/s。軸は重力と同じ体座標です。"}
      </p>
    </article>
  );
}

function PhaseCard({ policy }: { policy: M5PolicyObs }) {
  const s = num(policy.phase_sin) ?? 0;
  const c = num(policy.phase_cos) ?? 1;
  const radius = 62;
  const center = 78;
  const reach = radius - 10;
  // 周期の 0 を上に置く。sin が正へ進むと、点は右へ回る。
  const dotX = center + s * reach;
  const dotY = center - c * reach;
  const cycle = (Math.atan2(s, c) * 180) / Math.PI;
  const cycleDeg = (cycle + 360) % 360;
  const vx = num(policy.vx);
  const yaw = num(policy.yaw);
  const standing = vx != null && yaw != null && Math.abs(vx) < 0.01 && Math.abs(yaw) < 0.01;
  return (
    <article className="m5-pol__card" aria-label="歩行位相と速度指令">
      <h3>歩行位相</h3>
      <div className="m5-pol__split">
        <svg className="m5-pol__dial" viewBox="0 0 156 156" role="img" aria-hidden="true">
          <circle className="m5-pol__well" cx={center} cy={center} r={radius} />
          <text className="m5-pol__cap" x={center} y={14} textAnchor="middle">
            0
          </text>
          <circle className="m5-pol__dot m5-pol__dot--phase" cx={dotX} cy={dotY} r={7} />
        </svg>
        <dl className="m5-pol__nums">
          <div>
            <dt>周期の位置</dt>
            <dd>{cycleDeg.toFixed(0)}°</dd>
          </div>
          <div>
            <dt>sin</dt>
            <dd>{fmtSigned(num(policy.phase_sin), 2)}</dd>
          </div>
          <div>
            <dt>cos</dt>
            <dd>{fmtSigned(num(policy.phase_cos), 2)}</dd>
          </div>
        </dl>
      </div>
      <p className="m5-pol__note">
        1 周 {num(policy.period_s)?.toFixed(1) ?? "—"} 秒。この角度はサーボの度ではありません。
      </p>
      <h3 className="m5-pol__sub">方策への指令</h3>
      <dl className="m5-pol__nums m5-pol__nums--row">
        <div>
          <dt>前進</dt>
          <dd>
            {fmtSigned(vx, 2)}
            <span> m/s</span>
          </dd>
        </div>
        <div>
          <dt>ヨー</dt>
          <dd>
            {fmtSigned(yaw, 2)}
            <span> rad/s</span>
          </dd>
        </div>
      </dl>
      <p className="m5-pol__note">{standing ? "止まっていろ、という指令です。" : "スティックの奥が、この前進です。"}</p>
    </article>
  );
}

function TargetCard({ frame, policy }: { frame: M5Frame; policy: M5PolicyObs }) {
  const scale = num(policy.action_scale) ?? 0.25;
  const scaleDeg = (scale * 180) / Math.PI;
  return (
    <article className="m5-pol__card m5-pol__card--targets" aria-label="直前に出した目標">
      <h3>直前に出した目標</h3>
      <p className="m5-pol__note">
        度は画面の基準です。出力 1 は、直立から {scale.toFixed(2)} rad（約 {scaleDeg.toFixed(1)}°）動かします。
      </p>
      <table className="m5-pol__table">
        <thead>
          <tr>
            <th>関節</th>
            <th>左の目標</th>
            <th>右の目標</th>
          </tr>
        </thead>
        <tbody>
          {LEG_ROWS.map((row, index) => {
            const left = legJoint("left", index);
            const right = legJoint("right", index);
            return (
              <tr key={row.id}>
                <th>
                  {row.label}
                  <span>{plusHint(row.id)}</span>
                </th>
                <td>
                  <TargetCell
                    ch={left.ch}
                    cmd={at(frame.cmd, left.ch)}
                    corr={at(frame.corr, left.ch)}
                    raw={at(policy.last_action, left.ch)}
                  />
                </td>
                <td>
                  <TargetCell
                    ch={right.ch}
                    cmd={at(frame.cmd, right.ch)}
                    corr={at(frame.corr, right.ch)}
                    raw={at(policy.last_action, right.ch)}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </article>
  );
}

/** 中立よりプラスで、体がどちらへ動くか。docs/joint_angles.md と同じ。 */
function plusHint(id: (typeof LEG_ROWS)[number]["id"]): string {
  switch (id) {
    case "hipRoll":
      return "プラスで外側";
    case "hipPitch":
      return "プラスで前";
    case "kneePitch":
      return "プラスで後ろ";
    case "anklePitch":
      return "プラスでつま先上";
    case "ankleRoll":
      return "プラスで内側が下";
    default:
      return "";
  }
}

function TargetCell({
  ch,
  cmd,
  corr,
  raw,
}: {
  ch: number;
  cmd: number | null;
  corr: number | null;
  raw: number | null;
}) {
  const neutralName = isSm105Channel(ch) ? "0°" : "135°";
  return (
    <div className={"m5-pol__cell" + (upright(ch, cmd) ? " m5-pol__cell--upright" : "")}>
      <strong>{fmtDeg(cmd)}</strong>
      <span>{fromNeutral(ch, cmd)}</span>
      <span className="m5-pol__cell-sub">
        今 {fmtDeg(corr)}
        {" · "}
        出力 {fmtSigned(raw, 2)}
      </span>
      <span className="m5-pol__cell-sub">直立は {neutralName}</span>
    </div>
  );
}
