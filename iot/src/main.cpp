/**
 * Meter Monitor — ESP32 Firmware v4.1.0
 *
 * Arxitektura:
 *   core/log.h       → Debug logging
 *   core/config.h    → NVS konfiguratsiya
 *   core/wifi.h      → WiFi (non-blocking reconnect)
 *   core/http.h      → HTTP + OTA
 *   core/api.h       → Backend API
 *   sensors/dlms.h   → DLMS/HDLC protokol
 *   sensors/*.h      → Sensor modullari
 *   display/*.h      → LCD display modullari
 */

#define FW_VERSION "4.2.0"

// ═══════════════════════════════════════════════════════════════════════════════
// ADS1115 TEST MODE
// ═══════════════════════════════════════════════════════════════════════════════
#ifdef ADS1115_TEST

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_ADS1X15.h>

#define ADS_SDA        21
#define ADS_SCL        22
#define ADS_ADDR       0x48
#define SHUNT_OHM      100.0f
#define SENSOR_MA_MIN   4.0f
#define SENSOR_MA_MAX  20.0f
#define SENSOR_MPA_MAX  0.6f

Adafruit_ADS1115 ads;

void setup() {
    Serial.begin(115200);
    unsigned long t = millis(); while (millis() - t < 500) yield();
    Serial.println("\n=== ADS1115 + HY-131 Test ===\n");

    Wire.begin(ADS_SDA, ADS_SCL);
    if (!ads.begin(ADS_ADDR)) {
        Serial.println("XATO: ADS1115 topilmadi!");
        while (true) yield();
    }
    ads.setGain(GAIN_TWO);
    ads.setDataRate(RATE_ADS1115_128SPS);
    Serial.printf("%-8s  %-9s  %-9s  %-10s  %-8s\n", "Raw", "V", "mA", "MPa", "bar");
}

void loop() {
    long sum = 0;
    for (int i = 0; i < 8; i++) {
        sum += ads.readADC_SingleEnded(0);
        unsigned long t = millis(); while (millis() - t < 10) yield();
    }
    int16_t raw = (int16_t)(sum / 8);
    float voltage = raw * 0.0000625f;
    float current_mA = voltage / (SHUNT_OHM / 1000.0f);
    float pressure_MPa = 0.0f;
    if (current_mA >= SENSOR_MA_MIN) {
        pressure_MPa = (current_mA - SENSOR_MA_MIN) / (SENSOR_MA_MAX - SENSOR_MA_MIN) * SENSOR_MPA_MAX;
        pressure_MPa = constrain(pressure_MPa, 0.0f, SENSOR_MPA_MAX);
    }
    Serial.printf("%-8d  %-9.4f  %-9.3f  %-10.4f  %-8.3f\n",
                  raw, voltage, current_mA, pressure_MPa, pressure_MPa * 10.0f);
    unsigned long t = millis(); while (millis() - t < 1000) yield();
}

#elif defined(LORA_NODE)
// ═══════════════════════════════════════════════════════════════════════════════
// LORA NODE MODE
// ═══════════════════════════════════════════════════════════════════════════════
#include "lora_node.h"

#elif defined(LORA_GATEWAY)
// ═══════════════════════════════════════════════════════════════════════════════
// LORA GATEWAY MODE
// ═══════════════════════════════════════════════════════════════════════════════
#include "common.h"
#include "lora_packet.h"
#include "lora_gw.h"

#else
// ═══════════════════════════════════════════════════════════════════════════════
// NORMAL FIRMWARE MODE
// ═══════════════════════════════════════════════════════════════════════════════
#include "common.h"

// ─── Sensor ──────────────────────────────────────────────────────────────────
#ifdef SENSOR_ELECTRICITY
  #include "sensors/electricity.h"
#elif defined(SENSOR_WATER)
  #include "sensors/water.h"
#elif defined(SENSOR_GAS)
  #include "sensors/gas.h"
#elif defined(SENSOR_SOIL)
  #include "sensors/soil.h"
#elif defined(SENSOR_SOUND)
  #include "sensors/sound.h"
#else
  #error "Sensor flag kerak: -DSENSOR_ELECTRICITY | _WATER | _GAS | _SOIL | _SOUND"
#endif

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

// ─── Konstantalar ────────────────────────────────────────────────────────────
#define WIFI_AP_NAME     "Bakhromdev"
#define WIFI_AP_PASS     "998935580311"
#ifndef READ_INTERVAL_MS
  #define READ_INTERVAL_MS  30000UL
#endif
#define CMD_POLL_MS       60000UL
#define HEALTH_CHECK_MS   60000UL
#define OFFLINE_BUF_SIZE  50

// ─── App state ───────────────────────────────────────────────────────────────
static char  device_id[20] = "";
static bool  registered    = false;
static bool  server_ok     = false;
static bool  prev_wifi_ok  = false;

static unsigned long last_read_ms   = 0;
static unsigned long last_cmd_ms    = 0;
static unsigned long last_health_ms = 0;
#ifdef SENSOR_SOUND
static unsigned long last_sound_lcd_ms = 0;
#define SOUND_LCD_MS  200UL   // Sound LCD har 200ms yangilansin
#endif

#ifdef SENSOR_ELECTRICITY
static int           pending_relay    = 0;
static int           meter_fail_count = 0;
static unsigned long meter_retry_ms   = 30000UL;
#define METER_RETRY_MAX_MS  300000UL
static bool g_lora_ok = false;

static void lora_check() {
    if (WiFi.status() != WL_CONNECTED) return;
    String resp = http_get("/api/public/lora-status");
    if (resp.isEmpty()) { g_lora_ok = false; return; }
    StaticJsonDocument<64> doc;
    if (deserializeJson(doc, resp)) { g_lora_ok = false; return; }
    g_lora_ok = doc["online"] | false;
}
#endif

// ─── Offline buffer ──────────────────────────────────────────────────────────
static String off_buf[OFFLINE_BUF_SIZE];
static int    off_head  = 0;
static int    off_count = 0;

// Minimum heap — bufer yozishni to'xtatish chegarasi (16KB qoldirish)
#define MIN_HEAP_BYTES  16384

static void buf_push(const String& json) {
    // Heap himoyasi: juda kam joy qolsa, eski yozuvlarni tozalash
    if (ESP.getFreeHeap() < MIN_HEAP_BYTES) {
        LOG_PRINTF("HEAP OGOHLANTIRISH: %d bayt qoldi — bufer tozalanadi\n",
                   (int)ESP.getFreeHeap());
        for (int i = 0; i < OFFLINE_BUF_SIZE; i++) off_buf[i] = "";
        off_head = 0;
        off_count = 0;
        return;
    }
    off_buf[off_head] = json;
    off_head = (off_head + 1) % OFFLINE_BUF_SIZE;
    if (off_count < OFFLINE_BUF_SIZE) off_count++;
}

static void buf_flush() {
    if (off_count == 0 || !server_ok) return;
    int start = (off_head - off_count + OFFLINE_BUF_SIZE) % OFFLINE_BUF_SIZE;
    int sent = 0;
    for (int i = 0; i < off_count; i++) {
        int idx = (start + i) % OFFLINE_BUF_SIZE;
        if (!http_post("/api/readings", off_buf[idx])) break;
        off_buf[idx] = "";  // RAM ni bo'shatish
        sent++;
    }
    off_count -= sent;
    if (off_count < 0) off_count = 0;
}

static bool do_register() {
    return sensor_do_register(device_id, FW_VERSION);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Setup
// ═══════════════════════════════════════════════════════════════════════════════
void setup() {
#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
    Serial.begin(115200);
    unsigned long _t = millis(); while (millis() - _t < 200) yield();
#endif

    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(device_id, sizeof(device_id), "%02X%02X%02X%02X%02X%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    LOG_PRINTLN();
    LOG_PRINTLN("╔══════════════════════════════════════════╗");
    LOG_PRINTLN("║       Meter Monitor v" FW_VERSION "            ║");
    LOG_PRINTLN("╚══════════════════════════════════════════╝");
    LOG_PRINTF("ID: %s\n", device_id);

    cfg_load();
    nvs_health_check();

    // BOOT tugmasi (GPIO0) 3s → WiFi reset
    pinMode(0, INPUT_PULLUP);
    if (digitalRead(0) == LOW) {
        unsigned long t = millis();
        while (millis() - t < 3000 && digitalRead(0) == LOW) yield();
        if (digitalRead(0) == LOW) {
            WiFiManager wm;
            wm.resetSettings();
            ESP.restart();
        }
    }

    // LCD: WiFi dan OLDIN
#ifndef SENSOR_ELECTRICITY
    disp_init();
#endif

    // WiFi
#ifndef DEFAULT_WIFI_SSID
  #define DEFAULT_WIFI_SSID "12"
#endif
#ifndef DEFAULT_WIFI_PASS
  #define DEFAULT_WIFI_PASS "12345678"
#endif
    wifi_quick(DEFAULT_WIFI_SSID, DEFAULT_WIFI_PASS);
    wifi_setup(WIFI_AP_NAME, WIFI_AP_PASS, device_id, g_cfg.meter_serial);

    // NTP vaqt sinxronlash (WiFi ulangandan keyin)
    if (WiFi.status() == WL_CONNECTED) ntp_init();

    server_ok = server_check();
    if (server_ok) ota_check(device_id, FW_VERSION);

    // ── Sensor ───────────────────────────────────────────────────────────────
#ifdef SENSOR_ELECTRICITY
    sensor_init();
    wifi_pause();

    bool meter_found = false;
    for (int attempt = 1; attempt <= 3; attempt++) {
        if (sensor_connect()) {
            dlms_get_string(1, OBIS_SERIAL, 2,
                            g_sensor_meta.meter_serial,
                            sizeof(g_sensor_meta.meter_serial));
            sensor_detect_type();
            cfg_save_meter_serial(g_sensor_meta.meter_serial);
            meter_found = true;
            break;
        }
        unsigned long t = millis(); while (millis() - t < 500) yield();
    }

    wifi_resume();
#else
    sensor_init();
#endif

    server_ok = server_check();
    if (server_ok) {
        registered = do_register();
        buf_flush();
    }
#ifdef SENSOR_ELECTRICITY
    if (server_ok) lora_check();
    disp_show_status(WiFi.status() == WL_CONNECTED, server_ok, g_lora_ok);
#endif

    // Watchdog va OTA rollback
    ota_mark_valid();
    wdt_init();

    LOG_PRINTLN("Tayyor!\n");
}

// ═══════════════════════════════════════════════════════════════════════════════
// Loop — blokirovkasiz
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();
    wdt_feed();

    // WiFi uzilish aniqlash
    bool wifi_now = (WiFi.status() == WL_CONNECTED);
    if (prev_wifi_ok && !wifi_now) {
        g_diag_wifi_drops++;
        diag_error("WiFi uzildi");
    }
    prev_wifi_ok = wifi_now;

    // WiFi: non-blocking qayta ulanish
    wifi_loop();

    // Sound LCD: har 200ms real-time yangilash
#ifdef SENSOR_SOUND
    if (now - last_sound_lcd_ms >= SOUND_LCD_MS) {
        last_sound_lcd_ms = now;
        SensorData _ld;
        if (sensor_read(_ld)) disp_show_reading(_ld);
    }
#endif

    // Sensor o'qish vaqti tekshirish
#ifdef SENSOR_ELECTRICITY
    bool meter_time = (now - last_read_ms >= meter_retry_ms || last_read_ms == 0);
#else
    bool meter_time = (now - last_read_ms >= g_cfg.read_interval_ms || last_read_ms == 0);
#endif

    // Server health check (har 60s, faqat WiFi bor bo'lsa)
    if (!meter_time && WiFi.status() == WL_CONNECTED &&
        now - last_health_ms >= HEALTH_CHECK_MS) {
        last_health_ms = now;
        bool prev = server_ok;
        server_ok = server_check();
        if (server_ok && !prev) {
            if (!registered) registered = do_register();
            buf_flush();
            ota_check(device_id, FW_VERSION);
        }
    }

    // ── Sensor o'qish ────────────────────────────────────────────────────────
    if (meter_time) {
        last_read_ms = now;

#ifdef SENSOR_ELECTRICITY
        wifi_pause();

        if (!dlms_connected) {
            if (!sensor_connect()) {
                wifi_resume();
                meter_fail_count++;
                g_diag_sensor_errors++;
                diag_error("Meter ulanish xato");
                if (meter_fail_count >= 3)
                    meter_retry_ms = min(meter_retry_ms * 2, METER_RETRY_MAX_MS);
                return;
            }
            meter_fail_count = 0;
            meter_retry_ms   = READ_INTERVAL_MS;
            if (!g_sensor_meta.meter_serial[0])
                dlms_get_string(1, OBIS_SERIAL, 2,
                                g_sensor_meta.meter_serial,
                                sizeof(g_sensor_meta.meter_serial));
            if (!g_sensor_meta.sensor_type[0])
                sensor_detect_type();
        }

        if (pending_relay) {
            sensor_relay(pending_relay);
            pending_relay = 0;
        }
#endif

        SensorData d;
        bool read_ok = sensor_read(d);

#ifdef SENSOR_ELECTRICITY
        bool wifi_ok = wifi_resume();
#else
        bool wifi_ok = (WiFi.status() == WL_CONNECTED);
#endif

        if (!read_ok) {
            g_diag_sensor_errors++;
#ifdef SENSOR_ELECTRICITY
            diag_error("Meter o'qish xato");
            dlms_disconnect();
#else
            diag_error("Sensor o'qish xato");
#endif
            return;
        }

        disp_show_reading(d);

        // Serverga yuborish — faqat POST, server_check periodic bo'ladi
        String json = sensor_build_json(device_id, FW_VERSION, d);

        // NTP timestamp qo'shish (offline bufer uchun muhim)
        // snprintf bilan — String concat heap fragmentatsiyasi yo'q
        char _ts[25];
        if (diag_timestamp(_ts, sizeof(_ts))) {
            int _lb = json.lastIndexOf('}');
            if (_lb > 0) {
                char _ts_frag[50];
                snprintf(_ts_frag, sizeof(_ts_frag), ",\"timestamp\":\"%s\"}", _ts);
                json = json.substring(0, _lb) + _ts_frag;
            }
        }

        if (wifi_ok && server_ok) {
            if (!registered) registered = do_register();
            if (!http_post("/api/readings", json)) {
                buf_push(json);
            }
        } else {
            buf_push(json);
        }

#ifdef SENSOR_ELECTRICITY
        disp_show_status(wifi_ok, server_ok, g_lora_ok);
#else
        disp_show_status(wifi_ok, server_ok, false);
#endif
    }

    // ── Periodic: health + flush + commands + OTA (har 60s) ──────────────
    if (WiFi.status() == WL_CONNECTED &&
        now - last_health_ms >= HEALTH_CHECK_MS) {
        last_health_ms = now;

        bool prev = server_ok;
        server_ok = server_check();

        if (server_ok) {
            if (!registered) registered = do_register();
            buf_flush();
#ifdef SENSOR_ELECTRICITY
            lora_check();
#endif
        }

        if (server_ok && !prev) {
            ota_check(device_id, FW_VERSION);
        }
    }

    // ── Command poll + status (har 60s, health dan alohida) ──────────────
    if (server_ok && WiFi.status() == WL_CONNECTED &&
        now - last_cmd_ms >= CMD_POLL_MS) {
        last_cmd_ms = now;
#ifdef SENSOR_ELECTRICITY
        app_poll_commands(device_id, &pending_relay);
#else
        app_poll_commands(device_id, nullptr);
#endif
        app_send_status(device_id, FW_VERSION);
    }
}

#endif // ADS1115_TEST
