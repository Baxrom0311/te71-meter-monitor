#pragma once
/**
 * lora_node.h — LoRa Node firmware (WiFi YO'Q)
 *
 * Barcha sensor turlarini qo'llab-quvvatlaydi:
 *   SENSOR_SOIL        → LoRaSoilUplink  (12 bayt)
 *   SENSOR_SOUND       → LoRaSoundUplink (12 bayt)
 *   SENSOR_WATER       → LoRaWaterUplink (22 bayt)
 *   SENSOR_GAS         → LoRaGasUplink   (20 bayt)
 *   SENSOR_ELECTRICITY → LoRaUplink      (47 bayt, maxsus DLMS/relay/downlink)
 *
 * Build:
 *   pio run -e soil_lora
 *   pio run -e sound_lora
 *   pio run -e water_lora
 *   pio run -e gas_lora
 *   pio run -e electricity_lora
 */

#include <Arduino.h>
#include <esp_system.h>
#include "core/log.h"
#include "core/watchdog.h"

// Water/Gas sensorlari Preferences.h dan foydalanadi (impuls saqlash)
#if defined(SENSOR_WATER) || defined(SENSOR_GAS)
  #include <Preferences.h>
#endif

// ─── Minimal config (WiFi/HTTP yo'q) ─────────────────────────────────────────
struct AppConfig { bool test_mode; };
static AppConfig g_cfg = { false };

// ─── Sensor tanlash ───────────────────────────────────────────────────────────
#if defined(SENSOR_SOIL)
  #include "sensors/soil.h"
  #define NODE_SENSOR_NAME "Tuproq"
#elif defined(SENSOR_SOUND)
  #include "sensors/sound.h"
  #define NODE_SENSOR_NAME "Ovoz"
#elif defined(SENSOR_WATER)
  #include "sensors/water.h"
  #define NODE_SENSOR_NAME "Suv"
#elif defined(SENSOR_GAS)
  #include "sensors/gas.h"
  #define NODE_SENSOR_NAME "Gaz"
#elif defined(SENSOR_ELECTRICITY)
  #include "sensors/electricity.h"
  #define NODE_SENSOR_NAME "Elektr"
#else
  #define SENSOR_ELECTRICITY
  #include "sensors/electricity.h"
  #define NODE_SENSOR_NAME "Elektr"
#endif
#include "lora_packet.h"

// ─── Display ─────────────────────────────────────────────────────────────────
#if defined(HAVE_LCD) && defined(SENSOR_SOIL)
  #include "display/disp_soil.h"
#elif defined(HAVE_LCD) && defined(SENSOR_SOUND)
  #include "display/disp_sound.h"
#elif defined(HAVE_LCD) && defined(SENSOR_ELECTRICITY)
  #include "display/disp_elec.h"
#else
  #include "display/disp_none.h"
#endif

// ─── Konstantalar ─────────────────────────────────────────────────────────────
#ifndef READ_INTERVAL_MS
  #define READ_INTERVAL_MS  30000UL
#endif
#define NODE_READ_MS        READ_INTERVAL_MS

// ─── Node holati ──────────────────────────────────────────────────────────────
static uint8_t       node_mac[6];
static char          node_id[20];
static unsigned long node_last_ms  = 0;

// ─── Mesh relay: boshqa nodelar paketini qayta yuborish ───────────────────────
// TX dan keyin LORA_RELAY_LISTEN_MS davomida tinglaydi.
// Boshqa node ning paketini qabul qilsa, TTL ni kamaytiradi va relay qiladi.
static void node_relay_listen() {
#ifdef SKIP_LORA_INIT
    return;
#endif
    LoRa.receive();
    unsigned long start = millis();
    while (millis() - start < LORA_RELAY_LISTEN_MS) {
        wdt_feed();
        int sz = LoRa.parsePacket();
        if (sz > 0 && sz <= 64) {
            uint8_t buf[64];
            LoRa.readBytes(buf, sz);

            // Minimal tekshirish: type(1)+mac(6)+flags(1) = 8 bayt minimum
            if (sz < 8) continue;

            // O'z paketini relay qilmaslik
            if (memcmp(buf + 1, node_mac, 6) == 0) continue;

            // Deshifrlash + CRC tekshirish
            if (!lora_decrypt_pkt(buf, sz)) {
                LOG_PRINTLN("RELAY: CRC/kalit xato — o'tkazib yuborildi");
                continue;
            }

            // TTL tekshirish
            uint8_t ttl = lora_ttl_get(buf[7]);
            if (ttl == 0) continue;  // TTL tugagan — relay qilinmaydi

            // TTL kamaytirish
            buf[7] = lora_ttl_dec(buf[7]);

            // Tasodifiy kechikish — to'qnashuvni oldini olish (50-300ms)
            {
                unsigned long d = random(50, 300);
                unsigned long t = millis(); while (millis() - t < d) { wdt_feed(); yield(); }
            }

            // Qayta shifrlash (CRC yangilanadi chunki flags o'zgardi)
            lora_encrypt_pkt(buf, sz);

            // Relay TX
            LoRa.beginPacket();
            LoRa.write(buf, sz);
            bool ok = LoRa.endPacket();
            LoRa.receive();

            LOG_PRINTF("RELAY: %02X%02X%02X → TTL=%d %s\n",
                       buf[1], buf[2], buf[3], ttl - 1, ok ? "OK" : "XATO");
        }
        yield();
    }
}

// =============================================================================
// ODDIY SENSORLAR (soil, sound, water, gas)
// =============================================================================
#if !defined(SENSOR_ELECTRICITY)

// ─── Paket qurish va yuborish ────────────────────────────────────────────────
#if defined(SENSOR_SOIL)
static bool node_send(const SensorData& d) {
    LoRaSoilUplink pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.pkt_type = PKT_UPLINK_SOIL;
    memcpy(pkt.mac, node_mac, 6);
    pkt.flags    = lora_flags_make(g_cfg.test_mode);
    pkt.humidity = (int16_t)(d.humidity * 100.0f);
    lora_encrypt_pkt((uint8_t*)&pkt, sizeof(pkt));

    LOG_PRINTF("LoRa TX -> [%s] namlik=%.1f%% (%d bayt)\n",
               node_id, d.humidity, (int)sizeof(pkt));
    LoRa.beginPacket();
    LoRa.write((uint8_t*)&pkt, sizeof(pkt));
    return LoRa.endPacket();
}

#elif defined(SENSOR_SOUND)
static bool node_send(const SensorData& d) {
    LoRaSoundUplink pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.pkt_type = PKT_UPLINK_SOUND;
    memcpy(pkt.mac, node_mac, 6);
    pkt.flags    = lora_flags_make(g_cfg.test_mode);
    pkt.level    = (int16_t)(d.level * 100.0f);
    lora_encrypt_pkt((uint8_t*)&pkt, sizeof(pkt));

    LOG_PRINTF("LoRa TX -> [%s] ovoz=%.1f%% (%d bayt)\n",
               node_id, d.level, (int)sizeof(pkt));
    LoRa.beginPacket();
    LoRa.write((uint8_t*)&pkt, sizeof(pkt));
    return LoRa.endPacket();
}

#elif defined(SENSOR_WATER)
static bool node_send(const SensorData& d) {
    LoRaWaterUplink pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.pkt_type = PKT_UPLINK_WATER;
    memcpy(pkt.mac, node_mac, 6);
    pkt.flags    = lora_flags_make(g_cfg.test_mode);
    pkt.p_bottom = (int16_t)(d.pressure_bottom_bar * 1000.0f);
    pkt.p_top    = (int16_t)(d.pressure_top_bar * 1000.0f);
    pkt.flow     = (int16_t)(d.flow_rate * 100.0f);
    pkt.volume   = (int32_t)(d.volume_m3 * 1000.0f);
    if (!isnan(d.temperature_c))
        pkt.temp = (int16_t)(d.temperature_c * 100.0f);
    lora_encrypt_pkt((uint8_t*)&pkt, sizeof(pkt));

    LOG_PRINTF("LoRa TX -> [%s] suv p=%.3f/%.3f oqim=%.1f hajm=%.3f (%d bayt)\n",
               node_id, d.pressure_bottom_bar, d.pressure_top_bar,
               d.flow_rate, d.volume_m3, (int)sizeof(pkt));
    LoRa.beginPacket();
    LoRa.write((uint8_t*)&pkt, sizeof(pkt));
    return LoRa.endPacket();
}

#elif defined(SENSOR_GAS)
static bool node_send(const SensorData& d) {
    LoRaGasUplink pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.pkt_type = PKT_UPLINK_GAS;
    memcpy(pkt.mac, node_mac, 6);
    pkt.flags    = lora_flags_make(g_cfg.test_mode);
    pkt.pressure = (int16_t)(d.pressure_bar * 1000.0f);
    pkt.flow     = (int16_t)(d.flow_rate * 1000.0f);
    pkt.volume   = (int32_t)(d.volume_m3 * 1000.0f);
    if (!isnan(d.temperature_c))
        pkt.temp = (int16_t)(d.temperature_c * 100.0f);
    lora_encrypt_pkt((uint8_t*)&pkt, sizeof(pkt));

    LOG_PRINTF("LoRa TX -> [%s] gaz p=%.3f oqim=%.3f hajm=%.3f (%d bayt)\n",
               node_id, d.pressure_bar, d.flow_rate, d.volume_m3,
               (int)sizeof(pkt));
    LoRa.beginPacket();
    LoRa.write((uint8_t*)&pkt, sizeof(pkt));
    return LoRa.endPacket();
}
#endif  // SENSOR_*

// ─── Setup ────────────────────────────────────────────────────────────────────
void setup() {
#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
    Serial.begin(115200);
    unsigned long _t = millis(); while (millis() - _t < 200) yield();
#endif
    esp_read_mac(node_mac, ESP_MAC_WIFI_STA);
    snprintf(node_id, sizeof(node_id), "%02X%02X%02X%02X%02X%02X",
             node_mac[0], node_mac[1], node_mac[2],
             node_mac[3], node_mac[4], node_mac[5]);

    LOG_PRINTLN();
    LOG_PRINTLN("╔══════════════════════════════════════════╗");
    LOG_PRINTLN("║  Meter Monitor v" FW_VERSION " — LoRa MESH NODE ║");
    LOG_PRINTF( "║  WiFi YO'Q | %-28s║\n", NODE_SENSOR_NAME " + LoRa 433MHz");
    LOG_PRINTLN("╚══════════════════════════════════════════╝");
    LOG_PRINTF("Node ID: %s\n", node_id);

    LOG_PRINT("LoRa SX1278 init...");
#ifdef SKIP_LORA_INIT
    LOG_PRINTLN(" [SKIP_LORA_INIT] - serial test only");
#else
    if (!lora_init()) {
        LOG_PRINTLN(" XATO! Modul topilmadi.");
        LOG_PRINTLN("  Ulanishni tekshiring: CS=15 RST=14 DIO0=2");
        while (true) yield();
    }
    LOG_PRINTF(" OK (433MHz, SF%d, BW%.0fkHz, PWR=%ddBm)\n",
               LORA_SF, LORA_BW / 1000.0, LORA_TX_PWR);
#endif

    disp_init();
    sensor_init();

    LOG_PRINTLN();
    LOG_PRINTLN("┌──────────────────────────────────────────┐");
    LOG_PRINTF( "│  Node ID  : %-28s│\n", node_id);
    LOG_PRINTF( "│  Sensor   : %-28s│\n", NODE_SENSOR_NAME);
    {
        char _iv[29];
        snprintf(_iv, sizeof(_iv), "%lu s", NODE_READ_MS / 1000);
        LOG_PRINTF("│  Interval : %-28s│\n", _iv);
    }
    LOG_PRINTLN("└──────────────────────────────────────────┘");

    ota_mark_valid();
    wdt_init();
    LOG_PRINTLN("Tayyor!\n");
}

// ─── Loop ─────────────────────────────────────────────────────────────────────
void loop() {
    wdt_feed();
    unsigned long now = millis();

    // Sensor o'qish vaqti kelmagan bo'lsa — relay tinglash
    if (node_last_ms != 0 && now - node_last_ms < NODE_READ_MS) {
        node_relay_listen();  // Bo'sh vaqtda boshqa nodelar uchun relay
        return;
    }
    node_last_ms = now;

    SensorData d;
    if (!sensor_read(d) || !d.valid) {
        LOG_PRINTLN("Sensor o'qish xato");
        return;
    }
    disp_show_reading(d);
#ifndef SKIP_LORA_INIT
    bool sent = node_send(d);
    LOG_PRINTF("LoRa TX: %s\n", sent ? "OK" : "XATO");
    if (sent) node_relay_listen();  // TX dan keyin ham relay tinglash
#else
    LOG_PRINTLN("[SKIP] Sensor read OK (LoRa o'chirilgan)");
    unsigned long _st = millis(); while (millis() - _st < 5000) yield();
#endif
}

// =============================================================================
// ELEKTR HISOBLAGICH (maxsus DLMS/relay/downlink)
// =============================================================================
#else  // SENSOR_ELECTRICITY

#define NODE_METER_MAX_MS   300000UL   // Elektr: maksimal retry interval

static int           node_pending_relay = 0;
static int           node_fail_count    = 0;
static unsigned long node_retry_ms      = NODE_READ_MS;
static const int     NODE_DL_WAIT_MS    = 3000;

static bool node_send_uplink(const SensorData& d) {
    LoRaUplink pkt;
    memset(&pkt, 0, sizeof(pkt));

    pkt.pkt_type = PKT_UPLINK;
    memcpy(pkt.mac, node_mac, 6);
    pkt.flags = LORA_TTL_DEFAULT << LORA_TTL_SHIFT;
    if (strcmp(d.sensor_type, "te73") == 0) pkt.flags |= 0x01;

    strncpy(pkt.meter_serial, d.meter_serial, 12);
    pkt.meter_serial[12] = '\0';

    if (!isnan(d.voltage_l1)) pkt.v_l1      = (int16_t)(d.voltage_l1 * 100.0f);
    if (!isnan(d.voltage_l2)) pkt.v_l2      = (int16_t)(d.voltage_l2 * 100.0f);
    if (!isnan(d.voltage_l3)) pkt.v_l3      = (int16_t)(d.voltage_l3 * 100.0f);
    if (!isnan(d.current_l1)) pkt.i_l1      = (int16_t)(d.current_l1 * 1000.0f);
    if (!isnan(d.current_l2)) pkt.i_l2      = (int16_t)(d.current_l2 * 1000.0f);
    if (!isnan(d.current_l3)) pkt.i_l3      = (int16_t)(d.current_l3 * 1000.0f);
    if (!isnan(d.power_w))    pkt.power_w   = (int32_t)d.power_w;
    if (!isnan(d.frequency))  pkt.freq_chz  = (int16_t)(d.frequency * 100.0f);
    if (!isnan(d.energy_kwh)) pkt.energy_wh = (int32_t)(d.energy_kwh * 1000.0f);
    if (!isnan(d.pf))         pkt.pf_pct    = (int16_t)(d.pf * 100.0f);

    lora_encrypt_pkt((uint8_t*)&pkt, sizeof(pkt));

    LOG_PRINTF("LoRa TX -> [%s] V=%.1fV P=%dW E=%.3fkWh (%d bayt)\n",
               pkt.meter_serial, pkt.v_l1 / 100.0f,
               (int)pkt.power_w, pkt.energy_wh / 1000.0f,
               (int)sizeof(pkt));

    LoRa.beginPacket();
    LoRa.write((uint8_t*)&pkt, sizeof(pkt));
    return LoRa.endPacket();
}

static void node_wait_downlink() {
    uint32_t t = millis();
    while (millis() - t < NODE_DL_WAIT_MS) {
        int sz = LoRa.parsePacket();
        if (sz == (int)sizeof(LoRaDownlink)) {
            LoRaDownlink dl;
            LoRa.readBytes((uint8_t*)&dl, sizeof(dl));
            if (dl.pkt_type != PKT_DOWNLINK)             continue;
            if (!lora_decrypt_pkt((uint8_t*)&dl, sizeof(dl))) {
                LOG_PRINTLN("LoRa RX: deshifrlash/CRC xato");
                continue;
            }
            if (memcmp(dl.mac, node_mac, 6) != 0)        continue;
            if (dl.relay_cmd > 0) {
                node_pending_relay = dl.relay_cmd;
                LOG_PRINTF("LoRa RX: relay_cmd=%d (%s)\n",
                           dl.relay_cmd, dl.relay_cmd == 2 ? "ON" : "OFF");
            }
        }
        yield();
    }
}

void setup() {
#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
    Serial.begin(115200);
    unsigned long _t = millis(); while (millis() - _t < 200) yield();
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

    LOG_PRINT("LoRa SX1278 init...");
    if (!lora_init()) {
        LOG_PRINTLN(" XATO! Modul topilmadi.");
        LOG_PRINTLN("  Ulanishni tekshiring: CS=15 RST=14 DIO0=2");
        while (true) yield();
    }
    LOG_PRINTF(" OK (433MHz, SF%d, BW%.0fkHz, PWR=%ddBm)\n",
               LORA_SF, LORA_BW / 1000.0, LORA_TX_PWR);

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
            unsigned long _w = millis(); while (millis() - _w < 500) yield();
        }
    }
    if (!found) LOG_PRINTLN(" XATO — meter topilmadi, loop da qayta urinadi");

    LOG_PRINTLN();
    LOG_PRINTLN("┌──────────────────────────────────────────┐");
    LOG_PRINTF( "│  Node ID    : %-26s│\n", node_id);
    LOG_PRINTF( "│  Hisoblagich: %-26s│\n",
        g_sensor_meta.meter_serial[0] ? g_sensor_meta.meter_serial : "topilmadi");
    LOG_PRINTF( "│  Tur        : %-26s│\n",
        g_sensor_meta.sensor_type[0] ? g_sensor_meta.sensor_type : "aniqlanmadi");
    LOG_PRINTLN("└──────────────────────────────────────────┘");
    ota_mark_valid();
    wdt_init();
    LOG_PRINTLN("Tayyor!\n");
}

void loop() {
    wdt_feed();
    unsigned long now = millis();
    bool read_time = (now - node_last_ms >= node_retry_ms || node_last_ms == 0);
    if (!read_time) {
        node_relay_listen();  // Bo'sh vaqtda relay
        return;
    }
    node_last_ms = now;

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

    if (node_pending_relay) {
        bool ok = sensor_relay(node_pending_relay);
        LOG_PRINTF("Relay %s: %s\n",
                   node_pending_relay == 2 ? "ON" : "OFF", ok ? "OK" : "XATO");
        node_pending_relay = 0;
    }

    SensorData d;
    if (!sensor_read(d)) {
        LOG_PRINTLN("O'qish xato — meter sessiyasi uzildi");
        dlms_disconnect();
        return;
    }

    bool sent = node_send_uplink(d);
    LOG_PRINTF("LoRa TX: %s\n", sent ? "OK" : "XATO");

    if (sent) {
        LoRa.receive();
        node_wait_downlink();
        node_relay_listen();  // Downlink dan keyin mesh relay
    }
    dlms_disconnect();
}

#endif  // !SENSOR_ELECTRICITY
