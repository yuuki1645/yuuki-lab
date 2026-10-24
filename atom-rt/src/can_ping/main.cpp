/**
 * ATOM S3R と CoreS3 の CAN 疎通試験。本線の rt-usb とは別の書き込み対象。
 *
 * pio run -e can-ping -t upload
 * 戻すときは pio run -e rt-usb -t upload。
 *
 * Atomic CAN ベース（CA-IS3050G）を底面に挿す。
 * 公式例と同じく GPIO5 が送信、GPIO6 が受信。
 * バスが黙ったままなら、この 2 本を入れ替えて焼き直す。
 * Grove（G1/G2）は触らない。ベースの電源は ATOM の 5V から取る。
 *
 * 500 kbps。1 秒ごとに 0x101 を送り、受け取ったフレームを USB シリアルへ出す。
 * 机上の 2 台は両方とも端なので、120 Ω は両方に付ける。
 */

#include <Arduino.h>

#include "can_ping.hpp"

static constexpr int kCanTxPin = 5;
static constexpr int kCanRxPin = 6;

static uint32_t gSeq = 0;
static uint32_t gNextTxMs = 0;
static bool gSawRx = false;

static void printBanner() {
    Serial.println("can-ping atom");
    Serial.printf("twai 500k tx=%d rx=%d id=0x%03X\n", kCanTxPin, kCanRxPin, kCanPingIdAtom);
}

void setup() {
    Serial.begin(115200);
    Serial.setTxBufferSize(1024);
    delay(200);
    printBanner();
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
    const bool sent = canPingSend(kCanPingIdAtom, kCanPingNodeAtom, gSeq);
    Serial.printf("TX id=0x%03X seq=%lu %s\n",
                  kCanPingIdAtom,
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
