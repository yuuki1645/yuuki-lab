/**
 * 実機の配線表。表示だけ。
 *
 * 中身は腰が返す、ファームに焼き込んだ既定表です。
 * 編集は core-rt/src/topology.hpp を直して、両脚へ書き込みます。
 */
import { UiHelp } from "@/shared/components/UiHelp";
import { fmtFootRoute, pwmRouteLabel } from "./m5Route";
import { sm105ServoId } from "./rightLeg";
import { type M5Cmd, type M5FootRoute, type M5Profile, type M5Route } from "./types";

const JOINT_NAMES = [
  "右 股ロール",
  "右 股ピッチ",
  "右 ひざ",
  "右 かかとピッチ",
  "右 かかとロール",
  "左 股ロール",
  "左 股ピッチ",
  "左 ひざ",
  "左 かかとピッチ",
  "左 かかとロール",
];

function place(hub: number, ch: number, addr: number): string {
  if (!addr) return "なし";
  const hex = `0x${(addr & 0xff).toString(16).toUpperCase().padStart(2, "0")}`;
  if (!hub) return `直下 ${hex}`;
  const hubHex = `0x${(hub & 0xff).toString(16).toUpperCase().padStart(2, "0")}`;
  return `PaHub ${hubHex} CH${ch}  ${hex}`;
}

/** サーボ欄。ひざとかかとピッチは PWM 経路ではなく RS485 の ID を出す。 */
function servoCell(index: number, route: M5Route): string {
  const id = sm105ServoId(index);
  if (id != null) {
    return `SM105BL  RS485 ID ${id}`;
  }
  return pwmRouteLabel(route);
}

function footLine(label: string, foot: M5FootRoute | null | undefined) {
  return (
    <p className="m5__meta">
      {label}：{foot && foot.addr ? fmtFootRoute(foot) : "なし"}
    </p>
  );
}

export function ProfilePanel({
  profile,
  canCmd,
  send,
}: {
  profile: M5Profile | null;
  canCmd: boolean;
  send: (cmd: M5Cmd) => void;
}) {
  const routes = profile?.routes ?? [];

  return (
    <section className="m5__section">
      <div className="m5__toolbar">
        <UiHelp title="配線表" wide>
          腰のファームに焼き込んだ既定です。画面からは変えられません。端子を動かすときは
          core-rt/src/topology.hpp を直して、両脚の ATOM S3R へ同じファームを書き込みます。
        </UiHelp>
        <button
          type="button"
          className="m5__btn"
          disabled={!canCmd}
          onClick={() => send({ op: "prof_get" })}
        >
          腰から読み直す
        </button>
      </div>
      <p className="m5__meta">
        各脚は起動時に見えた PaHub で、右用か左用かを選びます。PWM のオンとオフは脚タブのボタンです。ひざとかかとピッチは両脚とも SM105BL で、サーボ欄は RS485 の ID です。
      </p>
      {routes.length === 0 ? (
        <p className="m5__meta">腰から配線表が届いていません。「腰から読み直す」を押してください。</p>
      ) : (
        <div className="m5__table-wrap">
          <table className="m5__table">
            <thead>
              <tr>
                <th>関節</th>
                <th>角度センサ</th>
                <th>サーボ</th>
                <th>電流センサ</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((route: M5Route, i: number) => {
                const sm105 = sm105ServoId(i) != null;
                return (
                  <tr key={i} className={sm105 ? "m5__table-row--sm105" : undefined}>
                    <td>{JOINT_NAMES[i] ?? String(i)}</td>
                    <td>{place(route.enc_hub, route.enc_ch, route.enc_addr)}</td>
                    <td className={sm105 ? "m5__servo--sm105" : undefined}>{servoCell(i, route)}</td>
                    <td>{place(route.ina_hub, route.ina_ch, route.ina_addr)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {profile ? (
        <>
          {footLine("右足", profile.foot)}
          {footLine("左足", profile.foot_left)}
        </>
      ) : null}
    </section>
  );
}
