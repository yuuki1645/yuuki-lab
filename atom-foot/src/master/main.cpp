/**
 * I2C マスターファーム（脚の ATOMS3 Lite）
 *
 * Core 1: 20 Hz で足側スレーブから四隅ミリボルトを読む（I2C はここだけ）
 * Core 0: スナップショットを USB バイナリフレームで PC へ送る
 *
 * 配線:
 *   PC --USB-C-- Master --Grove-- Grove Hub --Grove-- Slave (on foot)
 */

#include <Arduino.h>
#include <Wire.h>
#include <string.h>
#include "driver/gpio.h"
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "atoms3_lite_hw.h"
#include "i2c_foot_proto.h"
#include "usb_proto.hpp"

// =============================================================================
// 周期 / コア
// =============================================================================
static constexpr uint32_t kPeriodMs = 50;
static constexpr uint32_t kPeriodUs = kPeriodMs * 1000;
static constexpr int kRtCore = 1;
static constexpr int kUsbCore = 0;
static constexpr uint32_t kRtStack = 8192;
static constexpr uint32_t kUsbStack = 6144;
static constexpr uint32_t kIdentifyMs = 2500;
static constexpr uint32_t kButtonDebounceMs = 40;

// =============================================================================
// スナップショット（制御コアが書き、USB コアが読む）
// =============================================================================
struct Snapshot {
    uint32_t seq;
    uint32_t t_period_us;
    uint32_t t_loop_us;
    uint32_t t_i2c_us;
    uint8_t slave_ok;
    uint8_t overrun;
    uint16_t i2c_err;
    uint16_t mv[kCornerCount];
};

static Snapshot gSnapFront;
static portMUX_TYPE gSnapLock = portMUX_INITIALIZER_UNLOCKED;
static volatile uint16_t gI2cErr = 0;
static volatile uint32_t gIdentifyUntilMs = 0;
static volatile uint8_t gHelloReq = 1;
static volatile uint8_t gEvtBtn = 0;

enum UsbRxState : uint8_t {
    kUsbRxMagic0 = 0,
    kUsbRxMagic1,
    kUsbRxType,
    kUsbRxLen,
    kUsbRxPayload,
    kUsbRxCrc0,
    kUsbRxCrc1,
};

static UsbRxState gRxState = kUsbRxMagic0;
static uint8_t gRxType = 0;
static uint8_t gRxLen = 0;
static uint8_t gRxGot = 0;
static uint8_t gRxPayload[kUsbMaxPayload];
static uint8_t gRxCrcLo = 0;

// =============================================================================
// I2C（制御コア専用）
// =============================================================================
static bool writeRegs(uint8_t reg, const uint8_t* data, size_t len) {
    Wire.beginTransmission(kI2cSlaveAddr);
    Wire.write(reg);
    if (data != nullptr && len > 0) {
        Wire.write(data, len);
    }
    const uint8_t err = Wire.endTransmission(true);
    if (err != 0) {
        if (gI2cErr < 0xFFFF) {
            ++gI2cErr;
        }
        return false;
    }
    return true;
}

static bool readRegs(uint8_t reg, uint8_t* data, size_t len) {
    Wire.beginTransmission(kI2cSlaveAddr);
    Wire.write(reg);
    // STOP してから読む。ESP32 スレーブは Repeated START で欠落することがある
    const uint8_t err = Wire.endTransmission(true);
    if (err != 0) {
        if (gI2cErr < 0xFFFF) {
            ++gI2cErr;
        }
        return false;
    }
    delayMicroseconds(200);
    const size_t got = Wire.requestFrom(static_cast<int>(kI2cSlaveAddr), static_cast<int>(len));
    if (got != len) {
        if (gI2cErr < 0xFFFF) {
            ++gI2cErr;
        }
        return false;
    }
    for (size_t i = 0; i < len; ++i) {
        data[i] = static_cast<uint8_t>(Wire.read());
    }
    return true;
}

static uint16_t u16Le(const uint8_t* p) {
    return static_cast<uint16_t>(p[0]) | (static_cast<uint16_t>(p[1]) << 8);
}

static bool readSlaveSample(uint16_t* mv_out) {
    uint8_t who = 0;
    if (!readRegs(kRegWhoAmI, &who, 1) || who != kWhoAmIValue) {
        return false;
    }
    uint8_t raw[8] = {};
    if (!readRegs(kRegMv0, raw, sizeof(raw))) {
        return false;
    }
    for (int i = 0; i < kCornerCount; ++i) {
        mv_out[i] = u16Le(&raw[i * 2]);
    }
    return true;
}

static void publishSnapshot(const Snapshot& snap) {
    portENTER_CRITICAL(&gSnapLock);
    gSnapFront = snap;
    portEXIT_CRITICAL(&gSnapLock);
}

static bool copySnapshot(Snapshot& out) {
    portENTER_CRITICAL(&gSnapLock);
    out = gSnapFront;
    portEXIT_CRITICAL(&gSnapLock);
    return out.seq != 0;
}

// =============================================================================
// USB（Core 0）
// =============================================================================
static void usbSend(uint8_t type, const void* payload, uint8_t len) {
    uint8_t buf[6 + kUsbMaxPayload];
    const size_t n = usbBuildFrame(buf, sizeof(buf), type, payload, len);
    if (n == 0) {
        return;
    }
    const uint32_t t0 = millis();
    while (Serial.availableForWrite() < static_cast<int>(n)) {
        if ((millis() - t0) > 80) {
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    Serial.write(buf, n);
}

static void usbPrintHello(uint8_t slave_ok) {
    UsbHello h{};
    h.ver = kUsbFwVer;
    h.corners = kUsbCorners;
    h.slave_ok = slave_ok;
    h.reserved = 0;
    usbSend(kUsbHello, &h, sizeof(h));
}

static void usbPrintFrame(const Snapshot& snap) {
    UsbTelemetry t{};
    t.seq = snap.seq;
    t.t_period_us = snap.t_period_us;
    t.t_loop_us = snap.t_loop_us;
    t.t_i2c_us = snap.t_i2c_us;
    t.slave_ok = snap.slave_ok;
    t.overrun = snap.overrun;
    t.i2c_err = snap.i2c_err;
    memcpy(t.mv, snap.mv, sizeof(t.mv));
    usbSend(kUsbTelemetry, &t, sizeof(t));
}

static void handleUsbFrame(uint8_t type, const uint8_t* /*p*/, uint8_t /*len*/) {
    if (type == kUsbCmdPing) {
        gHelloReq = 1;
        return;
    }
    if (type == kUsbCmdIdentify) {
        gIdentifyUntilMs = millis() + kIdentifyMs;
        usbSend(kUsbIdentifyOk, nullptr, 0);
        return;
    }
}

static void usbRxReset() {
    gRxState = kUsbRxMagic0;
    gRxGot = 0;
}

static void pollUsbRx() {
    while (Serial.available() > 0) {
        const int c = Serial.read();
        if (c < 0) {
            break;
        }
        const uint8_t b = static_cast<uint8_t>(c);
        switch (gRxState) {
        case kUsbRxMagic0:
            if (b == kUsbMagic0) {
                gRxState = kUsbRxMagic1;
            }
            break;
        case kUsbRxMagic1:
            gRxState = (b == kUsbMagic1) ? kUsbRxType : kUsbRxMagic0;
            if (gRxState == kUsbRxMagic0 && b == kUsbMagic0) {
                gRxState = kUsbRxMagic1;
            }
            break;
        case kUsbRxType:
            gRxType = b;
            gRxState = kUsbRxLen;
            break;
        case kUsbRxLen:
            gRxLen = b;
            gRxGot = 0;
            if (gRxLen > kUsbMaxPayload) {
                usbRxReset();
            } else if (gRxLen == 0) {
                gRxState = kUsbRxCrc0;
            } else {
                gRxState = kUsbRxPayload;
            }
            break;
        case kUsbRxPayload:
            gRxPayload[gRxGot++] = b;
            if (gRxGot >= gRxLen) {
                gRxState = kUsbRxCrc0;
            }
            break;
        case kUsbRxCrc0:
            gRxCrcLo = b;
            gRxState = kUsbRxCrc1;
            break;
        case kUsbRxCrc1: {
            uint8_t tmp[2 + kUsbMaxPayload];
            tmp[0] = gRxType;
            tmp[1] = gRxLen;
            if (gRxLen > 0) {
                memcpy(tmp + 2, gRxPayload, gRxLen);
            }
            const uint16_t crc = usbCrc16(tmp, static_cast<size_t>(2) + gRxLen);
            const uint16_t got = static_cast<uint16_t>(gRxCrcLo) |
                                 (static_cast<uint16_t>(b) << 8);
            if (crc == got) {
                handleUsbFrame(gRxType, gRxPayload, gRxLen);
            }
            usbRxReset();
            break;
        }
        default:
            usbRxReset();
            break;
        }
    }
}

static bool wasButtonClicked() {
    static bool lastStable = false;
    static bool lastRaw = false;
    static uint32_t lastChangeMs = 0;

    const bool rawPressed = buttonPressed();
    const uint32_t now = millis();
    if (rawPressed != lastRaw) {
        lastRaw = rawPressed;
        lastChangeMs = now;
        return false;
    }
    if ((now - lastChangeMs) < kButtonDebounceMs) {
        return false;
    }
    const bool clicked = lastStable && !rawPressed;
    lastStable = rawPressed;
    return clicked;
}

static void usbTask(void* /*arg*/) {
    Snapshot snap;
    uint32_t lastSeq = 0;
    bool haveLast = false;

    for (;;) {
        pollUsbRx();
        if (wasButtonClicked()) {
            gEvtBtn = 1;
            gIdentifyUntilMs = millis() + kIdentifyMs;
        }
        if (gHelloReq) {
            gHelloReq = 0;
            Snapshot cur{};
            copySnapshot(cur);
            usbPrintHello(cur.slave_ok);
        }
        if (gEvtBtn) {
            gEvtBtn = 0;
            usbSend(kUsbEvtBtn, nullptr, 0);
        }
        if (copySnapshot(snap) && (!haveLast || snap.seq != lastSeq)) {
            lastSeq = snap.seq;
            haveLast = true;
            usbPrintFrame(snap);
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// =============================================================================
// センサ周期（Core 1）
// =============================================================================
static void rtTask(void* /*arg*/) {
    TickType_t lastWake = xTaskGetTickCount();
    uint32_t prevStartUs = micros();
    bool first = true;
    uint32_t seq = 0;

    for (;;) {
        const uint32_t t0 = micros();
        uint32_t t_period_us = kPeriodUs;
        if (!first) {
            t_period_us = t0 - prevStartUs;
        }
        prevStartUs = t0;
        first = false;
        ++seq;

        uint16_t mv[kCornerCount] = {0, 0, 0, 0};
        const uint32_t i2c0 = micros();
        const bool ok = readSlaveSample(mv);
        const uint32_t t_i2c = micros() - i2c0;
        const uint32_t t_loop = micros() - t0;
        const bool overrun = t_loop > kPeriodUs;

        Snapshot snap{};
        snap.seq = seq;
        snap.t_period_us = t_period_us;
        snap.t_loop_us = t_loop;
        snap.t_i2c_us = t_i2c;
        snap.slave_ok = ok ? 1 : 0;
        snap.overrun = overrun ? 1 : 0;
        snap.i2c_err = gI2cErr;
        memcpy(snap.mv, mv, sizeof(mv));
        publishSnapshot(snap);

        const uint32_t nowMs = millis();
        if (nowMs < gIdentifyUntilMs) {
            const uint8_t hue = static_cast<uint8_t>((nowMs / 4) & 0xFF);
            rgbLedArray()[0] = CHSV(hue, 255, 160);
            FastLED.show();
            // 足側 LED も虹色にして、どの足か目視できるようにする
            uint8_t rgb[3] = {0, 0, 0};
            const CRGB c = CHSV(hue, 255, 80);
            rgb[0] = c.r;
            rgb[1] = c.g;
            rgb[2] = c.b;
            writeRegs(kRegLedR, rgb, 3);
        } else if (overrun) {
            setRgbLed(180, 0, 0);
        } else if (!ok) {
            setRgbLed(((t0 / 250000) % 2) ? 80 : 0, 0, 0);
        } else {
            setRgbLed(0, 90, 20);
        }

        vTaskDelayUntil(&lastWake, pdMS_TO_TICKS(kPeriodMs));
    }
}

void setup() {
    beginAtoms3Lite("MASTER / leg");

    Serial.printf("I2C master -> slave 0x%02X  SDA=G%d  SCL=G%d  %lu Hz\n",
                  kI2cSlaveAddr, kI2cSdaPin, kI2cSclPin,
                  static_cast<unsigned long>(kI2cFrequencyHz));
    Serial.println("USB はバイナリフレーム（tools/foot_pressure_gui.py）");
    Serial.println("正面ボタン: Identify");

    const bool ok = Wire.begin(kI2cSdaPin, kI2cSclPin, kI2cFrequencyHz);
    gpio_set_pull_mode(static_cast<gpio_num_t>(kI2cSdaPin), GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(static_cast<gpio_num_t>(kI2cSclPin), GPIO_PULLUP_ONLY);
    Wire.setTimeOut(20);

    if (!ok) {
        Serial.println("ERROR: Wire.begin (master) failed");
        setRgbLed(48, 0, 0);
        return;
    }

    memset(&gSnapFront, 0, sizeof(gSnapFront));
    gHelloReq = 1;
    setRgbLed(16, 16, 0);

    xTaskCreatePinnedToCore(usbTask, "usb", kUsbStack, nullptr, 1, nullptr, kUsbCore);
    xTaskCreatePinnedToCore(rtTask, "rt", kRtStack, nullptr, 2, nullptr, kRtCore);
}

void loop() {
    vTaskDelay(pdMS_TO_TICKS(1000));
}
