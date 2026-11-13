/**
 * ATOM S3R + LTC1480 から、SM105BL との RS485 を見る。
 *
 * USB は行テキスト。RS485 のバイト列は @bus / @echo に載せる。
 * 接続しただけでは軸は動かない。トルクは arm だけが入れる。
 * arm は現在位置を目標にしてから保持する。目標 0 のまま出すと、そこへ回る。
 *
 * PC からは 1 行 1 コマンド。
 *   hello / echo / ping / info / scan / fb / id N
 *   arm LIMIT SPEED ACC / move COUNTS / torque 0
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

// SRAM。40 から 31 バイトで、トルクと位置と電流が 1 回で読める。
static constexpr uint8_t kRegTorque = 40;
static constexpr uint8_t kRegAcc = 41;
static constexpr uint8_t kRegGoal = 42;
static constexpr uint8_t kRegSpeed = 46;
static constexpr uint8_t kRegTorqueLimit = 48;
static constexpr uint8_t kRegPresent = 56;
static constexpr uint8_t kRegBlock = 40;
static constexpr uint8_t kRegBlockLen = 31;
static constexpr uint8_t kTorqueOff = 0;

// arm が成功したあとのみ move を通す。切断と ID 変更で戻す。
static bool gOutputOn = false;

static uint16_t u16le(const uint8_t* p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

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

// 速度 0 は位相のビット3次第で最高速になる。試験では拒否する。
static bool motionArgsOk(const char* cmd, int limit, int speed, int acc) {
    if (!rangeOk(limit, 0, 1000) || !rangeOk(speed, 1, 32767) || !rangeOk(acc, 0, 254)) {
        printErr(cmd, "bad_arg");
        return false;
    }
    return true;
}

static bool stageMotion(const char* cmd, int limit, int speed, int acc) {
    SmsReply reply;
    if (!smsWrite16(kRegTorqueLimit, (uint16_t)limit, &reply)) {
        printErr(cmd, "write_limit");
        return false;
    }
    if (!smsWrite8(kRegAcc, (uint8_t)acc, &reply)) {
        printErr(cmd, "write_acc");
        return false;
    }
    if (!smsWrite16(kRegSpeed, (uint16_t)speed, &reply)) {
        printErr(cmd, "write_speed");
        return false;
    }
    return true;
}

static void cmdArm(int limit, int speed, int acc) {
    if (!motionArgsOk("arm", limit, speed, acc)) {
        return;
    }
    // 速度と制限を先に書く。目標位置の書き込みが、トルクを自分でオンにする。
    if (!stageMotion("arm", limit, speed, acc)) {
        return;
    }
    SmsReply pos;
    if (!smsRead(kRegPresent, 2, &pos)) {
        printErr("arm", "read_pos");
        return;
    }
    const uint16_t raw = u16le(pos.data);
    SmsReply wrote;
    if (!smsWrite16(kRegGoal, raw, &wrote)) {
        // 届いたか分からない。出力が残らないよう、切る方は一度試みる。
        SmsReply off;
        smsWrite8(kRegTorque, kTorqueOff, &off);
        gOutputOn = false;
        printErr("arm", "write_goal");
        return;
    }
    gOutputOn = true;
    Serial.printf("@ok cmd=arm value=1 pos=%u st=%u\n", raw, wrote.status);
}

static void cmdTorqueOff() {
    SmsReply reply;
    if (!smsWrite8(kRegTorque, kTorqueOff, &reply)) {
        printErr("torque", "timeout");
        return;
    }
    gOutputOn = false;
    Serial.printf("@ok cmd=torque value=0 st=%u\n", reply.status);
}

static void cmdMove(int counts) {
    if (!gOutputOn) {
        printErr("move", "torque_off");
        return;
    }
    if (!rangeOk(counts, -32767, 32767)) {
        printErr("move", "bad_arg");
        return;
    }
    SmsReply reply;
    const uint16_t raw = smsEncodeSigned15(counts);
    if (!smsWrite16(kRegGoal, raw, &reply)) {
        printErr("move", "timeout");
        return;
    }
    Serial.printf("@ok cmd=move pos=%d raw=%u st=%u\n", counts, raw, reply.status);
}

static void cmdFb() {
    SmsReply reply;
    if (!smsRead(kRegBlock, kRegBlockLen, &reply)) {
        Serial.println("@fb ok=0");
        return;
    }
    const uint8_t* d = reply.data;
    // 40 からの並び。位置は 56、目標は 67、電流は 69。
    Serial.printf("@fb ok=1 torque=%u pos=%u spd=%u load=%u volt=%u temp=%u status=%u moving=%u goal=%u curr=%u\n",
                  d[0],
                  u16le(d + 16),
                  u16le(d + 18),
                  u16le(d + 20),
                  d[22],
                  d[23],
                  d[25],
                  d[26],
                  u16le(d + 27),
                  u16le(d + 29));
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
    int b = 0;
    int c = 0;
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
    } else if (strcmp(line, "fb") == 0) {
        cmdFb();
    } else if (strcmp(line, "torque 0") == 0 || strcmp(line, "torque0") == 0) {
        cmdTorqueOff();
    } else if (sscanf(line, "arm %d %d %d", &a, &b, &c) == 3) {
        cmdArm(a, b, c);
    } else if (sscanf(line, "move %d", &a) == 1) {
        cmdMove(a);
    } else if (sscanf(line, "id %d", &a) == 1) {
        // 254 は 1 台だけの同報。EEPROM の ID は変えない。
        if (!rangeOk(a, 0, 254)) {
            printErr("id", "bad_arg");
            return;
        }
        // 同じ ID の再送で、保持中のトルクまで落とさない。
        if ((uint8_t)a != smsId()) {
            gOutputOn = false;
        }
        smsSetId((uint8_t)a);
        Serial.printf("@ok cmd=id value=%d\n", a);
    } else if (strncmp(line, "torque", 6) == 0) {
        // 1 は arm の仕事。128 は中点校正で、軸のゼロがずれる。
        printErr("torque", "use_arm_or_off");
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
