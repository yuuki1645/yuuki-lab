#pragma once

#include <stdint.h>

// =============================================================================
// 脚マスター ↔ 足スレーブ の I2C レジスタ定義
//
// 配線:
//   PC --USB-C-- Master --Grove-- Grove Hub --Grove-- Slave (on foot)
//
// ATOMS3 Lite の HY2.0-4P は公式名称 PORT.CUSTOM。
//   Yellow = G2, White = G1, Red = 5V, Black = GND
//   SDA = G2 (黄), SCL = G1 (白)
// =============================================================================

static constexpr int kI2cSdaPin = 2;
static constexpr int kI2cSclPin = 1;

// Grove Hub 経由は配線容量が増えるため 100 kHz で安定させる
static constexpr uint32_t kI2cFrequencyHz = 100000;

// 7bit スレーブアドレス。既存センサ（0x36 AS5600 等）と衝突しにくい値
static constexpr uint8_t kI2cSlaveAddr = 0x28;

// -----------------------------------------------------------------------------
// レジスタマップ（一般的な I2C センサと同じ「ポインタ + 読み書き」）
//
// マスター書込み: [reg] [data...]
// マスター読出し: [reg] を STOP 付きで書いたあと requestFrom
//   （ESP32 スレーブは Repeated START で欠落することがある）
// -----------------------------------------------------------------------------
enum I2cReg : uint8_t {
    kRegWhoAmI = 0x00,      // R    デバイス識別子
    kRegVersion = 0x01,     // R    プロトコル版
    kRegStatus = 0x02,      // R    bit0: ready
    kRegCornerMask = 0x03,  // R    bit0..3 = TL/TR/BR/BL 設置
    kRegSeq = 0x04,         // R    uint32 LE。ADC サンプル連番
    kRegMv0 = 0x10,         // R    uint16 LE ミリボルト × 4 隅
    kRegMv1 = 0x12,         // R    top_right
    kRegMv2 = 0x14,         // R    bottom_right
    kRegMv3 = 0x16,         // R    bottom_left
    kRegLedR = 0x20,        // R/W  スレーブ RGB（マスターが Identify に使う）
    kRegLedG = 0x21,
    kRegLedB = 0x22,
};

// WHO_AM_I = 'F' (Foot)
static constexpr uint8_t kWhoAmIValue = 0x46;

// レジスタを増やしたら上げる
static constexpr uint8_t kVersionValue = 0x01;

static constexpr uint8_t kStatusReadyBit = 0x01;

// 四隅すべて設置
static constexpr uint8_t kCornerMaskAll = 0x0F;

static constexpr int kCornerCount = 4;

// レジスタファイルサイズ（未定義領域は 0）
static constexpr uint8_t kRegMapSize = 0x30;

// 足裏上面・つま先が上。Hub の A0..A3 と同じ並び
enum CornerId : uint8_t {
    kCornerTopLeft = 0,      // 左上 = つま先左
    kCornerTopRight = 1,     // 右上
    kCornerBottomRight = 2,  // 右下 = かかと右
    kCornerBottomLeft = 3,   // 左下
};
