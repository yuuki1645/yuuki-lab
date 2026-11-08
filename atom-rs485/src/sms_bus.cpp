#include "sms_bus.hpp"

#include <stdio.h>
#include <string.h>

// UART2。USB CDC が Serial を使うので、RS485 はこちら。
static HardwareSerial gBus(2);
static uint8_t gId = kDefaultServoId;
static char gTxHex[80];
static bool gSelfOk = false;

static uint8_t checksumOf(uint8_t id, uint8_t length, uint8_t inst, const uint8_t* params, uint8_t nparams) {
    // ~(ID + Length + Instruction + パラメータ) の下位 8bit。チェックサム自身は足さない。
    unsigned sum = (unsigned)id + length + inst;
    for (uint8_t i = 0; i < nparams; ++i) {
        sum += params[i];
    }
    return (uint8_t)(~sum);
}

static size_t buildPacket(uint8_t id, uint8_t inst, const uint8_t* params, uint8_t nparams, uint8_t* out) {
    // Length は Instruction、パラメータ、チェックサムのバイト数。
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

static void rememberTx(const uint8_t* packet, size_t len) {
    size_t used = 0;
    gTxHex[0] = '\0';
    for (size_t i = 0; i < len && used + 2 < sizeof(gTxHex); ++i) {
        used += (size_t)snprintf(gTxHex + used, sizeof(gTxHex) - used, "%02x", packet[i]);
    }
}

const char* smsLastTxHex() {
    return gTxHex;
}

// 受信バッファからステータスパケットを 1 つ取り出す。足りなければ false。
// エコー（送信そのもの）は 1 回だけ捨てる。FF FF がデータ中に出ても、
// チェックサムが合う位置だけをパケットとして扱う。
static bool pullPacket(uint8_t* buf, size_t* n, const uint8_t* echo, size_t echoLen, bool* echoSkipped, SmsReply* out) {
    size_t i = 0;
    while (i + 4 <= *n) {
        if (buf[i] != 0xFF || buf[i + 1] != 0xFF) {
            ++i;
            continue;
        }
        const uint8_t length = buf[i + 3];
        // 読む最大は 40 バイト。Length = status + data + checksum なので 48 を超えたらゴミ。
        if (length < 2 || length > 48) {
            ++i;
            continue;
        }
        const size_t total = (size_t)length + 4;
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

static bool transact(uint8_t inst, const uint8_t* params, uint8_t nparams, SmsReply* reply) {
    uint8_t tx[40];
    const size_t txLen = buildPacket(gId, inst, params, nparams, tx);
    rememberTx(tx, txLen);
    reply->ok = false;
    reply->status = 0;
    reply->len = 0;

    // 前の応答の残りと、バスが静まるのを待ってから送る。
    delayMicroseconds(150);
    while (gBus.available() > 0) {
        gBus.read();
    }
    gBus.write(tx, txLen);
    gBus.flush();

    uint8_t buf[96];
    size_t n = 0;
    bool echoSkipped = false;
    const uint32_t start = millis();
    while ((uint32_t)(millis() - start) < kReplyTimeoutMs) {
        while (gBus.available() > 0 && n < sizeof(buf)) {
            buf[n++] = (uint8_t)gBus.read();
        }
        if (pullPacket(buf, &n, tx, txLen, &echoSkipped, reply)) {
            return true;
        }
        if (n >= sizeof(buf)) {
            memmove(buf, buf + 32, n - 32);
            n -= 32;
        }
        delayMicroseconds(200);
    }
    return false;
}

static void selfTest() {
    // ID 1 の PING。sum = 1+2+1 = 4、チェックサムは 0xFB。
    uint8_t ping[8];
    const size_t pingLen = buildPacket(1, 0x01, nullptr, 0, ping);
    const bool pingOk = pingLen == 6 && ping[0] == 0xFF && ping[1] == 0xFF && ping[2] == 0x01 &&
                        ping[3] == 0x02 && ping[4] == 0x01 && ping[5] == 0xFB;
    // ID 1 でアドレス 40 から 31 バイト読む。チェックサムは 0xB1。
    const uint8_t readParams[2] = {kRegBlock, kRegBlockLen};
    uint8_t readPkt[8];
    const size_t readLen = buildPacket(1, 0x02, readParams, 2, readPkt);
    const bool readOk = readLen == 8 && readPkt[5] == 0x28 && readPkt[6] == 0x1F && readPkt[7] == 0xB1;
    gSelfOk = pingOk && readOk;
    if (!gSelfOk) {
        Serial.println("@err cmd=self msg=checksum");
    }
}

bool smsSelfOk() {
    return gSelfOk;
}

void smsBegin() {
    gBus.setRxBufferSize(256);
    gBus.begin(kRs485Baud, SERIAL_8N1, kRs485RxPin, kRs485TxPin);
    selfTest();
}

void smsSetId(uint8_t id) {
    gId = id;
}

uint8_t smsId() {
    return gId;
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

bool smsPing(SmsReply* reply) {
    return transact(0x01, nullptr, 0, reply);
}

bool smsRead(uint8_t addr, uint8_t len, SmsReply* reply) {
    const uint8_t params[2] = {addr, len};
    if (!transact(0x02, params, 2, reply)) {
        return false;
    }
    // 短い応答を「読めた」にすると、GUI が隣のレジスタを誤って表示する。
    if (reply->len < len) {
        reply->ok = false;
        return false;
    }
    return true;
}

bool smsWrite(uint8_t addr, const uint8_t* data, uint8_t dataLen, SmsReply* reply) {
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
