/**
 * CoreS3 の Grove I2C だけを見る机上スキャナ。
 *
 * 腰の本線（ver 15）とは別の書き込み対象。pio run -e i2c-scan -t upload。
 * 戻すときは pio run -e core-s3 -t upload。
 *
 * 内部 I2C は AW9523 で PORT.A の 5V を出すためだけに開く。
 * IMU と RTC は読まない。Grove は GPIO2=SDA、GPIO1=SCL。
 */

#include <Arduino.h>
#include <Wire.h>

#include <cstdarg>
#include <cstdio>

// Grove PORT.A。黄が SDA、白が SCL。
static constexpr int kSdaPin = 2;
static constexpr int kSclPin = 1;
// 基板内の AW9523。PORT.A の 5V 負荷スイッチ。
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

// チャンネルを開いてから下流が ACK するまで。本線のスキャンと同じ 2 ms。
static constexpr uint32_t kMuxSettleMs = 2;
static constexpr int kHubChannels = 6;

// USB CDC の送信バッファは 256 バイトしかなく、モニタが開く前の文字は捨てられる。
// 結果はここに貯めて、loop から繰り返す。
static char gReport[4096];
static size_t gReportLen = 0;

/** スキャン結果を RAM に足す。USB がまだ開いていなくても失わない。 */
static void reportf(const char* fmt, ...) {
    if (gReportLen + 1 >= sizeof(gReport)) {
        return;
    }
    va_list args;
    va_start(args, fmt);
    const int wrote = vsnprintf(gReport + gReportLen, sizeof(gReport) - gReportLen, fmt, args);
    va_end(args);
    if (wrote > 0) {
        const size_t room = sizeof(gReport) - 1 - gReportLen;
        gReportLen += (static_cast<size_t>(wrote) < room) ? static_cast<size_t>(wrote) : room;
    }
}

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
    // 昇圧が立ち上がり、未給電の素子が SDA/SCL を離すまで待つ。
    delay(50);
    return true;
}

/** アドレス 1 バイトだけを書き、ACK なら true。 */
static bool i2cPing(uint8_t addr) {
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;
}

/** この機体でよく出るアドレスに名前を付ける。未知はそのまま。 */
static const char* addrName(uint8_t addr) {
    if (addr == 0x36) {
        return " as5600";
    }
    if (addr == 0x40 || addr == 0x41) {
        return " ina226";
    }
    if (addr == 0x25) {
        return " servo";
    }
    if (addr == 0x28) {
        return " foot";
    }
    if (addr >= 0x70 && addr <= 0x77) {
        return " pahub";
    }
    return "";
}

/**
 * 0x08〜0x77 を叩く。rootHit に載っているアドレスは親バスなので飛ばす。
 * PaHub 自身はチャンネルを開いても親に残るため、下流の一覧から除く。
 */
static int scanBus(const char* title, const uint8_t* rootHit) {
    reportf("%s", title);
    int n = 0;
    for (uint8_t addr = 0x08; addr <= 0x77; ++addr) {
        if (rootHit[addr] != 0) {
            continue;
        }
        if (!i2cPing(addr)) {
            continue;
        }
        reportf(" %02X%s", addr, addrName(addr));
        ++n;
    }
    if (n == 0) {
        reportf(" (なし)");
    }
    reportf("\n");
    return n;
}

/** 親バスを走査し、応答したアドレスを rootHit に残す。 */
static int scanRoot(uint8_t* rootHit) {
    reportf("root");
    int n = 0;
    for (uint8_t addr = 0x08; addr <= 0x77; ++addr) {
        if (!i2cPing(addr)) {
            continue;
        }
        rootHit[addr] = 1;
        reportf(" %02X%s", addr, addrName(addr));
        ++n;
    }
    if (n == 0) {
        reportf(" (なし)");
    }
    reportf("\n");
    return n;
}

/** 見つかった PaHub を全部閉じる。他チャンネルの素子が親バスに残らないようにする。 */
static void closeHubs(const uint8_t* rootHit) {
    for (uint8_t hub = 0x70; hub <= 0x77; ++hub) {
        if (rootHit[hub] == 0) {
            continue;
        }
        Wire.beginTransmission(hub);
        Wire.write(0);
        Wire.endTransmission();
    }
}

/** 1 台の 1 チャンネルだけを開く。ch が負ならそのハブは閉じたまま。 */
static bool selectChannel(const uint8_t* rootHit, uint8_t hub, int ch) {
    closeHubs(rootHit);
    if (ch < 0) {
        return true;
    }
    Wire.beginTransmission(hub);
    Wire.write(static_cast<uint8_t>(1u << ch));
    if (Wire.endTransmission() != 0) {
        return false;
    }
    delay(kMuxSettleMs);
    return true;
}

/** 貯めた結果を USB へ出す。256 バイトの既定バッファでは途中で消える。 */
static void publishReport() {
    if (gReportLen == 0) {
        return;
    }
    Serial.write(reinterpret_cast<const uint8_t*>(gReport), gReportLen);
}

void setup() {
    // begin より前でないと、既定の 256 バイトのまま固定される。
    Serial.setTxBufferSize(8192);
    Serial.begin(115200);
    Serial.setTxTimeoutMs(50);
    reportf("i2c-scan\n");

    if (enableGrovePower()) {
        reportf("Grove 5V ON\n");
    } else {
        reportf("Grove 5V 失敗\n");
    }

    Wire.begin(kSdaPin, kSclPin, kI2cHz);
    Wire.setTimeOut(kI2cTimeoutMs);

    uint8_t rootHit[128] = {};
    scanRoot(rootHit);

    for (uint8_t hub = 0x70; hub <= 0x77; ++hub) {
        if (rootHit[hub] == 0) {
            continue;
        }
        for (int ch = 0; ch < kHubChannels; ++ch) {
            char title[28];
            snprintf(title, sizeof(title), "hub %02X ch%d", hub, ch);
            if (!selectChannel(rootHit, hub, ch)) {
                reportf("%s 切替失敗\n", title);
                continue;
            }
            // 親バスのハブ自身は毎チャンネルに出るので、rootHit は表示しない。
            scanBus(title, rootHit);
        }
        selectChannel(rootHit, hub, -1);
    }
    reportf("done\n");
    publishReport();
}

void loop() {
    // モニタはリセットより後に開かれる。同じ文章を繰り返して、開いた側に届ける。
    publishReport();
    delay(2000);
}
