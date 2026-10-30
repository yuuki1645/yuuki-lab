#pragma once

/**
 * 取り付けの向きと、真下からのズレ。
 *
 * プログラムのほかの部分は、135° を真下、増える向きを URDF の正として扱う。
 * ホーンが逆の関節は 135° を中心に折り返し、そのあとでブラケットのズレを足す。
 * 足す場所は脚 ATOM がパルスへ変える直前。補正角は腰がマップの直後に逆変換する。
 *
 * ズレは、変換を入れる前に実機テレメトリの指令バーで測った。
 * リンクが真下を向いた指令角から 135 を引いた値。2026-10-30。
 * 右股ロールの −15° は、ほかより大きいが、取り付けそのものがそうだった。
 *
 * 校正マップの点は変えない。マップは「その電気角を指令したときの磁石位置」。
 * 掃引は kUsbCmdJointElec でこの変換を通さず、同じ電気角をパルスにする。
 */

#include <stdint.h>

static constexpr int kMountJoints = 10;
static constexpr float kMountNeutralDeg = 135.0f;

/** 論理軸 0〜9。1 の軸だけ、135° を中心に折り返す。 */
static constexpr uint16_t kMountFlipMask =
    (1u << 0) | (1u << 2) | (1u << 3) | (1u << 4) | (1u << 6);

/**
 * 電気角 − 135°。0.1° 単位。
 * 0 右股ロール −15、1 右股ピッチ −3、2 右ひざ +5、3 右踵ピッチ −2、4 右踵ロール +5、
 * 5 左股ロール 0、6 左股ピッチ 0、7 左ひざ 0、8 左踵ピッチ −1、9 左踵ロール +5。
 */
static constexpr int kMountBiasDeci[kMountJoints] = {
    -150, -30, 50, -20, 50, 0, 0, 0, -10, 50,
};

static constexpr int kMountNeutralDeci = 1350;
static constexpr int kMountTurnDeci = 2700;

static constexpr bool mountFlipped(int channel) {
    return channel >= 0 && channel < kMountJoints && (kMountFlipMask & (1u << channel)) != 0;
}

/** 理想角（0.1°）を、サーボへ出す電気角にする。範囲の外は呼び出し側が切る。 */
static constexpr int mountIdealToElectricalDeci(int channel, int idealDeci) {
    return ((kMountFlipMask & (1u << channel)) != 0 ? (kMountTurnDeci - idealDeci) : idealDeci) +
           kMountBiasDeci[channel];
}

/** マップが出す電気角（0.1°）を、理想角に戻す。 */
static constexpr int mountElectricalToIdealDeci(int channel, int electricalDeci) {
    return (kMountFlipMask & (1u << channel)) != 0
               ? (kMountTurnDeci - (electricalDeci - kMountBiasDeci[channel]))
               : (electricalDeci - kMountBiasDeci[channel]);
}

static inline float mountIdealToElectrical(int channel, float idealDeg) {
    if (channel < 0 || channel >= kMountJoints) {
        return idealDeg;
    }
    const float turned =
        mountFlipped(channel) ? (2.0f * kMountNeutralDeg - idealDeg) : idealDeg;
    return turned + (static_cast<float>(kMountBiasDeci[channel]) / 10.0f);
}

static inline float mountElectricalToIdeal(int channel, float electricalDeg) {
    if (channel < 0 || channel >= kMountJoints) {
        return electricalDeg;
    }
    const float shifted = electricalDeg - (static_cast<float>(kMountBiasDeci[channel]) / 10.0f);
    return mountFlipped(channel) ? (2.0f * kMountNeutralDeg - shifted) : shifted;
}

static_assert(mountIdealToElectricalDeci(0, kMountNeutralDeci) == 1200, "右股ロールの真下は 120°");
static_assert(mountIdealToElectricalDeci(1, kMountNeutralDeci) == 1320, "右股ピッチの真下は 132°");
static_assert(mountIdealToElectricalDeci(2, kMountNeutralDeci) == 1400, "右ひざの真下は 140°");
static_assert(mountIdealToElectricalDeci(3, kMountNeutralDeci) == 1330, "右踵ピッチの真下は 133°");
static_assert(mountIdealToElectricalDeci(4, kMountNeutralDeci) == 1400, "右踵ロールの真下は 140°");
static_assert(mountIdealToElectricalDeci(5, kMountNeutralDeci) == 1350, "左股ロールの真下は 135°");
static_assert(mountIdealToElectricalDeci(6, 1450) == 1250, "左股ピッチは向きだけ折り返す");
static_assert(mountIdealToElectricalDeci(8, kMountNeutralDeci) == 1340, "左踵ピッチの真下は 134°");
static_assert(mountIdealToElectricalDeci(9, kMountNeutralDeci) == 1400, "左踵ロールの真下は 140°");
static_assert(mountElectricalToIdealDeci(0, 1200) == kMountNeutralDeci, "右股ロールの補正角を真下へ戻す");
static_assert(mountElectricalToIdealDeci(0, 1100) == 1450, "折り返しとズレの逆変換");
static_assert(mountElectricalToIdealDeci(9, 1400) == kMountNeutralDeci, "左踵ロールの補正角を真下へ戻す");
