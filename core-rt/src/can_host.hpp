#pragma once

/**
 * 腰が左右の脚と話す口。計測の組立と、指令・経路・走査の送信。
 * USB のバイト列はここでは作らない。
 */

#include <stdint.h>

#include "joint_profile.hpp"
#include "usb_frame.hpp"

static constexpr int kCanHostJoints = 10;
static constexpr int kCanHostFeet = 2;

struct CanHostAxis {
    float raw_deg;
    float volt;
    float amp;
    float watt;
    uint8_t as_ok;
    uint8_t ina_ok;
    uint8_t mag;
    uint8_t agc;
};

struct CanHostFoot {
    uint8_t ok;
    uint8_t mask;
    uint32_t seq;
    uint16_t mv[4];
};

struct CanHostView {
    CanHostAxis axis[kCanHostJoints];
    CanHostFoot foot[kCanHostFeet];
    uint16_t i2c_err;
    uint8_t servo_ok;
    uint32_t sense_us;
    bool fault;
    bool overcurrent;
    float over_amp;
};

/** PORT.C。tx は GPIO17、rx は GPIO18。失敗したら false。 */
bool canHostStart(int txPin, int rxPin);

/** 受信キューを空にする。制御周期のたびに呼ぶ。 */
void canHostPoll();

/**
 * 直近の計測を論理軸 0〜9 に並べる。
 * 一度でも現れた脚が 200 ms 黙ったら fault。その脚の軸は欠測にする。
 * overcurrent は立ち上がりだけ true。
 */
void canHostRead(CanHostView& out);

/**
 * 論理軸の角度と 10 bit マスクを、現れている脚へ分ける。forceOff で両脚を切る。
 * electrical のビットが 1 の軸は電気角のまま送り、脚は取り付け変換を通さない。
 */
void canHostSendMotion(const float* deg, uint16_t mask, bool forceOff, uint16_t electrical = 0);

/** 片脚 5 軸ぶんの経路。腰はもう送らない。脚はファームの表を使う。 */
void canHostSendRoutes(const JointRoute* routes, const FootRoute* feet, uint16_t jointEn,
                       uint8_t footEn, uint8_t gen);

/** 現れている脚の走査が揃うか、waitMs まで待つ。戻った件数を返す。 */
int canHostCollectScan(UsbScanNode* out, int maxNodes, uint32_t waitMs);

/** 両脚へ Identify を 1 枚ずつ出す。 */
void canHostIdentify();
