#pragma once

/**
 * マスター ATOMS3 Lite ↔ PC の USB CDC バイナリフレーム。
 *
 * 1 フレーム:
 *   0xAA 0x55 | type | len | payload[len] | crc16_le
 * crc は type から payload 末尾まで（CRC-16-CCITT、初期値 0xFFFF）。
 *
 * 欄の並びは tools/usb_proto.py と揃えること。
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>

static constexpr uint8_t kUsbMagic0 = 0xAA;
static constexpr uint8_t kUsbMagic1 = 0x55;
static constexpr uint8_t kUsbMaxPayload = 64;
static constexpr uint8_t kUsbFwVer = 1;
static constexpr uint8_t kUsbCorners = 4;

enum UsbMsg : uint8_t {
    kUsbTelemetry = 0x01,
    kUsbHello = 0x02,
    kUsbIdentifyOk = 0x13,
    kUsbEvtBtn = 0x12,

    kUsbCmdPing = 0x80,
    kUsbCmdIdentify = 0x82,
};

#pragma pack(push, 1)

/** 20 Hz 前後の足裏サンプル。mv はミリボルト（未応答時は 0）。 */
struct UsbTelemetry {
    uint32_t seq;
    uint32_t t_period_us;
    uint32_t t_loop_us;
    uint32_t t_i2c_us;
    uint8_t slave_ok;
    uint8_t overrun;
    uint16_t i2c_err;
    uint16_t mv[kUsbCorners];  // TL, TR, BR, BL
};

struct UsbHello {
    uint8_t ver;
    uint8_t corners;
    uint8_t slave_ok;
    uint8_t reserved;
};

#pragma pack(pop)

static_assert(sizeof(UsbTelemetry) == 28, "UsbTelemetry layout");
static_assert(sizeof(UsbHello) == 4, "UsbHello layout");
static_assert(sizeof(UsbTelemetry) <= kUsbMaxPayload, "telemetry too big");

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

/** type+len+payload を buf に組む。戻り値は総バイト数。失敗時 0。 */
inline size_t usbBuildFrame(uint8_t* buf, size_t cap, uint8_t type,
                            const void* payload, uint8_t len) {
    const size_t total = static_cast<size_t>(6) + static_cast<size_t>(len);
    if (cap < total || len > kUsbMaxPayload) {
        return 0;
    }
    buf[0] = kUsbMagic0;
    buf[1] = kUsbMagic1;
    buf[2] = type;
    buf[3] = len;
    if (len > 0 && payload != nullptr) {
        memcpy(buf + 4, payload, len);
    }
    const uint16_t crc = usbCrc16(buf + 2, static_cast<size_t>(2) + len);
    buf[4 + len] = static_cast<uint8_t>(crc & 0xFFu);
    buf[5 + len] = static_cast<uint8_t>(crc >> 8);
    return total;
}
