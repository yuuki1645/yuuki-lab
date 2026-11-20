/**
 * CoreS3 の机上ブリッジ。腰の本線（core-rt、USB ver 15）ではない。
 *
 * サブ PC の USB と、PORT.B の Grove UART のあいだで行を渡す。
 * 指令の中身は解釈しない。hello のときだけ、ATOM へ渡す前に自分の行を出す。
 * ATOM S3R はこのポートの 5V で起動する。AW9523 がオンにするまで赤線に 5V は出ない。
 * サーボの 12V はここから出さない。
 *
 * ストレートの Grove ケーブルを PORT.B と ATOM の Grove につなぐ。
 *   黄 GPIO9 = 送信 → ATOM の黄 GPIO2（受信）
 *   白 GPIO8 = 受信 ← ATOM の白 GPIO1（送信）
 *   赤 = 5V、黒 = GND
 * ATOM の USB は書き込みのときだけ挿す。そのときはこの Grove を外す。
 * 動かすときに両方の 5V をつなぐと、電源がぶつかる。
 *
 * 50 ms ごとに hb を ATOM へ足す。返事は来ない。
 * ATOM は 200 ms 行が途切れると、出力中のトルクを切る。
 */

#include <Arduino.h>
#include <Wire.h>

#include <cstring>

// PORT.B。公式ピンマップでは黄が GPIO9、白が GPIO8。
static constexpr int kLinkTxPin = 9;
static constexpr int kLinkRxPin = 8;
static constexpr uint32_t kLinkBaud = 115200;

// ATOM の 200 ms 切断より十分短い。stream 中もこの行だけで生存とみなす。
static constexpr uint32_t kHeartbeatMs = 50;

// 内部 I2C。AW9523 で Grove の 5V を出すときだけ使う。
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

// UART1。USB CDC が Serial を使う。
static HardwareSerial gLink(1);
static bool gGroveOn = false;
static uint32_t gNextHbMs = 0;

// USB から 1 行貯めて、Grove の送信バッファが空くまで保持する。hb より先に出す。
static char gLine[96];
static size_t gLineLen = 0;
static bool gLineReady = false;
static bool gDiscard = false;

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
 * Grove の 5V を出す。P0 は上電時オープン・ドレインなので、
 * GPOMD を立ててから BUS_EN と BOOST_EN を書く。
 * PORT.A / B / C の赤線は同じ負荷スイッチの先である。
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
    // 昇圧と負荷スイッチが安定してから ATOM が起動し始める。
    delay(50);
    return true;
}

static void printHello() {
    // grove=0 のときは赤線に 5V が出ておらず、ATOM は起動しない。
    Serial.printf("@hello name=core-test grove=%d tx=%d rx=%d baud=%lu\n",
                  gGroveOn ? 1 : 0,
                  kLinkTxPin,
                  kLinkRxPin,
                  static_cast<unsigned long>(kLinkBaud));
}

static void pollUsb() {
    if (gLineReady) {
        return;
    }
    while (Serial.available() > 0) {
        const char c = (char)Serial.read();
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            if (gDiscard) {
                gDiscard = false;
                gLineLen = 0;
                return;
            }
            gLine[gLineLen] = '\0';
            if (gLineLen > 0) {
                gLineReady = true;
            }
            return;
        }
        if (gDiscard) {
            continue;
        }
        if (gLineLen >= sizeof(gLine) - 1) {
            // 続きを次の行とつなぐと、別の指令になる。改行まで捨てる。
            gDiscard = true;
            gLineLen = 0;
            Serial.println("@err cmd=link msg=long");
            continue;
        }
        gLine[gLineLen++] = c;
    }
}

static void pumpLine() {
    if (!gLineReady) {
        return;
    }
    // 改行ぶんを足して、1 回で書き切れるときだけ出す。途中で hb を挟まない。
    if (gLink.availableForWrite() < gLineLen + 1) {
        return;
    }
    if (strcmp(gLine, "hello") == 0) {
        printHello();
    }
    gLink.write(reinterpret_cast<const uint8_t*>(gLine), gLineLen);
    gLink.write('\n');
    gLineReady = false;
    gLineLen = 0;
}

static void pumpHeartbeat() {
    // 貯めた指令を hb が追い越さない。
    if (gLineReady) {
        return;
    }
    const uint32_t now = millis();
    if (static_cast<int32_t>(now - gNextHbMs) < 0) {
        return;
    }
    if (gLink.availableForWrite() < 3) {
        return;
    }
    gNextHbMs = now + kHeartbeatMs;
    gLink.print("hb\n");
}

static void pollAtom() {
    while (gLink.available() > 0) {
        const uint8_t b = static_cast<uint8_t>(gLink.read());
        Serial.write(b);
    }
}

void setup() {
    // begin より前でないと、送信バッファが 256 バイトのままになる。
    // PC が読んでいなくても、ここで待って hb を止めない。
    Serial.setTxBufferSize(2048);
    Serial.begin(115200);
    Serial.setTxTimeoutMs(0);

    gGroveOn = enableGrovePower();

    gLink.setRxBufferSize(1024);
    gLink.setTxBufferSize(1024);
    gLink.begin(kLinkBaud, SERIAL_8N1, kLinkRxPin, kLinkTxPin);

    printHello();
    gNextHbMs = millis();
}

void loop() {
    pollUsb();
    pumpLine();
    pumpHeartbeat();
    pollAtom();
}
