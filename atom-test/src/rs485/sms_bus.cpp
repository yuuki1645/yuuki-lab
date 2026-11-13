#include "sms_bus.hpp"

#include <driver/gpio.h>
#include <stdio.h>
#include <string.h>

// UART2。USB CDC が Serial を使うので、RS485 はこちら。
static HardwareSerial gBus(2);
static uint8_t gId = 1;
static uint32_t gBaud = kRs485Baud;
static bool gSelfOk = false;

// 出荷の机上と同じ。サーボ EEPROM の初期 ID であり、GUI の id コマンドで宛先だけ変える。
static constexpr uint8_t kDefaultServoId = 1;
// 115200 の往復は数 ms。これを過ぎたら、そのトランザクションは失敗。
static constexpr uint32_t kReplyTimeoutMs = 30;

static uint8_t checksumOf(uint8_t id, uint8_t length, uint8_t inst, const uint8_t* params, uint8_t nparams) {
    // ~(ID + Length + Instruction + パラメータ) の下位 8bit。チェックサム自身は足さない。
    unsigned sum = (unsigned)id + length + inst;
    for (uint8_t i = 0; i < nparams; ++i) {
        sum += params[i];
    }
    return (uint8_t)(~sum);
}

static size_t buildPacket(uint8_t id, uint8_t inst, const uint8_t* params, uint8_t nparams, uint8_t* out) {
    // Length は Instruction、パラメータ、チェックサムのバイト数。FF FF と ID は含めない。
    const uint8_t length = (uint8_t)(nparams + 2);
    out[0] = 0xFF;
    out[1] = 0xFF;
    out[2] = id;
    out[3] = length;
    out[4] = inst;
    for (uint8_t i = 0; i < nparams; ++i) {
        out[5 + i] = params[i];
    }
    out[5 + nparams] = checksumOf(id, length, inst, params, nparams);
    return (size_t)(6 + nparams);
}

static void appendHex(char* dst, size_t cap, const uint8_t* data, size_t len) {
    size_t used = 0;
    if (cap == 0) {
        return;
    }
    dst[0] = '\0';
    for (size_t i = 0; i < len && used + 2 < cap; ++i) {
        used += (size_t)snprintf(dst + used, cap - used, "%02x", data[i]);
    }
}

static void pullUpRx() {
    // pinMode で引き直すと UART の割り当てが外れる。プルだけ変える。
    gpio_set_pull_mode((gpio_num_t)kRs485RxPin, GPIO_PULLUP_ONLY);
}

// 受信バッファからステータスパケットを 1 つ取り出す。足りなければ false。
// エコー（送信そのもの）は 1 回だけ捨てる。FF FF がデータ中に出ても、
// チェックサムが合う位置だけをパケットとして扱う。
static bool pullPacket(uint8_t* buf, size_t* n, const uint8_t* echo, size_t echoLen, bool* echoSkipped,
                       SmsReply* out, uint8_t* raw, size_t* rawLen) {
    size_t i = 0;
    while (i + 4 <= *n) {
        if (buf[i] != 0xFF || buf[i + 1] != 0xFF) {
            ++i;
            continue;
        }
        const uint8_t length = buf[i + 3];
        // この試験が読む最大は 40 バイト。Length = status + data + checksum なので 48 を超えたらゴミ。
        if (length < 2 || length > 48) {
            ++i;
            continue;
        }
        const size_t total = (size_t)length + 4;
        if (total > 64) {
            ++i;
            continue;
        }
        if (i + total > *n) {
            break;
        }
        if (!*echoSkipped && echoLen == total && memcmp(buf + i, echo, echoLen) == 0) {
            *echoSkipped = true;
            i += total;
            continue;
        }
        unsigned sum = (unsigned)buf[i + 2] + length;
        for (uint8_t k = 0; k < length - 1; ++k) {
            sum += buf[i + 4 + k];
        }
        const uint8_t expect = (uint8_t)(~sum);
        if (buf[i + 4 + length - 1] != expect) {
            ++i;
            continue;
        }
        memcpy(raw, buf + i, total);
        *rawLen = total;
        out->ok = true;
        out->status = buf[i + 4];
        out->len = (uint8_t)(length - 2);
        if (out->len > 0) {
            memcpy(out->data, buf + i + 5, out->len);
        }
        const size_t rest = *n - (i + total);
        memmove(buf, buf + i + total, rest);
        *n = rest;
        return true;
    }
    if (i > 0) {
        const size_t rest = *n - i;
        memmove(buf, buf + i, rest);
        *n = rest;
    }
    return false;
}

// printf を 1 本にすると、長い十六進で内部バッファを取り逃すことがある。分けて出す。
static void printBus(bool ok, bool echo, uint32_t us, const uint8_t* tx, size_t txLen, const uint8_t* rx, size_t rxLen,
                     uint8_t status) {
    char txHex[96];
    char rxHex[200];
    appendHex(txHex, sizeof(txHex), tx, txLen);
    appendHex(rxHex, sizeof(rxHex), rx, rxLen);
    Serial.printf("@bus ms=%lu us=%lu echo=%d baud=%lu tx=",
                  static_cast<unsigned long>(millis()),
                  static_cast<unsigned long>(us),
                  echo ? 1 : 0,
                  static_cast<unsigned long>(gBaud));
    Serial.print(txHex);
    Serial.print(" rx=");
    Serial.print(rxHex);
    if (ok) {
        Serial.printf(" st=%u\n", status);
        return;
    }
    Serial.printf(" n=%u err=timeout\n", static_cast<unsigned>(rxLen));
}

static void busIdle() {
    // 前の応答の残りが次のエコー判定に混ざらないように、送る前だけ捨てる。
    delayMicroseconds(150);
    while (gBus.available() > 0) {
        gBus.read();
    }
}

static void drive(const uint8_t* data, size_t len) {
    // ドライバが有効になってから出す。LTC1480 の enable は 1us より短い。
    digitalWrite(kDePin, HIGH);
    delayMicroseconds(5);
    gBus.write(data, len);
    // flush はシフトレジスタが空になるまで待つ。
    gBus.flush();
    // 115200 の 1 ビットは約 9us。最後のビットがバスを出る余裕。
    delayMicroseconds(20);
    // ここより前に DE を戻すと、末尾がサーボへ届かない。
    // 戻したあとにサーボが話す。持ったままだと返事が潰れる。
    digitalWrite(kDePin, LOW);
}

static bool transact(uint8_t inst, const uint8_t* params, uint8_t nparams, SmsReply* reply) {
    uint8_t tx[40];
    const size_t txLen = buildPacket(gId, inst, params, nparams, tx);
    reply->ok = false;
    reply->status = 0;
    reply->len = 0;

    busIdle();
    drive(tx, txLen);
    // us は DE を戻してから、返事を採るか諦めるまでの時間。
    const uint32_t listenStart = micros();

    uint8_t buf[96];
    size_t n = 0;
    bool echoSkipped = false;
    uint8_t raw[64];
    size_t rawLen = 0;
    const uint32_t start = millis();
    while ((uint32_t)(millis() - start) < kReplyTimeoutMs) {
        while (gBus.available() > 0 && n < sizeof(buf)) {
            buf[n++] = (uint8_t)gBus.read();
        }
        if (pullPacket(buf, &n, tx, txLen, &echoSkipped, reply, raw, &rawLen)) {
            printBus(true, echoSkipped, micros() - listenStart, tx, txLen, raw, rawLen, reply->status);
            return true;
        }
        if (n >= sizeof(buf)) {
            memmove(buf, buf + 32, n - 32);
            n -= 32;
        }
        delayMicroseconds(200);
    }
    // エコーは pullPacket がバッファから除いてある。残っているのは返事にならなかった列。
    printBus(false, echoSkipped, micros() - listenStart, tx, txLen, buf, n, 0);
    return false;
}

static void selfTest() {
    // ID 1 の PING。sum = 1+2+1 = 4、チェックサムは 0xFB。
    uint8_t ping[8];
    const size_t pingLen = buildPacket(1, 0x01, nullptr, 0, ping);
    const bool pingOk = pingLen == 6 && ping[0] == 0xFF && ping[1] == 0xFF && ping[2] == 0x01 && ping[3] == 0x02 &&
                        ping[4] == 0x01 && ping[5] == 0xFB;
    // ID 1 でアドレス 40 から 31 バイト読む形。このファームは読まないが、組み立ての確認に使う。
    const uint8_t readParams[2] = {40, 31};
    uint8_t readPkt[8];
    const size_t readLen = buildPacket(1, 0x02, readParams, 2, readPkt);
    const bool readOk = readLen == 8 && readPkt[5] == 0x28 && readPkt[6] == 0x1F && readPkt[7] == 0xB1;
    // トルク切断。アドレス 40 に 0。チェックサムは 0xCF。
    const uint8_t offParams[2] = {40, 0};
    uint8_t offPkt[8];
    const size_t offLen = buildPacket(1, 0x03, offParams, 2, offPkt);
    const bool offOk = offLen == 8 && offPkt[4] == 0x03 && offPkt[5] == 0x28 && offPkt[6] == 0x00 && offPkt[7] == 0xCF;
    gSelfOk = pingOk && readOk && offOk;
    if (!gSelfOk) {
        Serial.println("@err cmd=self msg=checksum");
    }
}

bool smsSelfOk() {
    return gSelfOk;
}

void smsBegin() {
    // UART を開くより先にドライバを離す。浮いている DE は送信側に倒れうる。
    pinMode(kDePin, OUTPUT);
    digitalWrite(kDePin, LOW);
    gId = kDefaultServoId;
    gBaud = kRs485Baud;
    gBus.setRxBufferSize(256);
    gBus.begin(gBaud, SERIAL_8N1, kRs485RxPin, kRs485TxPin);
    pullUpRx();
    selfTest();
}

void smsSetId(uint8_t id) {
    gId = id;
}

uint8_t smsId() {
    return gId;
}

void smsSetBaud(uint32_t baud) {
    gBaud = baud;
    gBus.updateBaudRate(baud);
    pullUpRx();
}

uint32_t smsBaud() {
    return gBaud;
}

bool smsProbeEcho() {
    // FF FF で始まらない。サーボはこれを指令として採らない。トランシーバの往復だけを見る。
    static const uint8_t kTx[] = {0x55, 0xAA, 0x55, 0xAA};
    busIdle();
    drive(kTx, sizeof(kTx));
    const uint32_t listenStart = micros();

    uint8_t rx[32];
    size_t n = 0;
    while ((uint32_t)(micros() - listenStart) < 8000 && n < sizeof(rx)) {
        while (gBus.available() > 0 && n < sizeof(rx)) {
            rx[n++] = (uint8_t)gBus.read();
        }
        if (n >= sizeof(kTx) && memcmp(rx, kTx, sizeof(kTx)) == 0) {
            break;
        }
        delayMicroseconds(100);
    }
    const bool ok = n == sizeof(kTx) && memcmp(rx, kTx, sizeof(kTx)) == 0;
    char txHex[16];
    char rxHex[80];
    appendHex(txHex, sizeof(txHex), kTx, sizeof(kTx));
    appendHex(rxHex, sizeof(rxHex), rx, n);
    Serial.printf("@echo ok=%d n=%u us=%lu tx=", ok ? 1 : 0, static_cast<unsigned>(n),
                  static_cast<unsigned long>(micros() - listenStart));
    Serial.print(txHex);
    Serial.print(" rx=");
    Serial.println(rxHex);
    return ok;
}

bool smsPing(SmsReply* reply) {
    return transact(0x01, nullptr, 0, reply);
}

bool smsRead(uint8_t addr, uint8_t len, SmsReply* reply) {
    const uint8_t params[2] = {addr, len};
    if (!transact(0x02, params, 2, reply)) {
        return false;
    }
    // 短い応答を「読めた」にすると、隣のレジスタを誤って表示する。
    if (reply->len < len) {
        reply->ok = false;
        return false;
    }
    return true;
}

static bool smsWrite(uint8_t addr, const uint8_t* data, uint8_t dataLen, SmsReply* reply) {
    uint8_t params[16];
    if (dataLen > 14) {
        return false;
    }
    params[0] = addr;
    for (uint8_t i = 0; i < dataLen; ++i) {
        params[1 + i] = data[i];
    }
    return transact(0x03, params, (uint8_t)(dataLen + 1), reply);
}

bool smsWrite8(uint8_t addr, uint8_t value, SmsReply* reply) {
    return smsWrite(addr, &value, 1, reply);
}

bool smsWrite16(uint8_t addr, uint16_t valueLe, SmsReply* reply) {
    const uint8_t data[2] = {(uint8_t)(valueLe & 0xFF), (uint8_t)((valueLe >> 8) & 0xFF)};
    return smsWrite(addr, data, 2, reply);
}

uint16_t smsEncodeSigned15(int32_t value) {
    if (value < 0) {
        int32_t mag = -value;
        if (mag > 32767) {
            mag = 32767;
        }
        return (uint16_t)((uint16_t)mag | 0x8000u);
    }
    if (value > 32767) {
        value = 32767;
    }
    return (uint16_t)value;
}
