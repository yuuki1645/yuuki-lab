#include "as5600.hpp"

// データシート上の主要レジスタ
// STATUS     0x0B : MD / ML / MH
// RAW ANGLE  0x0C : 未加工 12bit 角度（上位 4bit + 下位 8bit）
// ANGLE      0x0E : ゼロ位置・ヒステリシス適用後の 12bit 角度
// AGC        0x1A : 自動ゲイン
// MAGNITUDE  0x1B : 磁場強度 12bit
static constexpr uint8_t kRegStatus = 0x0B;
static constexpr uint8_t kRegAngle = 0x0E;
static constexpr uint8_t kRegAgc = 0x1A;
static constexpr uint8_t kRegMagnitude = 0x1B;

// STATUS ビット（データシート Figure 23）
static constexpr uint8_t kStatusMd = 0x20;  // Magnet Detected
static constexpr uint8_t kStatusMl = 0x10;  // Magnet too Low (weak)
static constexpr uint8_t kStatusMh = 0x08;  // Magnet too High (strong)

// ESP32 Wire の Repeated START が失敗しやすいので、失敗時はやり直す
static constexpr uint8_t kMaxRetries = 3;

void As5600::begin(int sda, int scl, uint32_t clockHz) {
    Wire.begin(sda, scl);
    Wire.setClock(clockHz);
    // ハング防止。デフォルト 50ms だと失敗時にログが詰まる
    Wire.setTimeOut(20);
}

bool As5600::isConnected() {
    Wire.beginTransmission(kI2cAddress);
    return Wire.endTransmission() == 0;
}

bool As5600::readRegister(uint8_t reg, uint8_t& value) {
    for (uint8_t attempt = 0; attempt < kMaxRetries; ++attempt) {
        // STOP を挟む。endTransmission(false) は ESP32 で
        // i2cWriteReadNonStop Error -1 になりやすい
        Wire.beginTransmission(kI2cAddress);
        Wire.write(reg);
        if (Wire.endTransmission() != 0) {
            delayMicroseconds(200);
            continue;
        }

        const uint8_t n = Wire.requestFrom(kI2cAddress, static_cast<uint8_t>(1));
        if (n != 1) {
            delayMicroseconds(200);
            continue;
        }

        value = static_cast<uint8_t>(Wire.read());
        return true;
    }
    return false;
}

bool As5600::readRegister16(uint8_t reg, uint16_t& value) {
    for (uint8_t attempt = 0; attempt < kMaxRetries; ++attempt) {
        Wire.beginTransmission(kI2cAddress);
        Wire.write(reg);
        if (Wire.endTransmission() != 0) {
            delayMicroseconds(200);
            continue;
        }

        const uint8_t n = Wire.requestFrom(kI2cAddress, static_cast<uint8_t>(2));
        if (n != 2) {
            delayMicroseconds(200);
            continue;
        }

        const uint8_t high = static_cast<uint8_t>(Wire.read());
        const uint8_t low = static_cast<uint8_t>(Wire.read());
        // 有効なのは下位 12bit のみ
        value = static_cast<uint16_t>(((high & 0x0F) << 8) | low);
        return true;
    }
    return false;
}

bool As5600::readRawAngle(uint16_t& raw) {
    return readRegister16(kRegAngle, raw);
}

bool As5600::readDegrees(float& degrees) {
    uint16_t raw = 0;
    if (!readRawAngle(raw)) {
        return false;
    }
    // 4096 LSB = 360deg（12bit フルスケール）
    degrees = static_cast<float>(raw) * (360.0f / 4096.0f);
    return true;
}

As5600::MagnetStatus As5600::readMagnetStatus() {
    uint8_t status = 0;
    if (!readRegister(kRegStatus, status)) {
        return MagnetStatus::CommError;
    }

    const bool md = (status & kStatusMd) != 0;
    const bool ml = (status & kStatusMl) != 0;
    const bool mh = (status & kStatusMh) != 0;

    if (!md) {
        return MagnetStatus::None;
    }
    if (ml) {
        return MagnetStatus::TooWeak;
    }
    if (mh) {
        return MagnetStatus::TooStrong;
    }
    return MagnetStatus::Ok;
}

bool As5600::readAgc(uint8_t& agc) {
    return readRegister(kRegAgc, agc);
}

bool As5600::readMagnitude(uint16_t& magnitude) {
    return readRegister16(kRegMagnitude, magnitude);
}

uint8_t As5600::statusToCode(MagnetStatus status) {
    switch (status) {
        case MagnetStatus::Ok:
            return 0;
        case MagnetStatus::None:
            return 1;
        case MagnetStatus::TooWeak:
            return 2;
        case MagnetStatus::TooStrong:
            return 3;
        case MagnetStatus::CommError:
        default:
            return 4;
    }
}

const char* As5600::statusToString(MagnetStatus status) {
    switch (status) {
        case MagnetStatus::Ok:
            return "OK";
        case MagnetStatus::None:
            return "NO_MAGNET";
        case MagnetStatus::TooWeak:
            return "TOO_WEAK";
        case MagnetStatus::TooStrong:
            return "TOO_STRONG";
        case MagnetStatus::CommError:
            return "I2C_ERROR";
        default:
            return "UNKNOWN";
    }
}
