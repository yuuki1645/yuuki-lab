#pragma once

#include <stdint.h>

/**
 * 右足 ATOMS3 Lite スレーブ（atom-foot i2c_slave）の I2C レジスタ。
 *
 * マスターは atom-rt（ATOM S3R）。専用脚マスターは使わない。
 * ESP32 スレーブは Repeated START で欠けることがあるので、
 * レジスタポインタは STOP 付きで書いてから requestFrom する。
 */
static constexpr uint8_t kI2cFootAddrDefault = 0x28;
static constexpr uint32_t kI2cFootFrequencyHz = 100000;

enum I2cFootReg : uint8_t {
    kFootRegWhoAmI = 0x00,      // R    'F' (0x46)
    kFootRegVersion = 0x01,     // R
    kFootRegStatus = 0x02,      // R    bit0: ready
    kFootRegCornerMask = 0x03,  // R    bit0..3 = TL/TR/BR/BL
    kFootRegSeq = 0x04,         // R    uint32 LE
    kFootRegMv0 = 0x10,         // R    uint16 LE mV × 4 隅
    kFootRegMv1 = 0x12,
    kFootRegMv2 = 0x14,
    kFootRegMv3 = 0x16,
    kFootRegLedR = 0x20,        // R/W  Identify 用 RGB
    kFootRegLedG = 0x21,
    kFootRegLedB = 0x22,
};

static constexpr uint8_t kFootWhoAmIValue = 0x46;
static constexpr uint8_t kFootStatusReadyBit = 0x01;
static constexpr uint8_t kFootCornerMaskAll = 0x0F;
static constexpr int kFootCornerCount = 4;

enum FootCornerId : uint8_t {
    kFootCornerTopLeft = 0,
    kFootCornerTopRight = 1,
    kFootCornerBottomRight = 2,
    kFootCornerBottomLeft = 3,
};
