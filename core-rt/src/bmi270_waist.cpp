/**
 * BMI270 の初期化と読み取り。
 *
 * 設定バイトは M5Unified が配布している Bosch の初期化ファイル（8192 バイト）。
 * チップはこれを書かないと加速度も角速度も出さない。中身は改変しない。
 *
 * 加速度は ±4 g（レジスタ 0x41 = 1）。1 LSB = 4/32768 g。
 * 角速度は ±2000 deg/s（レジスタ 0x43 = 0）。1 LSB = 2000/32768 deg/s。
 * 設定ファイルが別のレンジを書いていても、初期化のあとでこの値に上書きする。
 */

#include "bmi270_waist.hpp"

#include <Arduino.h>
#include <Wire.h>
#include <string.h>

static constexpr uint8_t kAddr = 0x69;
static constexpr uint8_t kChipId = 0x24;

static constexpr uint8_t kRegChipId = 0x00;
static constexpr uint8_t kRegAcc = 0x0C;
static constexpr uint8_t kRegInternal = 0x21;
static constexpr uint8_t kRegAccConf = 0x40;
static constexpr uint8_t kRegAccRange = 0x41;
static constexpr uint8_t kRegGyrConf = 0x42;
static constexpr uint8_t kRegGyrRange = 0x43;
static constexpr uint8_t kRegInitCtrl = 0x59;
static constexpr uint8_t kRegInitAddr = 0x5B;
static constexpr uint8_t kRegInitData = 0x5E;
static constexpr uint8_t kRegPwrConf = 0x7C;
static constexpr uint8_t kRegPwrCtrl = 0x7D;
static constexpr uint8_t kRegCmd = 0x7E;

static constexpr uint8_t kCmdSoftReset = 0xB6;
// 100 Hz、性能モード、平均 4。odr=0x08、bwp=2、filter_perf=1。
static constexpr uint8_t kConf100Hz = 0xA8;
static constexpr uint8_t kAccRange4G = 0x01;
static constexpr uint8_t kGyrRange2000 = 0x00;
// 温度・加速度・角速度。磁気の補助センサは無い。
static constexpr uint8_t kPwrAccGyr = 0x0E;

// 設定データのバーストは 32 バイト。アドレスの下位が 16 ワードで一周するため。
static constexpr size_t kConfigChunk = 32;
static constexpr uint32_t kStaleUs = 100000;

static constexpr float kAccGPerLsb = 4.0f / 32768.0f;
static constexpr float kGyroRadPerLsb = (2000.0f / 32768.0f) * 0.01745329252f;

static const uint8_t kBmi270Config[] = {
#include "bmi270_config.inc"
};

static bool gReady = false;
static uint32_t gLastUs = 0;
static float gLastForce[3] = {};
static float gLastGyro[3] = {};

/**
 * チップ軸から体軸への対応。ここだけを直す。
 *
 * 体は前が +x、左が +y、上が +z。
 * 返す値は比力。止まって上を向く軸が +1 g。方策が欲しい重力は逆向きで、
 * その反転は walk_policy.cpp の式が行う。ここにマイナスを重ねて足さない。
 *
 * カゴへの取り付けは未計測。初期値はチップ軸をそのまま体軸とみなす。
 * CoreS3 の画面を上、USB コネクタをロボットの後ろに向けたとき、
 * 直立の重力（反転後）が (0, 0, -1) になるかを、方策を入れる前に確認する。
 * z が約 +1 なら、その軸の符号だけを反転する。x と y が入れ替わっていれば、
 * 軸番号だけを入れ替える。ほかのファイルでは直さない。
 *
 * kBodyAxis[i] は体の i 軸に載せるチップ軸（0=x, 1=y, 2=z）。
 * kBodySign[i] はその符号。+1 か -1。
 */
static constexpr int kBodyAxis[3] = {0, 1, 2};
static constexpr int kBodySign[3] = {1, 1, 1};

static bool writeReg(uint8_t reg, const uint8_t* data, size_t n) {
    Wire1.beginTransmission(kAddr);
    Wire1.write(reg);
    if (n > 0 && Wire1.write(data, n) != n) {
        return false;
    }
    return Wire1.endTransmission(true) == 0;
}

static bool writeU8(uint8_t reg, uint8_t value) {
    return writeReg(reg, &value, 1);
}

static bool readReg(uint8_t reg, uint8_t* data, size_t n) {
    Wire1.beginTransmission(kAddr);
    Wire1.write(reg);
    if (Wire1.endTransmission(false) != 0) {
        return false;
    }
    if (Wire1.requestFrom(static_cast<int>(kAddr), static_cast<int>(n)) != static_cast<int>(n)) {
        return false;
    }
    for (size_t i = 0; i < n; ++i) {
        data[i] = static_cast<uint8_t>(Wire1.read());
    }
    return true;
}

static int16_t s16le(uint8_t lo, uint8_t hi) {
    return static_cast<int16_t>(static_cast<uint16_t>(lo) | (static_cast<uint16_t>(hi) << 8));
}

/** Bosch の手順。アドレスはバイト位置 / 2 で、32 バイトごとに書き直す。 */
static bool uploadConfig() {
    if (!writeU8(kRegInitCtrl, 0x00)) {
        return false;
    }
    size_t index = 0;
    const size_t total = sizeof(kBmi270Config);
    while (index < total) {
        size_t n = total - index;
        if (n > kConfigChunk) {
            n = kConfigChunk;
        }
        uint8_t addr[2] = {
            static_cast<uint8_t>((index >> 1) & 0x0F),
            static_cast<uint8_t>(index >> 5),
        };
        if (!writeReg(kRegInitAddr, addr, 2)) {
            return false;
        }
        if (!writeReg(kRegInitData, kBmi270Config + index, n)) {
            return false;
        }
        index += n;
    }
    if (!writeU8(kRegInitCtrl, 0x01)) {
        return false;
    }
    // 下位 4 ビットが 1 なら初期化成功。2 は失敗なので、非ゼロだけでは通さない。
    for (int i = 0; i < 100; ++i) {
        uint8_t status = 0;
        if (readReg(kRegInternal, &status, 1) && (status & 0x0F) == 0x01) {
            return true;
        }
        delay(10);
    }
    return false;
}

static void mapChip(const float chip[3], float body[3]) {
    for (int i = 0; i < 3; ++i) {
        body[i] = static_cast<float>(kBodySign[i]) * chip[kBodyAxis[i]];
    }
}

bool bmi270Begin() {
    gReady = false;
    gLastUs = 0;
    uint8_t id = 0;
    if (!readReg(kRegChipId, &id, 1) || id != kChipId) {
        return false;
    }
    if (!writeU8(kRegCmd, kCmdSoftReset)) {
        return false;
    }
    delay(5);
    for (int i = 0; i < 16; ++i) {
        uint8_t pwr = 0;
        if (readReg(kRegPwrConf, &pwr, 1) && pwr != 0) {
            break;
        }
        delay(1);
    }
    if (!writeU8(kRegPwrConf, 0x00)) {
        return false;
    }
    delay(2);
    if (!uploadConfig()) {
        return false;
    }
    // レンジは設定ファイルのあとで固定する。尺度は上の定数と対。
    if (!writeU8(kRegPwrCtrl, kPwrAccGyr) || !writeU8(kRegAccConf, kConf100Hz) ||
        !writeU8(kRegAccRange, kAccRange4G) || !writeU8(kRegGyrConf, kConf100Hz) ||
        !writeU8(kRegGyrRange, kGyrRange2000)) {
        return false;
    }
    delay(50);
    gReady = true;
    return true;
}

bool bmi270Read(float specific_force_g[3], float gyro_rad_s[3]) {
    if (specific_force_g == nullptr || gyro_rad_s == nullptr) {
        return false;
    }
    uint8_t raw[12] = {};
    bool ok = gReady && readReg(kRegAcc, raw, sizeof(raw));
    if (ok) {
        float chip_acc[3];
        float chip_gyro[3];
        for (int i = 0; i < 3; ++i) {
            const int16_t acc = s16le(raw[i * 2], raw[i * 2 + 1]);
            const int16_t gyr = s16le(raw[6 + i * 2], raw[6 + i * 2 + 1]);
            chip_acc[i] = static_cast<float>(acc) * kAccGPerLsb;
            chip_gyro[i] = static_cast<float>(gyr) * kGyroRadPerLsb;
        }
        mapChip(chip_acc, gLastForce);
        mapChip(chip_gyro, gLastGyro);
        gLastUs = micros();
    } else if (gLastUs == 0 || (micros() - gLastUs) > kStaleUs) {
        return false;
    }
    memcpy(specific_force_g, gLastForce, sizeof(gLastForce));
    memcpy(gyro_rad_s, gLastGyro, sizeof(gLastGyro));
    return true;
}

uint16_t bmi270AgeMs() {
    if (!gReady || gLastUs == 0) {
        return 65535;
    }
    const uint32_t age_us = micros() - gLastUs;
    const uint32_t age_ms = age_us / 1000u;
    return age_ms > 65535u ? 65535 : static_cast<uint16_t>(age_ms);
}
