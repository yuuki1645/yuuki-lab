#pragma once

/**
 * ATOMS3 Lite / ATOM S3R の USB ペイロード（ver 14）。
 *
 * フレーム、メッセージ番号、校正チャンク、NVS の並びは link/include/usb_frame.hpp。
 * ここは 8 関節・右足 1 本のテレメトリと HELLO だけを持つ。
 * Python 側は link/py/rt_usb_proto.py と欄の並びを揃えること。
 */

#include <stdint.h>

#include "joint_profile.hpp"
#include "snapshot.hpp"
#include "usb_frame.hpp"

static constexpr uint8_t kUsbFwVer = 14;  // NVS 一覧は待ち＋間隔付き。ProfOk は en readback 後

#pragma pack(push, 1)

struct UsbTelemetry {
    uint32_t seq;
    uint32_t t_period_us;
    uint32_t t_loop_us;
    uint32_t t_sense_us;
    uint32_t t_state_us;
    uint32_t t_policy_us;
    uint32_t t_act_us;
    int32_t jitter_us;
    uint8_t overrun;
    float cmd_deg[kSnapJoints];
    float raw_deg[kSnapJoints];
    float unwrap_deg[kSnapJoints];
    float corr_deg[kSnapJoints];
    uint8_t as_ok[kSnapJoints];
    uint8_t map_ok[kSnapJoints];
    uint8_t mag[kSnapJoints];
    uint8_t agc[kSnapJoints];
    float volt[kSnapIna];
    float amp[kSnapIna];
    float watt[kSnapIna];
    uint8_t ina_ok[kSnapIna];
    uint16_t i2c_err;
    uint8_t servo_ok;
    uint8_t mode;
    uint8_t out_mask;
    uint8_t foot_ok;
    uint8_t foot_mask;
    uint32_t foot_seq;
    uint16_t foot_mv[4];
};

struct UsbHello {
    uint8_t ver;
    uint8_t mode;
    uint8_t joints;
    uint8_t ina;
    uint8_t servo;
    uint8_t out_mask;
};

#pragma pack(pop)

static_assert(sizeof(UsbTelemetry) <= kUsbMaxPayload, "telemetry too big");
// 8 関節 + 8 INA + 足 4 隅: 302 + 14 = 316
static_assert(sizeof(UsbTelemetry) == 316, "UsbTelemetry layout");
static_assert(sizeof(UsbHello) == 6, "UsbHello layout");
static_assert(sizeof(JointRoute) == 10, "JointRoute must be 10 bytes");
static_assert(sizeof(FootRoute) == 3, "FootRoute must be 3 bytes");
