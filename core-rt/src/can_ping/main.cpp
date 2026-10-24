/**
 * CoreS3 と ATOM S3R の CAN 疎通試験。腰の本線（ver 15）とは別の書き込み対象。
 *
 * pio run -e can-ping -t upload
 * 戻すときは pio run -e core-s3 -t upload。
 *
 * Unit CAN（CA-IS3050G）を PORT.C に挿す。
 *   黄 GPIO17 = 送信。トランシーバの TXD へ出す
 *   白 GPIO18 = 受信。トランシーバの RXD から読む
 * 赤の 5V は AW9523 がオンにするまで出ない。オフのままだとユニットは無応答。
 *
 * 500 kbps。1 秒ごとに 0x100 を送り、受け取ったフレームを USB シリアルへ出す。
 * 机上の 2 台は両方とも端なので、120 Ω は両方に付ける。
 */

#include <Arduino.h>
#include <Wire.h>

#include "can_ping.hpp"

static constexpr int kCanTxPin = 17;
static constexpr int kCanRxPin = 18;

static constexpr int kIntSdaPin = 12;
static constexpr int kIntSclPin = 11;
static constexpr uint32_t kI2cHz = 100000;
static constexpr uint32_t kI2cTimeoutMs = 20;

static constexpr uint8_t kAw9523Addr = 0x58;
static constexpr uint8_t kAwOutP0 = 0x02;
static constexpr uint8_t kAwCtl = 0x11;
static constexpr uint8_t kAwGpomdPushPull = 0x10;  // CTL bit4。P0 をプッシュ・プルへ
static constexpr uint8_t kAwBusEnBit = 0x02;       // P0.1 = BUS_EN
static constexpr uint8_t kAwBoostEnBit = 0x80;     // P1.7 = BOOST_EN

static bool awReadReg(uint8_t reg, uint8_t& value) {
    Wire1.beginTransmission(kAw9523Addr);
    Wire1.write(reg);
    if (Wire1.endTransmission(true) != 0) {
        return false;
    }
    if (Wire1.requestFrom(static_cast<int>(kAw9523Addr), 1) != 1) {
        return false;
    }
    value = static_cast<uint8_t>(Wire1.read());
    return true;
}

static bool awWriteReg(uint8_t reg, uint8_t value) {
    Wire1.beginTransmission(kAw9523Addr);
    Wire1.write(reg);
    Wire1.write(value);
    return Wire1.endTransmission(true) == 0;
}

/**
 * PORT.C を含む Grove の 5V を出す。
 * P0 は上電時オープン・ドレインなので、GPOMD を立ててから BUS_EN を書く。
 */
static bool enableGrovePower() {
    Wire1.begin(kIntSdaPin, kIntSclPin, kI2cHz);
    Wire1.setTimeOut(kI2cTimeoutMs);

    uint8_t ctl = 0;
    if (!awReadReg(kAwCtl, ctl)) {
        return false;
    }
    if (!awWriteReg(kAwCtl, static_cast<uint8_t>(ctl | kAwGpomdPushPull))) {
        return false;
    }

    Wire1.beginTransmission(kAw9523Addr);
    Wire1.write(kAwOutP0);
    if (Wire1.endTransmission(true) != 0) {
        return false;
    }
    // 0x02 から 2 バイト。AW9523 は自動で 0x03（P1）へ進む。
    if (Wire1.requestFrom(static_cast<int>(kAw9523Addr), 2) != 2) {
        return false;
    }
    const uint8_t p0 = static_cast<uint8_t>(Wire1.read()) | kAwBusEnBit;
    const uint8_t p1 = static_cast<uint8_t>(Wire1.read()) | kAwBoostEnBit;

    Wire1.beginTransmission(kAw9523Addr);
    Wire1.write(kAwOutP0);
    Wire1.write(p0);
    Wire1.write(p1);
    if (Wire1.endTransmission(true) != 0) {
        return false;
    }
    delay(50);
    return true;
}

static uint32_t gSeq = 0;
static uint32_t gNextTxMs = 0;
static bool gSawRx = false;

static void printBanner() {
    Serial.println("can-ping core");
    Serial.printf("twai 500k tx=%d rx=%d id=0x%03X\n", kCanTxPin, kCanRxPin, kCanPingIdCore);
}

void setup() {
    Serial.begin(115200);
    Serial.setTxBufferSize(1024);
    delay(200);
    printBanner();
    Serial.println(enableGrovePower() ? "grove 5V on" : "grove 5V off");
    const bool started = canPingStart(static_cast<gpio_num_t>(kCanTxPin),
                                       static_cast<gpio_num_t>(kCanRxPin));
    Serial.println(started ? "twai started" : "twai start failed");
    gNextTxMs = millis();
}

void loop() {
    canPingRecover();
    if (canPingDrain()) {
        gSawRx = true;
    }
    const uint32_t now = millis();
    if (static_cast<int32_t>(now - gNextTxMs) < 0) {
        delay(10);
        return;
    }
    gNextTxMs = now + kCanPingPeriodMs;
    const bool sent = canPingSend(kCanPingIdCore, kCanPingNodeCore, gSeq);
    Serial.printf("TX id=0x%03X seq=%lu %s\n",
                  kCanPingIdCore,
                  static_cast<unsigned long>(gSeq),
                  sent ? "ok" : "fail");
    ++gSeq;
    if (!gSawRx) {
        Serial.println("RX none");
    }
    gSawRx = false;
    canPingPrintBus();
    delay(10);
}
