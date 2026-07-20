#pragma once
/**
 * lora_gw.h — LoRa Gateway firmware
 *
 * Gateway (WiFi yonida):
 *   1. LoRa RX → Node dan sensor ma'lumot qabul
 *   2. WiFi → Backend /api/readings ga POST
 *   3. Backend /api/commands → relay buyruq poll
 *   4. LoRa TX → Node ga downlink (relay buyruq)
 *
 * Gateway o'zi ham qurilma sifatida ro'yxatdan o'tadi.
 * Har bir node — alohida device_id (node MAC) bilan backendda ro'yxatdan o'tadi.
 *
 * Build: pio run -e lora_gateway
 */

// common.h main.cpp da LORA_GATEWAY blokida include qilinadi
// lora_packet.h ham u yerda include qilinadi
#include <ArduinoJson.h>

// ─── Gateway konstantalar ─────────────────────────────────────────────────────
#define GW_CMD_POLL_MS    30000UL   // Har 30s da command poll
#define GW_STATUS_MS      60000UL   // Har 60s da status yuborish
#define GW_HEALTH_MS      60000UL   // Har 60s da server health check
#define GW_MAX_NODES           8    // Bir vaqtda kuzatiladigan max node soni

// ─── Node holati (RAM da) ─────────────────────────────────────────────────────
struct NodeState {
    uint8_t  mac[6];
    char     device_id[20];   // "AABBCCDDEEFF"
    bool     registered;
    uint8_t  pending_relay;   // 0=yo'q, 1=off, 2=on
    unsigned long last_seen;
};

static NodeState gw_nodes[GW_MAX_NODES];
static int       gw_node_count = 0;

static char          gw_id[20]       = "";
static bool          gw_server_ok    = false;
static bool          gw_registered   = false;
static unsigned long gw_last_cmd_ms  = 0;
static unsigned long gw_last_hlth_ms = 0;
static unsigned long gw_last_stat_ms = 0;

// ─── Node topish / qo'shish ───────────────────────────────────────────────────
static NodeState* gw_find_node(const uint8_t mac[6]) {
    for (int i = 0; i < gw_node_count; i++)
        if (memcmp(gw_nodes[i].mac, mac, 6) == 0) return &gw_nodes[i];
    return nullptr;
}

static NodeState* gw_get_node(const uint8_t mac[6]) {
    NodeState* n = gw_find_node(mac);
    if (n) return n;
    if (gw_node_count >= GW_MAX_NODES) {
        LOG_PRINTLN("GW: node limit to'ldi!");
        return nullptr;
    }
    n = &gw_nodes[gw_node_count++];
    memset(n, 0, sizeof(*n));
    memcpy(n->mac, mac, 6);
    snprintf(n->device_id, sizeof(n->device_id),
             "%02X%02X%02X%02X%02X%02X",
             mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    LOG_PRINTF("GW: yangi node → %s\n", n->device_id);
    return n;
}

// ─── Node ni backendga ro'yxatdan o'tkazish ──────────────────────────────────
static void gw_register_node(NodeState* n, const LoRaUplink& pkt) {
    if (n->registered) return;
    bool is_te73 = (pkt.flags & 0x01) != 0;
    StaticJsonDocument<256> doc;
    doc["device_id"]        = n->device_id;
    doc["utility_type"]     = "electricity";
    doc["meter_type"]       = is_te73 ? "te73" : "te71";
    doc["meter_serial"]     = pkt.meter_serial;
    doc["software_version"] = FW_VERSION;
    doc["baud_rate"]        = 9600;
    doc["chip_model"]       = "ESP32+LoRa-Node";
    String body; serializeJson(doc, body);

    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s/api/register", g_cfg.server_url);
    if (!http_begin_url(http, url)) return;
    http.addHeader("Content-Type", "application/json");
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http_prepare(http, 8000);
    int code = http.POST(body);
    if (code == 200 || code == 201) {
        n->registered = true;
        LOG_PRINTF("GW: node %s ro'yxatga olindi\n", n->device_id);
    }
    http.end();
}

// ─── Uplink qabul → backend ──────────────────────────────────────────────────
static void gw_handle_uplink(const LoRaUplink& pkt, int rssi) {
    NodeState* node = gw_get_node(pkt.mac);
    if (!node) return;
    node->last_seen = millis();

    bool is_te73 = (pkt.flags & 0x01) != 0;

    // Fixed-point → float
    float v_l1 = pkt.v_l1 / 100.0f;
    float v_l2 = pkt.v_l2 / 100.0f;
    float v_l3 = pkt.v_l3 / 100.0f;
    float i_l1 = pkt.i_l1 / 1000.0f;
    float i_l2 = pkt.i_l2 / 1000.0f;
    float i_l3 = pkt.i_l3 / 1000.0f;
    float freq  = pkt.freq_chz / 100.0f;
    float energy = pkt.energy_wh / 1000.0f;
    float pf     = pkt.pf_pct / 100.0f;

    LOG_PRINTF("GW RX ← [%s] RSSI=%ddBm V=%.1fV P=%dW E=%.3fkWh\n",
               node->device_id, rssi, v_l1, (int)pkt.power_w, energy);

    if (!gw_server_ok) {
        LOG_PRINTLN("GW: server offline — ma'lumot yo'qoldi");
        return;
    }

    // Node ro'yxatdan o'tish (birinchi marta)
    gw_register_node(node, pkt);

    // Readings JSON
    StaticJsonDocument<512> doc;
    doc["device_id"]    = node->device_id;
    doc["utility_type"] = "electricity";
    doc["sensor_type"]  = is_te73 ? "te73" : "te71";
    doc["meter_serial"] = pkt.meter_serial;
    doc["fw_version"]   = FW_VERSION;
    doc["lora_rssi"]    = rssi;

    if (pkt.v_l1 != 0) doc["voltage_l1"] = serialized(String(v_l1, 2));
    if (pkt.i_l1 != 0) doc["current_l1"] = serialized(String(i_l1, 3));
    if (is_te73) {
        if (pkt.v_l2 != 0) doc["voltage_l2"] = serialized(String(v_l2, 2));
        if (pkt.v_l3 != 0) doc["voltage_l3"] = serialized(String(v_l3, 2));
        if (pkt.i_l2 != 0) doc["current_l2"] = serialized(String(i_l2, 3));
        if (pkt.i_l3 != 0) doc["current_l3"] = serialized(String(i_l3, 3));
    }
    if (pkt.power_w  != 0) doc["power_w"]    = (int)pkt.power_w;
    if (pkt.freq_chz != 0) doc["frequency"]  = serialized(String(freq, 2));
    if (pkt.energy_wh!= 0) doc["energy_kwh"] = serialized(String(energy, 3));
    if (pkt.pf_pct   != 0) doc["pf"]         = serialized(String(pf, 3));

    String body; serializeJson(doc, body);
    bool ok = http_post("/api/readings", body);
    LOG_PRINTF("GW: readings → %s\n", ok ? "OK" : "XATO");
}

// ─── Backend command poll → pending_relay ────────────────────────────────────
static void gw_poll_commands() {
    for (int i = 0; i < gw_node_count; i++) {
        NodeState* n = &gw_nodes[i];
        char path[80];
        snprintf(path, sizeof(path), "/api/commands/%s", n->device_id);
        String resp = http_get(path);
        if (resp.isEmpty()) continue;

        StaticJsonDocument<1024> doc;
        if (deserializeJson(doc, resp)) continue;

        for (JsonObject cmd : doc["commands"].as<JsonArray>()) {
            int id = cmd["id"];
            const char* action = cmd["action"];
            if (!action) continue;

            char ack[80];
            snprintf(ack, sizeof(ack), "/api/commands/%d/ack", id);

            if (strcmp(action, "relay_on") == 0) {
                n->pending_relay = 2;
                http_post(ack, "{}");
                LOG_PRINTF("GW: relay_on navbatga [%s]\n", n->device_id);
            } else if (strcmp(action, "relay_off") == 0) {
                n->pending_relay = 1;
                http_post(ack, "{}");
                LOG_PRINTF("GW: relay_off navbatga [%s]\n", n->device_id);
            } else if (strcmp(action, "reboot") == 0) {
                http_post(ack, "{}");
                LOG_PRINTLN("GW: reboot buyrug'i");
                delay(200); ESP.restart();
            } else {
                http_post(ack, "{}");
                LOG_PRINTF("GW: noma'lum cmd '%s'\n", action);
            }
        }
    }
}

// ─── Pending relay buyruqlarni LoRa downlink orqali yuborish ─────────────────
static void gw_send_downlinks() {
    for (int i = 0; i < gw_node_count; i++) {
        NodeState* n = &gw_nodes[i];
        if (n->pending_relay == 0) continue;

        LoRaDownlink dl;
        dl.pkt_type  = PKT_DOWNLINK;
        memcpy(dl.mac, n->mac, 6);
        dl.relay_cmd = n->pending_relay;
        lora_crc_set((uint8_t*)&dl, sizeof(dl));

        LoRa.beginPacket();
        LoRa.write((uint8_t*)&dl, sizeof(dl));
        bool ok = LoRa.endPacket();
        LOG_PRINTF("GW DL → [%s] relay_%s: %s\n",
                   n->device_id,
                   n->pending_relay == 2 ? "ON" : "OFF",
                   ok ? "OK" : "XATO");
        if (ok) n->pending_relay = 0;
        delay(50);
    }
    // TX tugagach RX rejimiga qaytish
    LoRa.receive();
}

// ═══════════════════════════════════════════════════════════════════════════════
// Setup
// ═══════════════════════════════════════════════════════════════════════════════
void setup() {
#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
    Serial.begin(115200);
    delay(200);
#endif

    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(gw_id, sizeof(gw_id), "%02X%02X%02X%02X%02X%02X",
             mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);

    LOG_PRINTLN();
    LOG_PRINTLN("╔══════════════════════════════════════════╗");
    LOG_PRINTLN("║  Meter Monitor v" FW_VERSION " — LoRa GATEWAY  ║");
    LOG_PRINTLN("║  WiFi + LoRa 433MHz                      ║");
    LOG_PRINTLN("╚══════════════════════════════════════════╝");
    LOG_PRINTF("Gateway ID: %s\n", gw_id);

    cfg_load();
    LOG_PRINTF("Server: %s\n", g_cfg.server_url);

    // BOOT tugmasi (GPIO0) 3s → WiFi reset
    pinMode(0, INPUT_PULLUP);
    if (digitalRead(0) == LOW) {
        delay(3000);
        if (digitalRead(0) == LOW) {
            LOG_PRINTLN("[BOOT] WiFi sozlamalari o'chirilmoqda...");
            WiFiManager wm; wm.resetSettings(); ESP.restart();
        }
    }

    // WiFi ulanish
#ifndef DEFAULT_WIFI_SSID
  #define DEFAULT_WIFI_SSID "12"
#endif
#ifndef DEFAULT_WIFI_PASS
  #define DEFAULT_WIFI_PASS "12345678"
#endif
    wifi_quick(DEFAULT_WIFI_SSID, DEFAULT_WIFI_PASS);
    wifi_setup("LoRaGW-Setup", "lora1234", gw_id, "LoRa Gateway");

    // Server + OTA
    gw_server_ok = server_check();
    if (gw_server_ok) {
        gw_registered = true;
        ota_check(gw_id, FW_VERSION);
    }

    // LoRa init
    LOG_PRINT("LoRa SX1278 init...");
    if (!lora_init()) {
        LOG_PRINTLN(" XATO! Modul topilmadi.");
        LOG_PRINTLN("  Ulanishni tekshiring: CS=5 RST=14 DIO0=2");
        while (true) delay(5000);
    }
    LoRa.receive();  // RX rejimida kutish
    LOG_PRINTF(" OK (433MHz, SF%d, BW%.0fkHz)\n", LORA_SF, LORA_BW / 1000.0);

    LOG_PRINTLN();
    LOG_PRINTLN("┌──────────────────────────────────────────┐");
    LOG_PRINTF( "│  Gateway ID : %-26s│\n", gw_id);
    LOG_PRINTF( "│  Server     : %-26s│\n", g_cfg.server_url);
    LOG_PRINTF( "│  Max nodes  : %-26d│\n", GW_MAX_NODES);
    LOG_PRINTLN("└──────────────────────────────────────────┘");
    LOG_PRINTLN("Tinglayapman...\n");
}

// ═══════════════════════════════════════════════════════════════════════════════
// Loop
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();

    // ── LoRa paket tekshirish (interrupt-less polling) ────────────────────────
    int pkt_size = LoRa.parsePacket();
    if (pkt_size > 0) {
        int rssi = LoRa.packetRssi();

        if (pkt_size == (int)sizeof(LoRaUplink)) {
            LoRaUplink pkt;
            LoRa.readBytes((uint8_t*)&pkt, sizeof(pkt));
            if (pkt.pkt_type == PKT_UPLINK &&
                lora_crc_ok((uint8_t*)&pkt, sizeof(pkt))) {
                gw_handle_uplink(pkt, rssi);
                // Darhol pending downlink bor bo'lsa yubor
                gw_send_downlinks();
            } else {
                LOG_PRINTF("GW: noto'g'ri paket (type=0x%02X, size=%d)\n",
                           pkt.pkt_type, pkt_size);
            }
        } else {
            // Noto'g'ri o'lcham — bufer tozalash
            while (LoRa.available()) LoRa.read();
            LOG_PRINTF("GW: kutilmagan paket hajmi=%d\n", pkt_size);
        }
        // TX tugagach RX ga qaytish (gw_handle_uplink da bo'lmasa)
        LoRa.receive();
    }

    // ── Server health check (har 60s) ─────────────────────────────────────────
    if (now - gw_last_hlth_ms >= GW_HEALTH_MS) {
        gw_last_hlth_ms = now;
        bool prev = gw_server_ok;
        gw_server_ok = server_check();
        if (gw_server_ok && !prev) {
            LOG_PRINTLN("GW: server qaytdi!");
            if (!gw_registered) {
                gw_registered = true;
            }
        }
    }

    // ── Command poll + status (har 30s) ──────────────────────────────────────
    if (gw_server_ok && WiFi.status() == WL_CONNECTED &&
        now - gw_last_cmd_ms >= GW_CMD_POLL_MS) {
        gw_last_cmd_ms = now;
        gw_poll_commands();
    }

    if (gw_server_ok && WiFi.status() == WL_CONNECTED &&
        now - gw_last_stat_ms >= GW_STATUS_MS) {
        gw_last_stat_ms = now;
        app_send_status(gw_id, FW_VERSION);
        ota_check(gw_id, FW_VERSION);
    }
}
