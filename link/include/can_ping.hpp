#pragma once

/**
 * 机上の CAN 疎通試験。脚のセンサやサーボ指令ではない。
 *
 * 500 kbps、標準 11 bit ID。データは 8 バイト。
 *   0..3  送信カウンタ。uint32 リトルエンディアン。1 秒に 1 増える
 *   4     送信元。1 = CoreS3、2 = ATOM S3R
 *   5     0xA5。この試験の印
 *   6..7  0
 *
 * CoreS3 は 0x100、ATOM S3R は 0x101 を送る。
 * 相手の ACK が無いと送信は失敗する。1 台だけでは成功しない。
 */

#include <Arduino.h>
#include <string.h>

#include "driver/twai.h"

static constexpr uint32_t kCanPingIdCore = 0x100;
static constexpr uint32_t kCanPingIdAtom = 0x101;
static constexpr uint8_t kCanPingNodeCore = 1;
static constexpr uint8_t kCanPingNodeAtom = 2;
static constexpr uint8_t kCanPingMark = 0xA5;
static constexpr uint32_t kCanPingPeriodMs = 1000;

static const char* canPingNodeName(uint8_t node) {
    if (node == kCanPingNodeCore) {
        return "core";
    }
    if (node == kCanPingNodeAtom) {
        return "atom";
    }
    return "?";
}

static const char* canPingStateName(twai_state_t state) {
    switch (state) {
    case TWAI_STATE_STOPPED:
        return "stopped";
    case TWAI_STATE_RUNNING:
        return "running";
    case TWAI_STATE_BUS_OFF:
        return "bus-off";
    case TWAI_STATE_RECOVERING:
        return "recovering";
    default:
        return "unknown";
    }
}

/**
 * TWAI を 500 kbps で始める。tx はトランシーバの TXD へ出すピン。
 * 失敗したら false。呼び出し側が理由を出す。
 */
static bool canPingStart(gpio_num_t tx, gpio_num_t rx) {
    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(tx, rx, TWAI_MODE_NORMAL);
    const twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
    const twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    if (twai_driver_install(&general, &timing, &filter) != ESP_OK) {
        return false;
    }
    return twai_start() == ESP_OK;
}

/**
 * bus-off から戻す。線を外したあとは bus-off になり、
 * 128 回の recessive を見てから STOPPED へ落ちる。そこで start し直す。
 */
static void canPingRecover() {
    twai_status_info_t status{};
    if (twai_get_status_info(&status) != ESP_OK) {
        return;
    }
    if (status.state == TWAI_STATE_BUS_OFF) {
        twai_initiate_recovery();
        return;
    }
    if (status.state == TWAI_STATE_STOPPED) {
        twai_start();
    }
}

/** 1 フレームを送る。ACK が来なければ false。キューに残った分は捨てる。 */
static bool canPingSend(uint32_t id, uint8_t node, uint32_t seq) {
    twai_message_t msg{};
    msg.identifier = id;
    msg.data_length_code = 8;
    memcpy(msg.data, &seq, sizeof(seq));
    msg.data[4] = node;
    msg.data[5] = kCanPingMark;
    const esp_err_t err = twai_transmit(&msg, pdMS_TO_TICKS(50));
    if (err != ESP_OK) {
        twai_clear_transmit_queue();
        return false;
    }
    return true;
}

/** 届いているフレームを全部表示する。1 枚でも読めたら true。 */
static bool canPingDrain() {
    bool any = false;
    twai_message_t msg{};
    while (twai_receive(&msg, 0) == ESP_OK) {
        any = true;
        if (msg.data_length_code < 6 || msg.data[5] != kCanPingMark) {
            Serial.printf("RX id=0x%03X dlc=%u raw\n",
                          static_cast<unsigned>(msg.identifier),
                          msg.data_length_code);
            continue;
        }
        uint32_t seq = 0;
        memcpy(&seq, msg.data, sizeof(seq));
        Serial.printf("RX id=0x%03X seq=%lu node=%s\n",
                      static_cast<unsigned>(msg.identifier),
                      static_cast<unsigned long>(seq),
                      canPingNodeName(msg.data[4]));
    }
    return any;
}

static void canPingPrintBus() {
    twai_status_info_t status{};
    if (twai_get_status_info(&status) != ESP_OK) {
        Serial.println("bus status unread");
        return;
    }
    Serial.printf("bus=%s tx_err=%lu rx_err=%lu\n",
                  canPingStateName(status.state),
                  static_cast<unsigned long>(status.tx_error_counter),
                  static_cast<unsigned long>(status.rx_error_counter));
}
