/**
 * ATOM S3R + LTC1480 から、SM105BL との RS485 を見る。
 *
 * USB は行テキスト。RS485 のバイト列は @bus / @echo に載せる。
 * 角度の計算も、トルクを入れる WRITE もしない。
 * 接続しただけでは軸は動かない。
 *
 * PC からは 1 行 1 コマンド。
 *   hello / echo / ping / info / scan / id N
 * scan は UART のボーレートを変えて PING する。サーボの EEPROM は書かない。
 * 応答したレートが見つかったら、そのレートのまま残す。
 */

#include <Arduino.h>

#include "sms_bus.hpp"

// アドレス 6 に入っている値の意味。scan が試す順番とは別。
// 0 が 1Mbps。机上の初期 UART は 115200（この表の 4）。
static const uint32_t kServoBauds[] = {1000000, 500000, 250000, 128000, 115200, 76800, 57600, 38400};

// このリポジトリの机上は 115200。出荷テーブルの先頭は 1Mbps なので、その次に試す。
static const uint32_t kScanBauds[] = {115200, 1000000, 500000, 250000, 128000, 76800, 57600, 38400};

static void printErr(const char* cmd, const char* msg) {
    Serial.print("@err cmd=");
    Serial.print(cmd);
    Serial.print(" msg=");
    Serial.println(msg);
}

static void printHello() {
    // self=0 はパケット組み立ての自己検査に落ちたとき。サーボにはまだ何も書いていない。
    Serial.printf("@hello name=atom-test-rs485 rx=%d tx=%d de=%d baud=%lu id=%u self=%d\n",
                  kRs485RxPin,
                  kRs485TxPin,
                  kDePin,
                  static_cast<unsigned long>(smsBaud()),
                  smsId(),
                  smsSelfOk() ? 1 : 0);
}

static bool rangeOk(int value, int lo, int hi) {
    return value >= lo && value <= hi;
}

static void cmdPing() {
    SmsReply reply;
    if (!smsPing(&reply)) {
        printErr("ping", "timeout");
        return;
    }
    Serial.printf("@ok cmd=ping id=%u st=%u\n", smsId(), reply.status);
}

static void cmdInfo() {
    SmsReply mem;
    // アドレス 0 から 40 バイト。ID は 5、ボーレート番号は 6、ファームは 0 と 1。
    if (!smsRead(0, 40, &mem)) {
        printErr("info", mem.len > 0 ? "short" : "timeout");
        return;
    }
    const uint8_t* d = mem.data;
    const uint32_t bps = d[6] < (sizeof(kServoBauds) / sizeof(kServoBauds[0])) ? kServoBauds[d[6]] : 0;
    Serial.printf("@info ok=1 id=%u baud=%u baud_bps=%lu fw=%u.%u\n", d[5], d[6], static_cast<unsigned long>(bps), d[0],
                  d[1]);
}

static void cmdScan() {
    uint32_t keep = kRs485Baud;
    bool found = false;
    for (uint32_t baud : kScanBauds) {
        smsSetBaud(baud);
        // レートを変えた直後の 1 バイト目が崩れないように、バスを一度空ける。
        delay(2);
        SmsReply reply;
        if (smsPing(&reply)) {
            keep = baud;
            found = true;
            break;
        }
    }
    if (!found) {
        smsSetBaud(kRs485Baud);
        keep = kRs485Baud;
    }
    Serial.printf("@ok cmd=scan baud=%lu found=%d\n", static_cast<unsigned long>(keep), found ? 1 : 0);
}

static void handleLine(char* line) {
    int a = 0;
    if (strcmp(line, "hello") == 0) {
        printHello();
    } else if (strcmp(line, "echo") == 0) {
        smsProbeEcho();
    } else if (strcmp(line, "ping") == 0) {
        cmdPing();
    } else if (strcmp(line, "info") == 0) {
        cmdInfo();
    } else if (strcmp(line, "scan") == 0) {
        cmdScan();
    } else if (sscanf(line, "id %d", &a) == 1) {
        // 254 は 1 台だけの同報。EEPROM の ID は変えない。
        if (!rangeOk(a, 0, 254)) {
            printErr("id", "bad_arg");
            return;
        }
        smsSetId((uint8_t)a);
        Serial.printf("@ok cmd=id value=%d\n", a);
    } else {
        printErr("?", "bad_cmd");
    }
}

static void pollUsb() {
    static char line[96];
    static size_t len = 0;
    while (Serial.available() > 0) {
        const char c = (char)Serial.read();
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            line[len] = '\0';
            if (len > 0) {
                handleLine(line);
            }
            len = 0;
            continue;
        }
        if (len < sizeof(line) - 1) {
            line[len++] = c;
        }
    }
}

void setup() {
    // ホストがいないときに flush すると、USB CDC がそこで止まる。flush しない。
    // DE は UART より先に Low。起動のあいだバスを占有しない。
    pinMode(kDePin, OUTPUT);
    digitalWrite(kDePin, LOW);
    Serial.setTxBufferSize(2048);
    Serial.begin(115200);
    Serial.setTimeout(10);
    smsBegin();
    printHello();
    smsProbeEcho();
}

void loop() {
    pollUsb();
}
