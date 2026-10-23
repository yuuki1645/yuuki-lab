#pragma once

/**
 * CoreS3（ver 15）のテレメトリと HELLO。
 * フレームの番号と校正チャンクは link/include/usb_frame.hpp。
 */

#include <stdint.h>

#include "joint_profile.hpp"
#include "topology.hpp"
#include "usb_frame.hpp"

static constexpr uint8_t kUsbFwVer = 15;
static constexpr int kMapLen = 191;

#pragma pack(push, 1)

struct UsbFootSample {
    uint8_t ok;
    uint8_t mask;
    uint32_t seq;
    uint16_t mv[4];
};

struct UsbTelemetry15 {
    uint32_t seq;
    uint32_t t_period_us;
    uint32_t t_loop_us;
    uint32_t t_sense_us;
    uint32_t t_state_us;
    uint32_t t_policy_us;
    uint32_t t_act_us;
    int32_t jitter_us;
    uint8_t overrun;
    float cmd_deg[kCoreJoints];
    float raw_deg[kCoreJoints];
    float unwrap_deg[kCoreJoints];
    float corr_deg[kCoreJoints];
    uint8_t as_ok[kCoreJoints];
    uint8_t map_ok[kCoreJoints];
    uint8_t mag[kCoreJoints];
    uint8_t agc[kCoreJoints];
    float volt[kCoreJoints];
    float amp[kCoreJoints];
    float watt[kCoreJoints];
    uint8_t ina_ok[kCoreJoints];
    uint16_t i2c_err;
    uint8_t servo_ok;
    uint8_t mode;
    uint16_t out_mask;
    UsbFootSample foot[kCoreFeet];
};

struct UsbHello15 {
    uint8_t ver;
    uint8_t mode;
    uint8_t joints;
    uint8_t ina;
    uint8_t servo;
    uint8_t board;
    uint8_t feet;
    uint16_t out_mask;
};

#pragma pack(pop)

static_assert(sizeof(UsbTelemetry15) == 397, "ver 15 telemetry layout");
static_assert(sizeof(UsbHello15) == 9, "ver 15 hello layout");
static_assert(sizeof(UsbTelemetry15) <= kUsbMaxPayload, "telemetry too big");
static_assert(sizeof(JointRoute) == 10, "JointRoute");
static_assert(sizeof(FootRoute) == 3, "FootRoute");
static_assert(sizeof(UsbFootSample) == 14, "foot sample");
