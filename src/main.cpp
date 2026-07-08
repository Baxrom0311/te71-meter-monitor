/**
 * Meter Monitor — ESP32 Firmware v3.4.0
 *
 * Arxitektura:
 *   common.h                   → WiFi, HTTP, NVS, OTA, backend API
 *   sensors/electricity.h      → TE71/TE73 RS-485 DLMS protokol
 *   sensors/water.h            → (kelajak) Suv hisoblagichi
 *
 * Build environments (platformio.ini):
 *   pio run -e electricity     → Elektr hisoblagich (TE71/TE73)
 *   pio run -e water           → Suv hisoblagichi (kelajak)
 *
 * Birinchi sozlash:
 *   1. "MeterSetup" WiFi AP → 192.168.4.1
 *   2. Server URL kiriting: http://67.205.171.93
 *   3. Device Token kiriting (backend DEVICE_API_TOKEN qiymati)
 *   4. Save → ESP32 restart → tayyor
 */

#define FW_VERSION "3.4.0"

// ─── Umumiy framework ────────────────────────────────────────────────────────
#include "common.h"

// ─── Sensor tanlash (build flag orqali) ──────────────────────────────────────
#ifdef SENSOR_ELECTRICITY
  #include "sensors/electricity.h"

#elif defined(SENSOR_WATER)
  // Kelajakda:
  // #include "sensors/water.h"
  #error "SENSOR_WATER hali tayyor emas. sensors/water.h faylini yarating."

#else
  #error "Build flag kerak: -DSENSOR_ELECTRICITY yoki -DSENSOR_WATER"
#endif

// ═══════════════════════════════════════════════════════════════════════════════
// App konstantalar
// ═══════════════════════════════════════════════════════════════════════════════
#define WIFI_AP_NAME      "MeterSetup"
#define WIFI_AP_PASS      "meter1234"
#define READ_INTERVAL_MS  30000UL   // Har 30s da o'qish
#define CMD_POLL_MS       60000UL   // Har 60s da command poll
#define HEALTH_CHECK_MS   60000UL   // Har 60s da server check
#define OFFLINE_BUF_SIZE  50        // Offline buffer hajmi

// ═══════════════════════════════════════════════════════════════════════════════
// App state
// ═══════════════════════════════════════════════════════════════════════════════
static char  device_id[20] = "";
static bool  registered    = false;
static bool  server_ok     = false;
static int   pending_relay = 0;   // 0=yo'q, 1=relay_off, 2=relay_on

static unsigned long last_read_ms   = 0;
static unsigned long last_cmd_ms    = 0;
static unsigned long last_health_ms = 0;

// ═══════════════════════════════════════════════════════════════════════════════
// Offline buffer (JSON stringlar)
// Server o'chiq bo'lganda o'qishlarni vaqtincha saqlash
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
    int sent = 0;
    for (int i = 0; i < off_count; i++) {
        if (!http_post("/api/readings", off_buf[(start + i) % OFFLINE_BUF_SIZE]))
            break;
        sent++;
        delay(50);
    }
    off_count -= sent;
    if (off_count < 0) off_count = 0;
    if (sent > 0) Serial.printf("Buffer: %d ta yuborildi\n", sent);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Registratsiya yordamchi
// ═══════════════════════════════════════════════════════════════════════════════
static bool do_register() {
    return app_register(
        device_id,
        "electricity",               // utility_type
        g_sensor_meta.sensor_type,   // meter_type: "te71" | "te73"
        g_sensor_meta.meter_serial,
        FW_VERSION,
        g_sensor_meta.meter_baud
    );
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
    Serial.println("╔══════════════════════════════════════╗");
    Serial.println("║      Meter Monitor v" FW_VERSION "          ║");
    Serial.println("╚══════════════════════════════════════╝");
    Serial.printf("Qurilma ID : %s\n", device_id);

    // NVS dan config yuklash
    cfg_load();
    Serial.printf("Server     : %s\n", g_cfg.server_url);
    Serial.printf("Token      : %s\n",
        g_cfg.device_token[0] ? "✓ sozlangan" : "✗ YO'Q — WiFiManager da kiriting!");

    // BOOT tugmasi (GPIO0) uzoq bosilsa → WiFi sozlamalarini o'chirish
    pinMode(0, INPUT_PULLUP);
    if (digitalRead(0) == LOW) {
        delay(3000);
        if (digitalRead(0) == LOW) {
            Serial.println("[BOOT] WiFi sozlamalari o'chirilmoqda...");
            WiFiManager wm;
            wm.resetSettings();
            Serial.println("[BOOT] Qayta ishga tushirilmoqda...");
            ESP.restart();
        }
    }

    // WiFi: avval tez ulanish, keyin WiFiManager
    // NVS dagi seriya raqamini WiFiManager sahifasida ko'rsatamiz
    wifi_quick("12", "12345678");
    wifi_setup(WIFI_AP_NAME, WIFI_AP_PASS,
               device_id, g_cfg.meter_serial);

    // Server tekshirish + OTA
    server_ok = server_check();
    if (server_ok) ota_check(device_id, FW_VERSION);

    // ── RS-485 sensor ulanish ──────────────────────────────────────────────
    sensor_init();
    Serial.println("WiFi → pause (RS-485 o'qish)");
    wifi_pause();

    Serial.println("Hisoblagichga ulanilmoqda...");
    bool meter_found = false;
    for (int attempt = 1; attempt <= 3; attempt++) {
        if (sensor_connect()) {
            Serial.printf("  Ulandi! Baud: %d\n", g_sensor_meta.meter_baud);
            // Seriya raqamini o'qish
            dlms_get_string(1, OBIS_SERIAL, 2,
                            g_sensor_meta.meter_serial,
                            sizeof(g_sensor_meta.meter_serial));
            Serial.printf("  Seriya: %s\n", g_sensor_meta.meter_serial);
            // TE71/TE73 auto-detect
            sensor_detect_type();
            meter_found = true;
            // Seriya raqamini NVS ga saqlaymiz (keyingi WiFiManager da ko'rsatish uchun)
            cfg_save_meter_serial(g_sensor_meta.meter_serial);
            break;
        }
        Serial.printf("  Urinish %d/3 — muvaffaqiyatsiz\n", attempt);
        delay(500);
    }
    if (!meter_found) {
        Serial.println("Diqqat: hisoblagich topilmadi! Offline rejimda davom etiladi.");
    }

    // WiFi qayta yoqish
    Serial.println("WiFi → resume");
    wifi_resume();

    server_ok = server_check();
    if (server_ok) {
        registered = do_register();
        buf_flush();
    }

    // ── Foydalanuvchi uchun qo'llanma ────────────────────────────────────────
    Serial.println();
    Serial.println("┌─────────────────────────────────────────────┐");
    Serial.println("│  Dashboard da qurilmangizni topish uchun:   │");
    Serial.printf( "│  Qurilma ID : %-30s│\n", device_id);
    Serial.printf( "│  Hisoblagich: %-30s│\n",
        g_sensor_meta.meter_serial[0] ? g_sensor_meta.meter_serial : "topilmadi");
    Serial.printf( "│  Tur        : %-30s│\n",
        g_sensor_meta.sensor_type[0]  ? g_sensor_meta.sensor_type  : "aniqlanmadi");
    Serial.println("│  Server: http://67.205.171.93               │");
    Serial.println("└─────────────────────────────────────────────┘");

    Serial.println("Tayyor!\n");
}

// ═══════════════════════════════════════════════════════════════════════════════
// Loop
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();
    bool meter_time = (now - last_read_ms >= READ_INTERVAL_MS || last_read_ms == 0);

    // ── Meter o'qish vaqti emas: WiFi saqlab turish ──────────────────────────
    if (!meter_time && WiFi.status() != WL_CONNECTED) {
        WiFi.reconnect();
        delay(1000);
        return;
    }

    // ── Server health check (har 60s, meter o'qishdan tashqarida) ───────────
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

    // ── Har 30s da meter o'qish ──────────────────────────────────────────────
    if (meter_time) {
        last_read_ms = now;

        // WiFi radio o'chirish (RF → RS-485 parity xato qiladi)
        wifi_pause();

        // DLMS ulanish (yo'q bo'lsa)
        if (!dlms_connected) {
            Serial.print("Ulanilmoqda...");
            if (!sensor_connect()) {
                Serial.println(" XATO!");
                wifi_resume();
                return;
            }
            Serial.println(" OK");
            // Serial va type birinchi marta aniqlanmagan bo'lsa
            if (!g_sensor_meta.meter_serial[0])
                dlms_get_string(1, OBIS_SERIAL, 2,
                                g_sensor_meta.meter_serial,
                                sizeof(g_sensor_meta.meter_serial));
            if (!g_sensor_meta.sensor_type[0])
                sensor_detect_type();
        }

        // Relay buyrug'i — DLMS session ichida bajarish
        if (pending_relay) {
            bool ok = sensor_relay(pending_relay);
            Serial.printf("Relay %s: %s\n",
                pending_relay == 2 ? "ON" : "OFF",
                ok ? "OK" : "XATO");
            pending_relay = 0;
        }

        // Ma'lumotlarni o'qish
        SensorData d;
        bool read_ok = sensor_read(d);

        // WiFi qaytarish
        bool wifi_ok = wifi_resume();

        // ── Serial monitor ──────────────────────────────────────────────────
        Serial.println("---");
        if (strcmp(d.sensor_type, "te73") == 0) {
            Serial.printf("V: L1=%.2f  L2=%.2f  L3=%.2f V\n",
                isnan(d.voltage_l1) ? 0 : d.voltage_l1,
                isnan(d.voltage_l2) ? 0 : d.voltage_l2,
                isnan(d.voltage_l3) ? 0 : d.voltage_l3);
            Serial.printf("I: L1=%.3f  L2=%.3f  L3=%.3f A\n",
                isnan(d.current_l1) ? 0 : d.current_l1,
                isnan(d.current_l2) ? 0 : d.current_l2,
                isnan(d.current_l3) ? 0 : d.current_l3);
        } else {
            Serial.printf("V=%.2f V  I=%.3f A\n",
                isnan(d.voltage_l1) ? 0 : d.voltage_l1,
                isnan(d.current_l1) ? 0 : d.current_l1);
        }
        Serial.printf("P=%.0f W  F=%.2f Hz  E=%.3f kWh  PF=%.3f\n",
            isnan(d.power_w)     ? 0 : d.power_w,
            isnan(d.frequency)   ? 0 : d.frequency,
            isnan(d.energy_kwh)  ? 0 : d.energy_kwh,
            isnan(d.pf)          ? 0 : d.pf);

        if (!read_ok) {
            Serial.println("O'qish xato — DLMS qayta ulanadi");
            dlms_disconnect();
            last_health_ms = millis();
            return;
        }

        // ── Serverga yuborish ──────────────────────────────────────────────
        String json = sensor_build_json(device_id, FW_VERSION, d);

        if (wifi_ok) {
            server_ok = server_check();
            if (server_ok) {
                if (!registered) registered = do_register();
                buf_flush();
                if (!http_post("/api/readings", json)) {
                    server_ok = false;
                    buf_push(json);
                    Serial.printf("Yuborilmadi → buffer: %d/%d\n",
                        off_count, OFFLINE_BUF_SIZE);
                }
            } else {
                buf_push(json);
                Serial.printf("Server xato → buffer: %d/%d\n",
                    off_count, OFFLINE_BUF_SIZE);
            }
        } else {
            buf_push(json);
            Serial.printf("WiFi yo'q → buffer: %d/%d\n",
                off_count, OFFLINE_BUF_SIZE);
        }

        last_health_ms = millis();
    }

    // ── Command poll + status (har 60s) ──────────────────────────────────────
    if (server_ok && WiFi.status() == WL_CONNECTED &&
        now - last_cmd_ms >= CMD_POLL_MS) {
        last_cmd_ms = now;
        app_poll_commands(device_id, &pending_relay);
        app_send_status(device_id, FW_VERSION);
    }
}
