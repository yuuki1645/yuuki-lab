#pragma once

#include <Arduino.h>
#include <Wire.h>

/**
 * M5Stack Unit INA226（I2C 0x41）の簡易ドライバ。
 *
 * バス電圧は LSB=1.25mV。電流はシャント電圧 / Rshunt。
 * 既定は Unit INA226-10A（シャント 5mΩ、±10A）。
 * 1A ユニットなら kShuntOhm=0.08、kMaxAmp=1.0 に変える。
 */
class Ina226 {
public:
    static constexpr uint8_t kI2cAddress = 0x41;
    static constexpr uint8_t kRegConfig = 0x00;
    static constexpr uint8_t kRegShunt = 0x01;
    static constexpr uint8_t kRegBus = 0x02;
    static constexpr uint8_t kRegCal = 0x05;

    // 平均16、変換 1.1ms、シャント+バス連続
    static constexpr uint16_t kConfigContinuous = 0x4527;

    explicit Ina226(float shuntOhm = 0.005f, float maxAmp = 10.0f)
        : shuntOhm_(shuntOhm), maxAmp_(maxAmp), addr_(kI2cAddress) {}

    /** プロファイルの ina_addr を使う（既定 0x41）。 */
    void setAddress(uint8_t addr) { addr_ = addr; }

    bool isConnected() {
        Wire.beginTransmission(addr_);
        return Wire.endTransmission() == 0;
    }

    bool begin() {
        if (!isConnected()) {
            return false;
        }
        if (!write16(kRegConfig, kConfigContinuous)) {
            return false;
        }
        // CAL = 0.00512 / (Current_LSB * Rshunt)
        const float currentLsb = maxAmp_ / 32768.0f;
        const uint16_t cal = static_cast<uint16_t>(0.00512f / (currentLsb * shuntOhm_) + 0.5f);
        return write16(kRegCal, cal);
    }

    /**
     * @return 成功なら true。volt[V], amp[A], watt[W]
     */
    bool read(float& volt, float& amp, float& watt) {
        uint16_t busRaw = 0;
        int16_t shuntRaw = 0;
        if (!read16(kRegBus, busRaw) || !read16s(kRegShunt, shuntRaw)) {
            return false;
        }
        volt = static_cast<float>(busRaw) * 0.00125f;
        const float vShunt = static_cast<float>(shuntRaw) * 2.5e-6f;
        amp = vShunt / shuntOhm_;
        watt = volt * amp;
        return true;
    }

private:
    float shuntOhm_;
    float maxAmp_;
    uint8_t addr_;

    bool write16(uint8_t reg, uint16_t value) {
        Wire.beginTransmission(addr_);
        Wire.write(reg);
        Wire.write(static_cast<uint8_t>(value >> 8));
        Wire.write(static_cast<uint8_t>(value & 0xFF));
        return Wire.endTransmission() == 0;
    }

    bool read16(uint8_t reg, uint16_t& value) {
        Wire.beginTransmission(addr_);
        Wire.write(reg);
        if (Wire.endTransmission() != 0) {
            return false;
        }
        if (Wire.requestFrom(addr_, static_cast<uint8_t>(2)) != 2) {
            return false;
        }
        value = static_cast<uint16_t>(Wire.read() << 8);
        value |= static_cast<uint16_t>(Wire.read());
        return true;
    }

    bool read16s(uint8_t reg, int16_t& value) {
        uint16_t raw = 0;
        if (!read16(reg, raw)) {
            return false;
        }
        value = static_cast<int16_t>(raw);
        return true;
    }
};
