#pragma once
/**
 * lora_packet.h — LoRa paket formati (Node ↔ Gateway)
 *
 * SX1278 (Ra-02) ESP32 ga ulanish:
 *   Ra-02 MOSI → ESP32 GPIO23
 *   Ra-02 MISO → ESP32 GPIO19
 *   Ra-02 SCK  → ESP32 GPIO18
 *   Ra-02 NSS  → ESP32 GPIO5
 *   Ra-02 RST  → ESP32 GPIO14
 *   Ra-02 DIO0 → ESP32 GPIO2
 *   Ra-02 3.3V → ESP32 3.3V
 *   Ra-02 GND  → ESP32 GND
 */

#include <Arduino.h>
#include <SPI.h>
#include <LoRa.h>

// ─── SX1278 SPI pinlari ───────────────────────────────────────────────────────
#define LORA_PIN_CS   15
#define LORA_PIN_RST  14
#define LORA_PIN_IRQ  2

// ─── RF sozlamalari (433 MHz, O'zbekiston ISM band) ───────────────────────────
#define LORA_FREQ     433E6   // 433 MHz
#define LORA_SF       9       // Spreading Factor 9: ~1-3km shahar, ~5km ochiq
#define LORA_BW       125E3   // Bandwidth 125 kHz
#define LORA_CR       5       // Coding Rate 4/5
#define LORA_TX_PWR   2       // TX power dBm (test: 2dBm, antena yoq; production: 17)
#define LORA_SYNC     0xAB    // Sync word (tarmoq ajratuvchi, 0x12 = LoRaWAN)

// ─── Paket turlari ────────────────────────────────────────────────────────────
#define PKT_UPLINK   0x01   // Node → Gateway: sensor ma'lumotlari
#define PKT_DOWNLINK 0x02   // Gateway → Node: relay buyruq

// ─── Uplink paket: Node → Gateway ────────────────────────────────────────────
// Qiymatlar fixed-point (float overhead va NaN muammosi yo'q)
// Jami: 46 bayt — LoRa uchun ideal hajm
struct __attribute__((packed)) LoRaUplink {
    uint8_t  pkt_type;          // PKT_UPLINK = 0x01
    uint8_t  mac[6];            // Node WiFi MAC adresi (qurilma ID)
    uint8_t  flags;             // bit0=te73, bit1=test_mode
    char     meter_serial[13];  // Hisoblagich seriyasi (12 char + '\0')
    int16_t  v_l1;              // Kuchlanish L1: V×100  (21532 = 215.32 V)
    int16_t  v_l2;              // Kuchlanish L2
    int16_t  v_l3;              // Kuchlanish L3
    int16_t  i_l1;              // Tok L1: mA  (10500 = 10.5 A)
    int16_t  i_l2;
    int16_t  i_l3;
    int32_t  power_w;           // Aktiv quvvat: W
    int16_t  freq_chz;          // Chastota: Hz×100  (5000 = 50.00 Hz)
    int32_t  energy_wh;         // Energiya: Wh  (319830 = 319.830 kWh)
    int8_t   pf_pct;            // Power factor: ×100  (98 = 0.98)
    uint16_t crc;               // CRC16-CCITT (oxirgi 2 bayt, MAC dan hisob)
};

// ─── Downlink paket: Gateway → Node ──────────────────────────────────────────
// Jami: 10 bayt
struct __attribute__((packed)) LoRaDownlink {
    uint8_t  pkt_type;          // PKT_DOWNLINK = 0x02
    uint8_t  mac[6];            // Manzil node MAC
    uint8_t  relay_cmd;         // 0=yo'q, 1=relay_off(uzish), 2=relay_on(ulash)
    uint16_t crc;
};

// ─── CRC16-CCITT ─────────────────────────────────────────────────────────────
static uint16_t lora_crc16(const uint8_t* d, size_t n) {
    uint16_t c = 0xFFFF;
    for (size_t i = 0; i < n; i++) {
        c ^= (uint16_t)d[i] << 8;
        for (int j = 0; j < 8; j++)
            c = (c & 0x8000) ? (c << 1) ^ 0x1021 : (c << 1);
    }
    return c;
}

static void lora_crc_set(uint8_t* buf, size_t total) {
    uint16_t c = lora_crc16(buf, total - 2);
    buf[total - 2] = c & 0xFF;
    buf[total - 1] = c >> 8;
}

static bool lora_crc_ok(const uint8_t* buf, size_t total) {
    if (total < 2) return false;
    uint16_t rx   = buf[total-2] | ((uint16_t)buf[total-1] << 8);
    uint16_t calc = lora_crc16(buf, total - 2);
    return rx == calc;
}

// ─── LoRa init (ham node, ham gateway) ───────────────────────────────────────
static bool lora_init() {
    LoRa.setPins(LORA_PIN_CS, LORA_PIN_RST, LORA_PIN_IRQ);
    if (!LoRa.begin(LORA_FREQ)) return false;
    LoRa.setSpreadingFactor(LORA_SF);
    LoRa.setSignalBandwidth(LORA_BW);
    LoRa.setCodingRate4(LORA_CR);
    LoRa.setTxPower(LORA_TX_PWR);
    LoRa.setSyncWord(LORA_SYNC);
    return true;
}
