#pragma once

#include <Arduino.h>
#include <FastLED.h>

// =============================================================================
// ATOMS3 Lite 共通ハードウェア
//   - 正面 WS2812C / SK6812 RGB LED (GPIO35)
//   - 正面ボタン (GPIO41, 押下で LOW)
//   - Grove PORT.CUSTOM: SDA=G2, SCL=G1
// =============================================================================

static constexpr int kPinLed = 35;
static constexpr int kPinButton = 41;
static constexpr int kPinSda = 2;
static constexpr int kPinScl = 1;
static constexpr int kNumLeds = 1;
static constexpr uint8_t kLedBrightness = 48;

// USB CDC 列挙待ちの上限。Grove 給電のみのスレーブでも先に進む
static constexpr uint32_t kSerialWaitMs = 2000;

inline CRGB* rgbLedArray() {
    static CRGB leds[kNumLeds];
    return leds;
}

inline void setRgbLed(uint8_t r, uint8_t g, uint8_t b) {
    rgbLedArray()[0] = CRGB(r, g, b);
    FastLED.show();
}

/** LED とシリアルだけ初期化する。I2C は各ファームでピンを明示する。 */
inline void beginAtoms3Lite(const char* role_name) {
    pinMode(kPinButton, INPUT_PULLUP);
    pinMode(kPinLed, OUTPUT);
    FastLED.addLeds<SK6812, kPinLed, GRB>(rgbLedArray(), kNumLeds);
    FastLED.setBrightness(kLedBrightness);
    FastLED.clear(true);

    Serial.begin(115200);
    const uint32_t start_ms = millis();
    while (!Serial && (millis() - start_ms) < kSerialWaitMs) {
        delay(10);
    }

    Serial.println();
    Serial.println("========================================");
    Serial.printf("ATOMS3 Lite on-foot  %s\n", role_name);
    Serial.println("========================================");
}

inline bool buttonPressed() {
    return digitalRead(kPinButton) == LOW;
}
