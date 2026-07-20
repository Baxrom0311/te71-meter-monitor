#pragma once
/**
 * lora_node.h — LoRa Node firmware (WiFi YO'Q)
 *
 * Node (hisoblagich yonida, WiFi dan uzoqda):
 *   1. RS-485 → DLMS/COSEM orqali TE71/TE73 o'qish
 *   2. LoRa TX → Gateway ga sensor ma'lumot yuborish (har 30s)
 *   3. LoRa RX → Gateway dan relay buyruq qabul (TX dan so'ng 3s oyna)
 *   4. Relay → DLMS ACTION orqali bajarish
 *
 * WiFi ISHLATILMAYDI — meter RS-485 + LoRa yetarli.
 *
 * Build: pio run -e electricity_lora_node
 */

#include <Arduino.h>
#include <esp_system.h>

// ─── Minimal config (WiFi/HTTP yo'q, faqat test_mode kerak) ──────────────────
struct AppConfig { bool test_mode; };
static AppConfig g_cfg = { false };

// ─── Debug log (common.h yo'q, o'zimiz aniqlaymiz) ───────────────────────────
#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
  #define LOG_PRINT(x)       Serial.print(x)
  #define LOG_PRINTLN(x)     Serial.println(x)
  #define LOG_PRINTF(x, ...) Serial.printf(x, ##__VA_ARGS__)
#else
  #define LOG_PRINT(x)
  #define LOG_PRINTLN(x)
  #define LOG_PRINTF(x, ...)
#endif

// Electricity sensor (RS-485 DLMS) — g_cfg va LOG aniqlanganidan keyin
#include "sensors/electricity.h"
// LoRa paket formati
#include "lora_packet.h"

// ─── Konstantalar ─────────────────────────────────────────────────────────────
#define NODE_READ_MS        30000UL   // O'qish intervali: 30s
#define NODE_DL_WAIT_MS      3000     // Downlink kutish oynasi TX dan keyin
#define NODE_METER_MAX_MS  300000UL   // Maksimal retry interval: 5 daqiqa

// ─── Node holati ──────────────────────────────────────────────────────────────
static uint8_t  node_mac[6];
static char     node_id[20];
static int      node_pending_relay  = 0;
static int      node_fail_count     = 0;
static unsigned long node_retry_ms  = NODE_READ_MS;
static unsigned long node_last_ms   = 0;

// ─── LoRa TX: uplink yuborish ────────────────────────────────────────────────
static bool node_send_uplink(const SensorData& d) {
    LoRaUplink pkt;
    memset(&pkt, 0, sizeof(pkt));

    pkt.pkt_type = PKT_UPLINK;
    memcpy(pkt.mac, node_mac, 6);
    pkt.flags = 0;
    if (strcmp(d.sensor_type, "te73") == 0) pkt.flags |= 0x01;

    strncpy(pkt.meter_serial, d.meter_serial, 12);
    pkt.meter_serial[12] = '\0';

    // Fixed-point kodlash (NaN → 0, backend 0 ni skip qiladi)
    if (!isnan(d.voltage_l1)) pkt.v_l1      = (int16_t)(d.voltage_l1 * 100.0f);
    if (!isnan(d.voltage_l2)) pkt.v_l2      = (int16_t)(d.voltage_l2 * 100.0f);
    if (!isnan(d.voltage_l3)) pkt.v_l3      = (int16_t)(d.voltage_l3 * 100.0f);
    if (!isnan(d.current_l1)) pkt.i_l1      = (int16_t)(d.current_l1 * 1000.0f);
    if (!isnan(d.current_l2)) pkt.i_l2      = (int16_t)(d.current_l2 * 1000.0f);
    if (!isnan(d.current_l3)) pkt.i_l3      = (int16_t)(d.current_l3 * 1000.0f);
    if (!isnan(d.power_w))    pkt.power_w   = (int32_t)d.power_w;
    if (!isnan(d.frequency))  pkt.freq_chz  = (int16_t)(d.frequency * 100.0f);
    if (!isnan(d.energy_kwh)) pkt.energy_wh = (int32_t)(d.energy_kwh * 1000.0f);
    if (!isnan(d.pf))         pkt.pf_pct    = (int8_t)(d.pf * 100.0f);

    lora_crc_set((uint8_t*)&pkt, sizeof(pkt));

    LOG_PRINTF("LoRa TX → [%s] V=%.1fV P=%dW E=%.3fkWh (%d bayt)\n",
               pkt.meter_serial,
               pkt.v_l1 / 100.0f,
               (int)pkt.power_w,
               pkt.energy_wh / 1000.0f,
               (int)sizeof(pkt));

    LoRa.beginPacket();
    LoRa.write((uint8_t*)&pkt, sizeof(pkt));
    return LoRa.endPacket();  // true = muvaffaqiyatli
}

// ─── LoRa RX: downlink kutish (relay buyruq) ─────────────────────────────────
static void node_wait_downlink() {
    uint32_t t = millis();
    while (millis() - t < NODE_DL_WAIT_MS) {
        int sz = LoRa.parsePacket();
        if (sz == (int)sizeof(LoRaDownlink)) {
            LoRaDownlink dl;
            LoRa.readBytes((uint8_t*)&dl, sizeof(dl));

            if (dl.pkt_type != PKT_DOWNLINK)              { continue; }
            if (memcmp(dl.mac, node_mac, 6) != 0)         { continue; }  // boshqa node
            if (!lora_crc_ok((uint8_t*)&dl, sizeof(dl)))  {
                LOG_PRINTLN("LoRa RX: CRC xato — o'tkazildi");
                continue;
            }
            if (dl.relay_cmd > 0) {
                node_pending_relay = dl.relay_cmd;
                LOG_PRINTF("LoRa RX: relay_cmd=%d (%s)\n",
                           dl.relay_cmd, dl.relay_cmd == 2 ? "ON" : "OFF");
            }
        }
        delay(10);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Setup
// ═══════════════════════════════════════════════════════════════════════════════
void setup() {
#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
    Serial.begin(115200);
    delay(200);
#endif

    esp_read_mac(node_mac, ESP_MAC_WIFI_STA);
    snprintf(node_id, sizeof(node_id), "%02X%02X%02X%02X%02X%02X",
             node_mac[0], node_mac[1], node_mac[2],
             node_mac[3], node_mac[4], node_mac[5]);

    LOG_PRINTLN();
    LOG_PRINTLN("╔══════════════════════════════════════════╗");
    LOG_PRINTLN("║  Meter Monitor v" FW_VERSION " — LoRa NODE      ║");
    LOG_PRINTLN("║  WiFi YO'Q | RS-485 + LoRa 433MHz       ║");
    LOG_PRINTLN("╚══════════════════════════════════════════╝");
    LOG_PRINTF("Node ID: %s\n", node_id);

    // LoRa init
    LOG_PRINT("LoRa SX1278 init...");
    if (!lora_init()) {
        LOG_PRINTLN(" XATO! Modul topilmadi.");
        LOG_PRINTLN("  Ulanishni tekshiring: CS=5 RST=14 DIO0=2");
        while (true) delay(5000);
    }
    LOG_PRINTF(" OK (433MHz, SF%d, BW%.0fkHz, PWR=%ddBm)\n",
               LORA_SF, LORA_BW / 1000.0, LORA_TX_PWR);

    // Meter (RS-485 DLMS) init
    sensor_init();
    LOG_PRINT("Meter ulanmoqda:");
    bool found = false;
    for (int i = 1; i <= 3 && !found; i++) {
        LOG_PRINTF(" %d/3...", i);
        if (sensor_connect()) {
            dlms_get_string(1, OBIS_SERIAL, 2,
                            g_sensor_meta.meter_serial,
                            sizeof(g_sensor_meta.meter_serial));
            sensor_detect_type();
            LOG_PRINTF(" OK [%s / %s]\n",
                       g_sensor_meta.meter_serial,
                       g_sensor_meta.sensor_type);
            found = true;
        } else {
            delay(500);
        }
    }
    if (!found) {
        LOG_PRINTLN(" XATO — meter topilmadi, loop da qayta urinadi");
    }

    LOG_PRINTLN();
    LOG_PRINTLN("┌──────────────────────────────────────────┐");
    LOG_PRINTF( "│  Node ID    : %-26s│\n", node_id);
    LOG_PRINTF( "│  Hisoblagich: %-26s│\n",
        g_sensor_meta.meter_serial[0] ? g_sensor_meta.meter_serial : "topilmadi");
    LOG_PRINTF( "│  Tur        : %-26s│\n",
        g_sensor_meta.sensor_type[0] ? g_sensor_meta.sensor_type : "aniqlanmadi");
    LOG_PRINTF( "│  Interval   : %-26s│\n", "30s");
    LOG_PRINTLN("└──────────────────────────────────────────┘");
    LOG_PRINTLN("Tayyor!\n");
}

// ═══════════════════════════════════════════════════════════════════════════════
// Loop
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();
    bool read_time = (now - node_last_ms >= node_retry_ms || node_last_ms == 0);
    if (!read_time) { delay(50); return; }
    node_last_ms = now;

    // ── Meter ulanish ─────────────────────────────────────────────────────────
    if (!dlms_connected) {
        LOG_PRINT("Meter reconnect...");
        if (!sensor_connect()) {
            LOG_PRINTLN(" XATO");
            node_fail_count++;
            if (node_fail_count >= 3) {
                node_retry_ms = min(node_retry_ms * 2, NODE_METER_MAX_MS);
                LOG_PRINTF("Keyingi urinish %lu s keyin\n", node_retry_ms / 1000);
            }
            return;
        }
        node_fail_count = 0;
        node_retry_ms   = NODE_READ_MS;
        LOG_PRINTLN(" OK");
        if (!g_sensor_meta.meter_serial[0])
            dlms_get_string(1, OBIS_SERIAL, 2,
                            g_sensor_meta.meter_serial,
                            sizeof(g_sensor_meta.meter_serial));
        if (!g_sensor_meta.sensor_type[0]) sensor_detect_type();
    }

    // ── Relay buyruq (downlink dan kelgan) ────────────────────────────────────
    if (node_pending_relay) {
        bool ok = sensor_relay(node_pending_relay);
        LOG_PRINTF("Relay %s: %s\n",
                   node_pending_relay == 2 ? "ON" : "OFF", ok ? "OK" : "XATO");
        node_pending_relay = 0;
    }

    // ── Sensor o'qish ─────────────────────────────────────────────────────────
    SensorData d;
    if (!sensor_read(d)) {
        LOG_PRINTLN("O'qish xato — meter sessiyasi uzildi");
        dlms_disconnect();
        return;
    }

    // ── LoRa TX: uplink yuborish ──────────────────────────────────────────────
    bool sent = node_send_uplink(d);
    LOG_PRINTF("LoRa TX: %s\n", sent ? "OK" : "XATO");

    // ── LoRa RX: downlink oynasi (3s) ────────────────────────────────────────
    if (sent) {
        LoRa.receive();
        node_wait_downlink();
    }

    // Meter sessiyasini yopish — DLMS 30s inaktivlikda o'zi uzadi,
    // shuning uchun har o'qishdan keyin clean disconnect qilish yaxshiroq.
    // Keyingi loop iteratsiyasida qayta ulanadi.
    dlms_disconnect();
}
