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
 * チャンネル選択: コントロールレジスタへ (1 << ch) を書く。
 */
class PaHub {
public:
    static constexpr uint8_t kDefaultAddress = 0x70;
    static constexpr int kChannelCount = 6;

    explicit PaHub(uint8_t address = kDefaultAddress) : address_(address) {}

    bool isConnected() {
        Wire.beginTransmission(address_);
        return Wire.endTransmission() == 0;
    }

    /**
     * 指定チャンネルだけを開く。ch が範囲外なら全オフ。
     * @return endTransmission の結果（0 なら成功）
     */
    uint8_t select(int channel) {
        uint8_t mask = 0;
        if (channel >= 0 && channel < kChannelCount) {
            mask = static_cast<uint8_t>(1u << channel);
        }
        Wire.beginTransmission(address_);
        Wire.write(mask);
        return Wire.endTransmission();
    }

    uint8_t address() const { return address_; }

private:
    uint8_t address_;
};
