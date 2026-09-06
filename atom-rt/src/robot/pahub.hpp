#pragma once

#include <Arduino.h>
#include <Wire.h>

/**
 * M5Stack Unit PaHub v2.1（PCA9548AP）のチャンネル切替。
 *
 * I2C アドレスは DIP で 0x70〜0x77。工場出荷は 0x70。
 * 本機は AS5600 用 0x70 と INA226 用 0x71 を同時接続する。
 * 開いた CH の先は親バスに乗る。複数台では他 Hub を全オフしてから 1 CH だけ開く。
 * 拡張ポートは CH0〜CH5 の 6 つ。
 * チャンネル選択: コントロールレジスタへ (1 << ch) を書く。0 で全オフ。
 * 書いたあとレジスタを読み、一致するまで再送する（閉じ漏れ・開き漏れ対策）。
 */
class PaHub {
public:
    static constexpr uint8_t kDefaultAddress = 0x70;
    static constexpr int kChannelCount = 6;
    static constexpr int kSelectRetries = 4;

    explicit PaHub(uint8_t address = kDefaultAddress) : address_(address) {}

    bool isConnected() {
        Wire.beginTransmission(address_);
        return Wire.endTransmission() == 0;
    }

    /**
     * コントロールレジスタを読む。read 非対応クローンは false。
     */
    bool readMask(uint8_t& mask) const {
        const int n = Wire.requestFrom(address_, static_cast<uint8_t>(1));
        if (n < 1) {
            return false;
        }
        mask = static_cast<uint8_t>(Wire.read());
        return true;
    }

    /**
     * mask を書いて読み戻す。一致するまで最大 kSelectRetries 回。
     * 読み戻せない互換品は write ACK だけで成功とみなす。
     */
    bool selectMask(uint8_t mask) {
        bool wroteOk = false;
        for (int i = 0; i < kSelectRetries; ++i) {
            Wire.beginTransmission(address_);
            Wire.write(mask);
            if (Wire.endTransmission() != 0) {
                delayMicroseconds(200);
                continue;
            }
            wroteOk = true;
            uint8_t got = 0xFF;
            if (!readMask(got)) {
                return true;
            }
            if (got == mask) {
                return true;
            }
            delayMicroseconds(200);
        }
        return wroteOk;
    }

    /**
     * 指定チャンネルだけを開く。ch が範囲外なら全オフ。
     * @return 書き込み（と可能なら読み戻し）が成功したか
     */
    bool select(int channel) {
        uint8_t mask = 0;
        if (channel >= 0 && channel < kChannelCount) {
            mask = static_cast<uint8_t>(1u << channel);
        }
        return selectMask(mask);
    }

    uint8_t address() const { return address_; }

private:
    uint8_t address_;
};
