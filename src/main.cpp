/**
 * Meter Monitor — ESP32 Firmware v4.0.0
 *
 * Build environments (platformio.ini):
 *   pio run -e electricity   → TE71/TE73 elektr hisoblagich (RS-485 DLMS)
 *   pio run -e water         → 2x suv bosim sensori (analog ADC)
 *   pio run -e gas           → 1x gaz bosim sensori (analog ADC)
 *
 * Birinchi sozlash:
 *   1. "MeterSetup" WiFi AP → 192.168.4.1
 *   2. Server URL: http://67.205.171.93
 *   3. Device Token (backend DEVICE_API_TOKEN)
 *   4. Save → restart → tayyor
 *
 * Arxitektura:
 *   include/common.h              → WiFi, HTTP, NVS, OTA, backend API
 *   include/sensors/electricity.h → TE71/TE73 RS-485 DLMS
 *   include/sensors/water.h       → 2x analog bosim (suv)
 *   include/sensors/gas.h         → 1x analog bosim (gaz)
 */

#define FW_VERSION "4.0.0"

// ─── Umumiy framework ────────────────────────────────────────────────────────
#include "common.h"

// ─── Sensor tanlash (build flag orqali) ──────────────────────────────────────
#ifdef SENSOR_ELECTRICITY
  #include "sensors/electricity.h"
#elif defined(SENSOR_WATER)
  #include "sensors/water.h"
#elif defined(SENSOR_GAS)
  #include "sensors/gas.h"
#else
  #error "Build flag kerak: -DSENSOR_ELECTRICITY | -DSENSOR_WATER | -DSENSOR_GAS"
#endif

// ═══════════════════════════════════════════════════════════════════════════════
// App konstantalar
// ═══════════════════════════════════════════════════════════════════════════════
#define WIFI_AP_NAME     "MeterSetup"
#define WIFI_AP_PASS     "meter1234"
#define READ_INTERVAL_MS  30000UL  // Har 30s da o'qish
#define CMD_POLL_MS       60000UL  // Har 60s da command poll
#define HEALTH_CHECK_MS   60000UL  // Har 60s da server check
#define OFFLINE_BUF_SIZE  50       // Offline buffer hajmi

// ═══════════════════════════════════════════════════════════════════════════════
// App state
// ═══════════════════════════════════════════════════════════════════════════════
static char  device_id[20] = "";
static bool  registered    = false;
static bool  server_ok     = false;

static unsigned long last_read_ms   = 0;
static unsigned long last_cmd_ms    = 0;
static unsigned long last_health_ms = 0;

// Relay faqat elektr sensori uchun
#ifdef SENSOR_ELECTRICITY
static int           pending_relay      = 0;    // 0=yo'q, 1=relay_off, 2=relay_on
static int           meter_fail_count   = 0;    // Ketma-ket muvaffaqiyatsiz urinishlar
static unsigned long meter_retry_ms     = 30000UL; // Joriy retry interval
#define METER_RETRY_MAX_MS  300000UL            // Maksimal interval: 5 daqiqa
#endif

// ═══════════════════════════════════════════════════════════════════════════════
// Offline buffer
// ═══════════════════════════════════════════════════════════════════════════════
static String off_buf[OFFLINE_BUF_SIZE];
static int    off_head  = 0;
static int    off_count = 0;

static void buf_push(const String& json) {
    off_buf[off_head] = json;
    off_head = (off_head + 1) % OFFLINE_BUF_SIZE;
    if (off_count < OFFLINE_BUF_SIZE) off_count++;
    else Serial.println("Buffer to'ldi — eng eski o'qish o'chirildi");
}

static void buf_flush() {
    if (off_count == 0 || !server_ok) return;
    Serial.printf("Buffer: %d ta o'qish yuborilmoqda\n", off_count);
    int start = (off_head - off_count + OFFLINE_BUF_SIZE) % OFFLINE_BUF_SIZE;
    int sent  = 0;
    for (int i = 0; i < off_count; i++) {
        if (!http_post("/api/readings", off_buf[(start + i) % OFFLINE_BUF_SIZE])) break;
        sent++;
        delay(50);
    }
    off_count -= sent;
    if (off_count < 0) off_count = 0;
    if (sent > 0) Serial.printf("Buffer: %d ta yuborildi\n", sent);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Registratsiya
// ═══════════════════════════════════════════════════════════════════════════════
static bool do_register() {
    return sensor_do_register(device_id, FW_VERSION);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Setup
// ═══════════════════════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);
    delay(200);

    // Device ID = WiFi MAC
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(device_id, sizeof(device_id), "%02X%02X%02X%02X%02X%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    Serial.println();
    Serial.println("╔══════════════════════════════════════════╗");
    Serial.println("║       Meter Monitor v" FW_VERSION "            ║");

#ifdef SENSOR_ELECTRICITY
    Serial.println("║       Sensor: Elektr (TE71/TE73)         ║");
#elif defined(SENSOR_WATER)
    Serial.println("║       Sensor: Suv bosimi (2x ADC)        ║");
#elif defined(SENSOR_GAS)
    Serial.println("║       Sensor: Gaz bosimi (1x ADC)        ║");
#endif

    Serial.println("╚══════════════════════════════════════════╝");
    Serial.printf("Qurilma ID : %s\n", device_id);

    // NVS dan config yuklash
    cfg_load();
    Serial.printf("Server     : %s\n", g_cfg.server_url);
    Serial.printf("Token      : %s\n",
        g_cfg.device_token[0] ? "✓ sozlangan" : "✗ YO'Q — WiFiManager da kiriting!");

    // BOOT tugmasi (GPIO0) 3s bosilsa → WiFi reset
    pinMode(0, INPUT_PULLUP);
    if (digitalRead(0) == LOW) {
        delay(3000);
        if (digitalRead(0) == LOW) {
            Serial.println("[BOOT] WiFi sozlamalari o'chirilmoqda...");
            WiFiManager wm;
            wm.resetSettings();
            ESP.restart();
        }
    }

    // WiFi: tez ulanish, keyin WiFiManager
#ifndef DEFAULT_WIFI_SSID
  #define DEFAULT_WIFI_SSID "12"
#endif
#ifndef DEFAULT_WIFI_PASS
  #define DEFAULT_WIFI_PASS "12345678"
#endif
    wifi_quick(DEFAULT_WIFI_SSID, DEFAULT_WIFI_PASS);
    wifi_setup(WIFI_AP_NAME, WIFI_AP_PASS, device_id, g_cfg.meter_serial);

    // Server tekshirish + OTA
    server_ok = server_check();
    if (server_ok) ota_check(device_id, FW_VERSION);

    // ── Sensor sozlash ───────────────────────────────────────────────────────
#ifdef SENSOR_ELECTRICITY
    // RS-485: WiFi radio o'chirib DLMS ulanish
    sensor_init();
    Serial.println("WiFi → pause (RS-485 ulanish)");
    wifi_pause();

    bool meter_found = false;
    for (int attempt = 1; attempt <= 3; attempt++) {
        Serial.printf("  Urinish %d/3...", attempt);
        if (sensor_connect()) {
            Serial.println(" OK");
            dlms_get_string(1, OBIS_SERIAL, 2,
                            g_sensor_meta.meter_serial,
                            sizeof(g_sensor_meta.meter_serial));
            Serial.printf("  Seriya: %s\n", g_sensor_meta.meter_serial);
            sensor_detect_type();
            cfg_save_meter_serial(g_sensor_meta.meter_serial);
            meter_found = true;
            break;
        }
        Serial.println(" XATO");
        delay(500);
    }
    if (!meter_found)
        Serial.println("Diqqat: hisoblagich topilmadi! Offline rejimda davom etiladi.");

    Serial.println("WiFi → resume");
    wifi_resume();

#else
    // Analog sensor (suv/gaz): WiFi o'chirish shart emas
    sensor_init();
#endif

    server_ok = server_check();
    if (server_ok) {
        registered = do_register();
        buf_flush();
    }

    // ── Serial monitor xulosa ───────────────────────────────────────────────
    Serial.println();
    Serial.println("┌──────────────────────────────────────────────┐");
    Serial.printf( "│  Qurilma ID : %-30s│\n", device_id);
#ifdef SENSOR_ELECTRICITY
    Serial.printf( "│  Hisoblagich: %-30s│\n",
        g_sensor_meta.meter_serial[0] ? g_sensor_meta.meter_serial : "topilmadi");
    Serial.printf( "│  Tur        : %-30s│\n",
        g_sensor_meta.sensor_type[0]  ? g_sensor_meta.sensor_type  : "aniqlanmadi");
#endif
    Serial.printf( "│  Server     : %-30s│\n", g_cfg.server_url);
    Serial.println("└──────────────────────────────────────────────┘");
    Serial.println("Tayyor!\n");
}

// ═══════════════════════════════════════════════════════════════════════════════
// Loop
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();

    // WiFi yo'q bo'lsa qayta ulanish
#ifdef SENSOR_ELECTRICITY
    bool meter_time = (now - last_read_ms >= meter_retry_ms || last_read_ms == 0);
#else
    bool meter_time = (now - last_read_ms >= READ_INTERVAL_MS || last_read_ms == 0);
#endif
    if (!meter_time && WiFi.status() != WL_CONNECTED) {
        WiFi.reconnect();
        delay(1000);
        return;
    }

    // Server health check (har 60s)
    if (!meter_time && now - last_health_ms >= HEALTH_CHECK_MS) {
        last_health_ms = now;
        bool prev = server_ok;
        server_ok = server_check();
        if (server_ok && !prev) {
            Serial.println("Server qaytdi!");
            if (!registered) registered = do_register();
            buf_flush();
            ota_check(device_id, FW_VERSION);
        }
    }

    // ── Sensor o'qish ────────────────────────────────────────────────────────
    if (meter_time) {
        last_read_ms = now;

#ifdef SENSOR_ELECTRICITY
        // RS-485: WiFi radio o'chirish (RF interferensiya oldini olish)
        wifi_pause();

        // DLMS sessiyasi yo'q bo'lsa qayta ulanish
        if (!dlms_connected) {
            Serial.print("Ulanilmoqda...");
            if (!sensor_connect()) {
                Serial.println(" XATO!");
                wifi_resume();
                // Backoff: har muvaffaqiyatsizlikda interval 2x oshadi (max 5 daqiqa)
                meter_fail_count++;
                if (meter_fail_count >= 3) {
                    meter_retry_ms = min(meter_retry_ms * 2, METER_RETRY_MAX_MS);
                    Serial.printf("Keyingi urinish %lu s dan keyin\n", meter_retry_ms / 1000);
                }
                return;
            }
            meter_fail_count = 0;
            meter_retry_ms   = READ_INTERVAL_MS;  // Ulanish bo'lsa intervalni tiklash
            Serial.println(" OK");
            if (!g_sensor_meta.meter_serial[0])
                dlms_get_string(1, OBIS_SERIAL, 2,
                                g_sensor_meta.meter_serial,
                                sizeof(g_sensor_meta.meter_serial));
            if (!g_sensor_meta.sensor_type[0])
                sensor_detect_type();
        }

        // Relay buyrug'ini DLMS session ichida bajarish
        if (pending_relay) {
            bool ok = sensor_relay(pending_relay);
            Serial.printf("Relay %s: %s\n",
                pending_relay == 2 ? "ON" : "OFF", ok ? "OK" : "XATO");
            pending_relay = 0;
        }
#endif

        // Sensor o'qish
        SensorData d;
        bool read_ok = sensor_read(d);

        // WiFi qaytarish / holat
#ifdef SENSOR_ELECTRICITY
        bool wifi_ok = wifi_resume();
#else
        bool wifi_ok = (WiFi.status() == WL_CONNECTED);
        if (!wifi_ok) { WiFi.reconnect(); delay(2000); wifi_ok = (WiFi.status() == WL_CONNECTED); }
#endif

        if (!read_ok) {
            Serial.println("O'qish xato");
#ifdef SENSOR_ELECTRICITY
            dlms_disconnect();
#endif
            last_health_ms = millis();
            return;
        }

        // ── Serverga yuborish ────────────────────────────────────────────────
        String json = sensor_build_json(device_id, FW_VERSION, d);

        if (wifi_ok) {
            server_ok = server_check();
            if (server_ok) {
                if (!registered) registered = do_register();
                buf_flush();
                if (!http_post("/api/readings", json)) {
                    server_ok = false;
                    buf_push(json);
                    Serial.printf("Yuborilmadi → buffer: %d/%d\n", off_count, OFFLINE_BUF_SIZE);
                }
            } else {
                buf_push(json);
                Serial.printf("Server xato → buffer: %d/%d\n", off_count, OFFLINE_BUF_SIZE);
            }
        } else {
            buf_push(json);
            Serial.printf("WiFi yo'q → buffer: %d/%d\n", off_count, OFFLINE_BUF_SIZE);
        }

        last_health_ms = millis();
    }

    // ── Command poll + status + OTA (har 60s) ────────────────────────────────
    if (server_ok && WiFi.status() == WL_CONNECTED &&
        now - last_cmd_ms >= CMD_POLL_MS) {
        last_cmd_ms = now;
#ifdef SENSOR_ELECTRICITY
        app_poll_commands(device_id, &pending_relay);
#else
        app_poll_commands(device_id, nullptr);
#endif
        app_send_status(device_id, FW_VERSION);
        ota_check(device_id, FW_VERSION);
    }
}
