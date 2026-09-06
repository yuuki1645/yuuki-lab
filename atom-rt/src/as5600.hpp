#pragma once

#include <Arduino.h>
#include <Wire.h>

/**
 * AS5600 磁気角度センサ（I2C）ドライバ。
 *
 * I2C スレーブアドレスは固定 0x36。
 * 角度は 12bit（0〜4095）で、360度に換算して返す。
 */
class As5600 {
public:
    /// AS5600 の固定 I2C アドレス
    static constexpr uint8_t kI2cAddress = 0x36;

    /// 磁石の検出状態（STATUS レジスタ 0x0B）
    enum class MagnetStatus : uint8_t {
        None,      ///< 磁石未検出（MD=0）
        Ok,        ///< 適正距離（MD=1, ML=0, MH=0）
        TooWeak,   ///< 磁場が弱すぎる（ML=1）
        TooStrong, ///< 磁場が強すぎる（MH=1）
        CommError, ///< I2C 通信失敗
    };

    /**
     * I2C バスを初期化する。
     * @param sda SDA ピン（ATOMS3 Lite Grove は GPIO2）
     * @param scl SCL ピン（ATOMS3 Lite Grove は GPIO1）
     * @param clockHz I2C クロック。Grove + ESP32 では 100kHz の方が安定する
     */
    void begin(int sda, int scl, uint32_t clockHz = 100000);

    /**
     * バス上に AS5600 が応答するか確認する。
     * @return 応答があれば true
     */
    bool isConnected();

    /**
     * スケーリング済み角度レジスタ（ANGLE 0x0E/0x0F）を読む。
     * ゼロ位置・ヒステリシス適用後の値。
     * @param raw 12bit 生値（0〜4095）の出力先
     * @return 読み取り成功なら true
     */
    bool readRawAngle(uint16_t& raw);

    /**
     * 角度を度（0.0〜360.0）で返す。
     * @param degrees 角度の出力先
     * @return 読み取り成功なら true
     */
    bool readDegrees(float& degrees);

    /**
     * 磁石の検出状態を返す。
     * STATUS: bit5=MD, bit4=ML, bit3=MH
     */
    MagnetStatus readMagnetStatus();

    /**
     * AGC（自動ゲイン, レジスタ 0x1A）。
     * 3.3V ではおおむね 0〜128。距離・偏心の目安。
     */
    bool readAgc(uint8_t& agc);

    /**
     * 磁場強度 MAGNITUDE（0x1B/0x1C, 12bit）。
     */
    bool readMagnitude(uint16_t& magnitude);

    /// テレメトリ用の短いコード。0=OK 1=無し 2=弱い 3=強い 4=通信
    static uint8_t statusToCode(MagnetStatus status);

    /// 磁石状態を人間向けの文字列にする
    static const char* statusToString(MagnetStatus status);

private:
    /// 指定レジスタから 1 バイト読む
    bool readRegister(uint8_t reg, uint8_t& value);

    /// 指定レジスタから連続 2 バイト読む（12bit 角度用）
    bool readRegister16(uint8_t reg, uint16_t& value);
};
