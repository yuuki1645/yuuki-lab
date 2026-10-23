/**
 * 左もも PaHub 0x71 の CH4 を開いたままにする。
 *
 * エンコーダ側の「1」が、チャンネルを開いたあと何 V になるかを測るため。
 * プローブは、0x71 の CH4 の黄（SDA）と黒（GND）。
 *
 * pio run -e i2c-hold -t upload
 * 戻すときは pio run -e core-s3 -t upload。
 *
 * 内部 I2C は AW9523 で PORT.A の 5V を出すだけ。IMU と RTC は読まない。
 */

#include <Arduino.h>
#include <Wire.h>

// Grove PORT.A。黄が SDA、白が SCL。
static constexpr int kSdaPin = 2;
static constexpr int kSclPin = 1;
static constexpr int kIntSdaPin = 12;
static constexpr int kIntSclPin = 11;
static constexpr uint32_t kI2cHz = 100000;
static constexpr uint32_t kI2cTimeoutMs = 20;

static constexpr uint8_t kAw9523Addr = 0x58;
static constexpr uint8_t kAwOutP0 = 0x02;
static constexpr uint8_t kAwCtl = 0x11;
static constexpr uint8_t kAwGpomdPushPull = 0x10;
static constexpr uint8_t kAwBusEnBit = 0x02;
static constexpr uint8_t kAwBoostEnBit = 0x80;

// 測定で開いたままにする先。左もも、CH4。
static constexpr uint8_t kHoldHub = 0x71;
static constexpr int kHoldChannel = 4;
static constexpr uint8_t kAs5600Addr = 0x36;

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

/** Grove の 5V を出す。P0 をプッシュ・プルにしてから BUS_EN と BOOST_EN を書く。 */
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

static bool i2cPing(uint8_t addr) {
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;
}

/** 0x71 以外の PaHub を閉じる。別ハブのチャンネルが親バスに残らないようにする。 */
static void closeOtherHubs() {
    for (uint8_t hub = 0x70; hub <= 0x77; ++hub) {
        if (hub == kHoldHub || !i2cPing(hub)) {
            continue;
        }
        Wire.beginTransmission(hub);
        Wire.write(0);
        Wire.endTransmission();
    }
}

/**
 * 0x71 の CH4 だけを開く。0 を書いてから開き直すと、測定中に線が浮く。
 * マスクの再送だけにする。
 */
static bool holdChannel() {
    Wire.beginTransmission(kHoldHub);
    Wire.write(static_cast<uint8_t>(1u << kHoldChannel));
    return Wire.endTransmission() == 0;
}

void setup() {
    // begin より前でないと、送信バッファが 256 バイトのままになる。
    Serial.setTxBufferSize(1024);
    Serial.begin(115200);
    Serial.setTxTimeoutMs(50);

    if (!enableGrovePower()) {
        Serial.println("Grove 5V 失敗");
    }

    Wire.begin(kSdaPin, kSclPin, kI2cHz);
    Wire.setTimeOut(kI2cTimeoutMs);
    closeOtherHubs();
    holdChannel();
    delay(2);
}

void loop() {
    // 開いたまま、0x36 に返事があるかを 2 秒ごとに出す。
    const bool open = holdChannel();
    delay(2);
    const bool ack = open && i2cPing(kAs5600Addr);
    Serial.printf("hub %02X ch%d %s  0x36 %s\n", kHoldHub, kHoldChannel,
                  open ? "open" : "切替失敗", ack ? "ACK" : "なし");
    delay(2000);
}
