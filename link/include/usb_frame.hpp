#pragma once

/**
 * USB CDC の共通契約。ATOM（ver 14）と CoreS3（ver 15）が同じ番号を使う。
 *
 * 1 フレーム:
 *   0xAA 0x55 | type | len_lo | len_hi | payload[len] | crc16_le
 * crc は type から payload 末尾まで（CRC-16-CCITT、初期値 0xFFFF）。
 * len は LE uint16。
 *
 * テレメトリと HELLO の中身は版で違う。各ファームの usb_proto.hpp が持つ。
 * ここにある構造体は、どちらの版でも並びを変えない。
 * Python の正本は link/py/rt_usb_proto.py。
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>

static constexpr uint8_t kUsbMagic0 = 0xAA;
static constexpr uint8_t kUsbMagic1 = 0x55;
static constexpr uint16_t kUsbMaxPayload = 512;
static constexpr uint8_t kUsbFrameOverhead = 7;  // magic2 + type + len2 + crc2
static constexpr uint8_t kUsbMapChunkLen = 16;

/** HELLO.board。ver 14 は欄が無いので 0。 */
static constexpr uint8_t kUsbBoardUnknown = 0;
static constexpr uint8_t kUsbBoardAtomLite = 1;
static constexpr uint8_t kUsbBoardAtomS3r = 2;
static constexpr uint8_t kUsbBoardCoreS3 = 3;

// ---------------------------------------------------------------------------
// 種類（ボード→PC は 0x01..、PC→ボードは 0x80..）
// 新しい番号はここに足す。各ファームは未対応なら黙って捨てるか、理由コードを返す。
// ---------------------------------------------------------------------------
enum UsbMsg : uint8_t {
    kUsbTelemetry = 0x01,
    kUsbHello = 0x02,
    kUsbScanBegin = 0x03,
    kUsbScanNode = 0x04,
    kUsbScanEnd = 0x05,
    kUsbProf = 0x06,
    kUsbProfOk = 0x07,
    kUsbProfErr = 0x08,
    kUsbMapChunk = 0x09,
    kUsbMapOk = 0x0A,
    kUsbMapErr = 0x0B,
    kUsbMode = 0x0C,
    kUsbCalStart = 0x0D,
    kUsbCalProg = 0x0E,
    kUsbCalOk = 0x0F,
    kUsbCalErr = 0x10,
    kUsbEvtOc = 0x11,
    kUsbEvtBtn = 0x12,
    kUsbIdentifyOk = 0x13,
    kUsbProbe = 0x14,
    kUsbNvsBegin = 0x15,
    kUsbNvsEntry = 0x16,
    kUsbNvsEnd = 0x17,
    kUsbNvsData = 0x18,

    kUsbCmdPing = 0x80,
    kUsbCmdScan = 0x81,
    kUsbCmdIdentify = 0x82,
    kUsbCmdHold = 0x83,
    kUsbCmdCalAbort = 0x84,
    kUsbCmdCal = 0x85,
    kUsbCmdMode = 0x86,
    kUsbCmdOut = 0x87,
    kUsbCmdJoint = 0x88,
    kUsbCmdProbe = 0x89,
    kUsbCmdProfGet = 0x8A,
    kUsbCmdProfDefault = 0x8B,
    kUsbCmdProfPut = 0x8C,
    kUsbCmdMapGet = 0x8D,
    kUsbCmdMapChunk = 0x8E,
    kUsbCmdNvsList = 0x8F,
    kUsbCmdNvsErase = 0x90,
};

/** 失敗理由。GUI の REASON と番号を揃える。 */
enum UsbReason : uint8_t {
    kUsbReasonOk = 0,
    kUsbReasonSettle = 1,
    kUsbReasonAs5600 = 2,
    kUsbReasonFull = 3,
    kUsbReasonBadCh = 4,
    kUsbReasonServo = 5,
    kUsbReasonAbort = 6,
    kUsbReasonFirst = 7,
    kUsbReasonFit = 8,
    kUsbReasonMap = 9,
    kUsbReasonNvs = 10,
    kUsbReasonBusy = 11,
    kUsbReasonShort = 12,
    kUsbReasonBadArg = 13,
    kUsbReasonCount = 14,
    kUsbReasonBad = 15,
};

#pragma pack(push, 1)

struct UsbScanNode {
    uint8_t hub;
    int8_t ch;
    uint8_t addr;
    uint8_t kind;
    uint8_t mag;
    uint8_t agc;
};

struct UsbProfOk {
    uint8_t n;
    uint8_t is_default;
};

struct UsbMapChunkHdr {
    uint8_t ch;
    uint16_t total;
    uint16_t start;
    uint8_t n;
};

struct UsbMapPoint {
    float x;
    float y;
};

struct UsbMapOk {
    uint8_t ch;
    uint16_t count;
};

struct UsbMapErr {
    int8_t ch;
    uint16_t got;
    uint16_t expect;
    uint8_t reason;
};

/** ver 14 のモード通知。out_mask は 8 bit。ver 15 は 3 バイト（mode, lo, hi）。 */
struct UsbModeOut {
    uint8_t mode;
    uint8_t out_mask;
};

struct UsbCalStart {
    uint8_t ch;
};

struct UsbCalProg {
    uint8_t ch;
    uint8_t pct;
    float cmd;
};

struct UsbCalOk {
    uint8_t ch;
    uint16_t count;
    float rms;
    float max_abs;
};

struct UsbCalErr {
    int8_t ch;
    uint8_t reason;
};

struct UsbEvtOc {
    float amp;
};

struct UsbProbe {
    uint8_t found;  // 0 none, 2 as5600, 3 ina
    uint8_t hub;
    int8_t ch;
    uint8_t addr;
    float f0;
    float f1;
    float f2;
    uint8_t mag;
    uint8_t agc;
    uint16_t magnitude;
    uint8_t ok;
};

struct UsbCmdCal {
    uint8_t ch;
};

struct UsbCmdMode {
    uint8_t mode;
};

struct UsbCmdOut {
    uint8_t ch;  // 0xFF = 全軸
    uint8_t on;
};

struct UsbCmdJoint {
    uint8_t ch;
    float deg;
};

struct UsbCmdProbe {
    uint8_t hub_mode;  // 0=root（addr を使う）, 1=hub
    uint8_t hub_or_addr;
    int8_t ch;
};

struct UsbCmdMapGet {
    uint8_t ch;
};

/** NVS 1 キー。ns/key は NUL 終端。type は nvs_type_t。 */
struct UsbNvsEntry {
    char ns[16];
    char key[16];
    uint8_t type;
    uint16_t size;
};

struct UsbNvsEnd {
    uint8_t count;
    uint16_t bytes;
};

/** NVS 値の断片。hdr の直後に n バイト。 */
struct UsbNvsDataHdr {
    char ns[16];
    char key[16];
    uint16_t total;
    uint16_t start;
    uint8_t n;
};

static constexpr uint8_t kUsbNvsChunk = 192;

/** 消してよい名前空間だけ受ける（"cal" / "jprof"）。 */
struct UsbCmdNvsErase {
    char ns[16];
};

#pragma pack(pop)

static_assert(sizeof(UsbScanNode) == 6, "UsbScanNode layout");
static_assert(sizeof(UsbMapChunkHdr) == 6, "UsbMapChunkHdr layout");
static_assert(sizeof(UsbMapPoint) == 8, "UsbMapPoint layout");
static_assert(sizeof(UsbProbe) == 21, "UsbProbe layout");
static_assert(sizeof(UsbNvsEntry) == 35, "UsbNvsEntry layout");
static_assert(sizeof(UsbNvsEnd) == 3, "UsbNvsEnd layout");
static_assert(sizeof(UsbNvsDataHdr) == 37, "UsbNvsDataHdr layout");
static_assert(sizeof(UsbCmdJoint) == 5, "UsbCmdJoint layout");

// ---------------------------------------------------------------------------
// CRC-16-CCITT
// ---------------------------------------------------------------------------
inline uint16_t usbCrc16(const uint8_t* data, size_t n) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < n; ++i) {
        crc = static_cast<uint16_t>(crc ^ (static_cast<uint16_t>(data[i]) << 8));
        for (int b = 0; b < 8; ++b) {
            if (crc & 0x8000u) {
                crc = static_cast<uint16_t>((crc << 1) ^ 0x1021u);
            } else {
                crc = static_cast<uint16_t>(crc << 1);
            }
        }
    }
    return crc;
}

/** type+len16+payload を buf に組む。戻り値は総バイト数。失敗時 0。 */
inline size_t usbBuildFrame(uint8_t* buf, size_t cap, uint8_t type,
                            const void* payload, uint16_t len) {
    const size_t total = static_cast<size_t>(kUsbFrameOverhead) + static_cast<size_t>(len);
    if (cap < total || len > kUsbMaxPayload) {
        return 0;
    }
    buf[0] = kUsbMagic0;
    buf[1] = kUsbMagic1;
    buf[2] = type;
    buf[3] = static_cast<uint8_t>(len & 0xFFu);
    buf[4] = static_cast<uint8_t>(len >> 8);
    if (len > 0 && payload != nullptr) {
        memcpy(buf + 5, payload, len);
    }
    const uint16_t crc = usbCrc16(buf + 2, static_cast<size_t>(3) + len);
    buf[5 + len] = static_cast<uint8_t>(crc & 0xFFu);
    buf[6 + len] = static_cast<uint8_t>(crc >> 8);
    return total;
}
