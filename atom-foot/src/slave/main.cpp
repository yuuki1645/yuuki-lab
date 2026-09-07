/**
 * I2C スレーブファーム（足裏 ATOMS3 Lite）
 *
 * Grove (G2=SDA, G1=SCL) でアドレス kI2cSlaveAddr として応答する。
 * 底面ヘッダの ADC で DF9-40 四隅の分圧電圧を読み、レジスタに公開する。
 * センサー励磁は基板表面の 3V3 ピンソケット（Grove 5V ではない）。
 *
 * ESP32-S3 の I2C スレーブは、応答データを FIFO に先載せした方が安定する。
 * onReceive / onRequest では delay / Serial / FastLED / analogRead を呼ばない。
 */

#include <Arduino.h>
#include <Wire.h>
#include <string.h>
#include "driver/gpio.h"

#include "atoms3_lite_hw.h"
#include "df9_force.hpp"
#include "i2c_foot_proto.h"

// =============================================================================
// 足裏 ADC ピン（ATOMS3 Lite 底面ヘッダ。ESP32-S3 ADC1）
//   上面・つま先が上: G5=左上 / G6=右上 / G7=右下 / G8=左下
// =============================================================================
static constexpr int kAdcPins[kCornerCount] = {5, 6, 7, 8};

static constexpr int kAdcBits = 12;
static constexpr int kAdcAvgSamples = 8;

// レジスタファイル。I2C コールバックと loop の両方から触る
static uint8_t g_regs[kRegMapSize];
static volatile uint8_t g_reg_ptr = 0;
static volatile bool g_led_dirty = false;
static portMUX_TYPE g_mux = portMUX_INITIALIZER_UNLOCKED;

static const size_t kTxChunk = 24;

static bool isWritable(uint8_t addr) {
    return addr >= kRegLedR && addr <= kRegLedB;
}

static void putU16Le(uint8_t* dst, uint16_t v) {
    dst[0] = static_cast<uint8_t>(v);
    dst[1] = static_cast<uint8_t>(v >> 8);
}

static void putU32Le(uint8_t* dst, uint32_t v) {
    dst[0] = static_cast<uint8_t>(v);
    dst[1] = static_cast<uint8_t>(v >> 8);
    dst[2] = static_cast<uint8_t>(v >> 16);
    dst[3] = static_cast<uint8_t>(v >> 24);
}

static void initRegisters() {
    memset(g_regs, 0, sizeof(g_regs));
    g_regs[kRegWhoAmI] = kWhoAmIValue;
    g_regs[kRegVersion] = kVersionValue;
    g_regs[kRegStatus] = kStatusReadyBit;
    g_regs[kRegCornerMask] = kCornerMaskAll;
    g_regs[kRegLedG] = 24;
    g_led_dirty = true;
}

static size_t copyTxChunk(uint8_t* dst) {
    const uint8_t start = g_reg_ptr;
    size_t n = 0;
    for (; n < kTxChunk; ++n) {
        const uint16_t addr = static_cast<uint16_t>(start) + n;
        dst[n] = (addr < kRegMapSize) ? g_regs[addr] : 0;
    }
    return n;
}

static void preloadTxBufferUnlocked() {
    uint8_t buf[kTxChunk];
    portENTER_CRITICAL(&g_mux);
    copyTxChunk(buf);
    portEXIT_CRITICAL(&g_mux);
    Wire.slaveWrite(buf, sizeof(buf));
}

static void onReceive(int len) {
    if (len < 1) {
        return;
    }

    portENTER_CRITICAL(&g_mux);
    const uint8_t start_addr = static_cast<uint8_t>(Wire.read());
    uint8_t addr = start_addr;
    g_reg_ptr = start_addr;
    int remain = len - 1;

    while (remain > 0 && Wire.available()) {
        const uint8_t value = static_cast<uint8_t>(Wire.read());
        --remain;
        if (isWritable(addr) && addr < kRegMapSize) {
            g_regs[addr] = value;
            if (addr >= kRegLedR && addr <= kRegLedB) {
                g_led_dirty = true;
            }
        }
        if (addr < 0xFF) {
            ++addr;
        }
    }
    portEXIT_CRITICAL(&g_mux);
    preloadTxBufferUnlocked();
}

static void onRequest() {
    uint8_t buf[kTxChunk];
    portENTER_CRITICAL(&g_mux);
    copyTxChunk(buf);
    portEXIT_CRITICAL(&g_mux);
    Wire.write(buf, sizeof(buf));
}

/** 1 チャネルを平均してミリボルトを返す。 */
static uint16_t readAdcMilliVolts(int pin) {
    int32_t sum = 0;
    for (int i = 0; i < kAdcAvgSamples; ++i) {
        sum += analogReadMilliVolts(pin);
        delayMicroseconds(150);
    }
    const int mv = static_cast<int>(sum / kAdcAvgSamples);
    if (mv < 0) {
        return 0;
    }
    if (mv > 3300) {
        return 3300;
    }
    return static_cast<uint16_t>(mv);
}

static void sampleAdcAndPublish() {
    uint16_t mv[kCornerCount];
    float total_kg = 0.0f;
    for (int i = 0; i < kCornerCount; ++i) {
        mv[i] = readAdcMilliVolts(kAdcPins[i]);
        total_kg += df9VoltageToForceKg(static_cast<float>(mv[i]) / 1000.0f);
    }

    portENTER_CRITICAL(&g_mux);
    uint32_t seq = static_cast<uint32_t>(g_regs[kRegSeq]) |
                   (static_cast<uint32_t>(g_regs[kRegSeq + 1]) << 8) |
                   (static_cast<uint32_t>(g_regs[kRegSeq + 2]) << 16) |
                   (static_cast<uint32_t>(g_regs[kRegSeq + 3]) << 24);
    ++seq;
    putU32Le(&g_regs[kRegSeq], seq);
    putU16Le(&g_regs[kRegMv0], mv[0]);
    putU16Le(&g_regs[kRegMv1], mv[1]);
    putU16Le(&g_regs[kRegMv2], mv[2]);
    putU16Le(&g_regs[kRegMv3], mv[3]);
    const bool led_dirty = g_led_dirty;
    const uint8_t lr = g_regs[kRegLedR];
    const uint8_t lg = g_regs[kRegLedG];
    const uint8_t lb = g_regs[kRegLedB];
    if (led_dirty) {
        g_led_dirty = false;
    }
    portEXIT_CRITICAL(&g_mux);

    // マスターが LED を書いていなければ、合計荷重で色を変える
    if (led_dirty) {
        setRgbLed(lr, lg, lb);
    } else {
        const float ratio = df9Clamp(total_kg / (kDf9ForceMaxKg * 4.0f), 0.0f, 1.0f);
        const uint8_t r = static_cast<uint8_t>(8 + ratio * 80);
        const uint8_t g = static_cast<uint8_t>(28 - ratio * 20);
        const uint8_t b = static_cast<uint8_t>(40 - ratio * 32);
        setRgbLed(r, g, b);
    }
}

void setup() {
    initRegisters();
    beginAtoms3Lite("SLAVE / foot");

    analogReadResolution(kAdcBits);
    for (int i = 0; i < kCornerCount; ++i) {
        analogSetPinAttenuation(kAdcPins[i], ADC_11db);
        pinMode(kAdcPins[i], INPUT);
    }

    // センサー励磁は基板表面の 3V3 ピンソケット（Grove 5V は使わない）
    Serial.printf("I2C slave addr=0x%02X  SDA=G%d  SCL=G%d  %lu Hz\n",
                  kI2cSlaveAddr, kI2cSdaPin, kI2cSclPin,
                  static_cast<unsigned long>(kI2cFrequencyHz));
    Serial.println("ADC: G5=TL G6=TR G7=BR G8=BL  excite=board 3V3 pin");
    Serial.println("Grove Hub 経由でマスターに接続してください。");

    Wire.onReceive(onReceive);
    Wire.onRequest(onRequest);
    const bool ok = Wire.begin(kI2cSlaveAddr, kI2cSdaPin, kI2cSclPin, kI2cFrequencyHz);
    gpio_set_pull_mode(static_cast<gpio_num_t>(kI2cSdaPin), GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(static_cast<gpio_num_t>(kI2cSclPin), GPIO_PULLUP_ONLY);

    if (!ok) {
        Serial.println("ERROR: Wire.begin (slave) failed");
        setRgbLed(48, 0, 0);
        return;
    }

    preloadTxBufferUnlocked();
    setRgbLed(g_regs[kRegLedR], g_regs[kRegLedG], g_regs[kRegLedB]);
    Serial.println("I2C slave ready.");
}

void loop() {
    sampleAdcAndPublish();
    delay(20);
}
