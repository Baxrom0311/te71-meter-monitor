/**
 * Meter Monitor — ESP32 Firmware v4.0.0
 *
 * Build environments (platformio.ini):
 *   pio run -e electricity    → TE71/TE73 elektr hisoblagich (RS-485 DLMS)
 *   pio run -e water          → 2x suv bosim sensori (analog ADC)
 *   pio run -e gas            → 1x gaz bosim sensori (analog ADC)
 *   pio run -e soil           → Yerto'la namligi sensori (kapasitiv ADC, WiFi)
 *   pio run -e sound          → Ovoz darajasi sensori (mikrofon ADC, WiFi)
 *   pio run -e ads1115_test   → ADS1115 + HY-131 4-20mA test
 *
 * Arxitektura:
 *   include/common.h              → WiFi, HTTP, NVS, OTA, backend API
 *   include/sensors/electricity.h → TE71/TE73 RS-485 DLMS
 *   include/sensors/water.h       → 2x analog bosim (suv)
 *   include/sensors/gas.h         → 1x analog bosim (gaz)
 *   include/sensors/soil.h        → Yerto'la namligi (kapasitiv, WiFi)
 *   include/sensors/sound.h       → Ovoz darajasi (mikrofon ADC, WiFi)
 */

#define FW_VERSION "4.0.0"

// ═══════════════════════════════════════════════════════════════════════════════
// ADS1115 TEST MODE — pio run -e ads1115_test
// HY-131 (4-20mA, 0-0.6MPa) + 100Ω shunt + ADS1115 (I2C 16-bit)
//
// Ulanish sxemasi:
//   24VDC(+) ────────────── HY-131(+/Brown)
//   HY-131(-/Blue) ──┬───── ADS1115 AIN0
//                  100Ω
//                    └───── GND  (= 24VDC(-) = ESP32 GND umumiy)
//
//   ADS1115 VDD  → 3.3V
//   ADS1115 GND  → GND
//   ADS1115 SDA  → GPIO21
//   ADS1115 SCL  → GPIO22
//   ADS1115 ADDR → GND   (I2C addr 0x48)
// ═══════════════════════════════════════════════════════════════════════════════
#ifdef ADS1115_TEST

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_ADS1X15.h>

#define ADS_SDA        21
#define ADS_SCL        22
#define ADS_ADDR       0x48
#define SHUNT_OHM      100.0f   // 100Ω shunt rezistor
#define SENSOR_MA_MIN   4.0f    // 4mA  = 0 MPa
#define SENSOR_MA_MAX  20.0f    // 20mA = 0.6 MPa
#define SENSOR_MPA_MAX  0.6f    // HY-131 range

Adafruit_ADS1115 ads;

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n╔══════════════════════════════════════╗");
    Serial.println(  "║   ADS1115 + HY-131 Pressure Test     ║");
    Serial.println(  "║   4-20mA / 0-0.6MPa / 100Ω shunt    ║");
    Serial.println(  "╚══════════════════════════════════════╝\n");

    Wire.begin(ADS_SDA, ADS_SCL);

    if (!ads.begin(ADS_ADDR)) {
        Serial.println("XATO: ADS1115 topilmadi! Ulanishni tekshiring:");
        Serial.println("  VDD->3.3V  GND->GND  SDA->GPIO21  SCL->GPIO22  ADDR->GND");
        while (true) delay(1000);
    }

    // GAIN_TWO = ±2.048V, 1 bit = 62.5 µV
    // 4mA  × 100Ω = 0.400V (0 MPa)
    // 20mA × 100Ω = 2.000V (0.6 MPa) — ±2.048V ga sig'adi
    ads.setGain(GAIN_TWO);
    ads.setDataRate(RATE_ADS1115_128SPS);

    Serial.println("OK: ADS1115 ulandi! (GAIN=+/-2.048V, 128SPS)");
    Serial.println();
    Serial.printf("%-8s  %-9s  %-9s  %-10s  %-8s\n",
                  "Raw", "V (volt)", "I (mA)", "P (MPa)", "P (bar)");
    Serial.println("--------------------------------------------------");
}

void loop() {
    // 8 ta namuna o'rtachasi — shovqin kamaytirish uchun
    long sum = 0;
    for (int i = 0; i < 8; i++) {
        sum += ads.readADC_SingleEnded(0);
        delay(10);
    }
    int16_t raw = (int16_t)(sum / 8);

    // Voltaj hisoblash (GAIN_TWO: 62.5 µV/bit)
    float voltage = raw * 0.0000625f;

    // Tok: I = V / R  (100Ω = 0.1kΩ)
    float current_mA = voltage / (SHUNT_OHM / 1000.0f);

    // Bosim: linear interpolatsiya 4-20mA → 0-0.6MPa
    float pressure_MPa = 0.0f;
    if (current_mA >= SENSOR_MA_MIN) {
        pressure_MPa = (current_mA - SENSOR_MA_MIN)
                     / (SENSOR_MA_MAX - SENSOR_MA_MIN)
                     * SENSOR_MPA_MAX;
        if (pressure_MPa < 0.0f)          pressure_MPa = 0.0f;
        if (pressure_MPa > SENSOR_MPA_MAX) pressure_MPa = SENSOR_MPA_MAX;
    }
    float pressure_bar = pressure_MPa * 10.0f;

    Serial.printf("%-8d  %-9.4f  %-9.3f  %-10.4f  %-8.3f\n",
                  raw, voltage, current_mA, pressure_MPa, pressure_bar);

    delay(1000);
}

#elif defined(LORA_NODE)
// ═══════════════════════════════════════════════════════════════════════════════
// LORA NODE MODE — RS-485 meter o'qish + LoRa TX (WiFi YO'Q)
// Build: pio run -e electricity_lora_node
// ═══════════════════════════════════════════════════════════════════════════════
#include "lora_node.h"
// setup() va loop() lora_node.h da aniqlanadi

#elif defined(LORA_GATEWAY)
// ═══════════════════════════════════════════════════════════════════════════════
// LORA GATEWAY MODE — LoRa RX + WiFi + Backend
// Build: pio run -e lora_gateway
// ═══════════════════════════════════════════════════════════════════════════════
#include "common.h"
#include "lora_packet.h"
#include "lora_gw.h"
// setup() va loop() lora_gw.h da aniqlanadi

#else
// ═══════════════════════════════════════════════════════════════════════════════
// NORMAL FIRMWARE MODE
// ═══════════════════════════════════════════════════════════════════════════════

// ─── Umumiy framework ────────────────────────────────────────────────────────
#include "common.h"

// ─── Sensor tanlash (build flag orqali) ──────────────────────────────────────
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
  #error "Build flag kerak: -DSENSOR_ELECTRICITY | -DSENSOR_WATER | -DSENSOR_GAS | -DSENSOR_SOIL | -DSENSOR_SOUND"
#endif

// ─── Display moduli ──────────────────────────────────────────────────────────
//  Yangi sensor qo'shganda: display/disp_SENSOR.h yarating va bu yerga qo'shing
#if defined(HAVE_LCD) && defined(SENSOR_SOIL)
  #include "display/disp_soil.h"
#elif defined(HAVE_LCD) && defined(SENSOR_SOUND)
  #include "display/disp_sound.h"
#elif defined(HAVE_LCD) && defined(SENSOR_ELECTRICITY)
  #include "display/disp_elec.h"
#else
  #include "display/disp_none.h"  // HAVE_LCD yo'q yoki sensor uchun display yo'q
#endif

// ═══════════════════════════════════════════════════════════════════════════════
// App konstantalar
// ═══════════════════════════════════════════════════════════════════════════════
#define WIFI_AP_NAME     "Bakhromdev"
#define WIFI_AP_PASS     "998935580311"
#ifndef READ_INTERVAL_MS
  #define READ_INTERVAL_MS  30000UL  // Har 30s da o'qish (sensor env dan override qilish mumkin)
#endif
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

static bool g_lora_ok = false;  // LoRa gateway online holati

// LoRa gateway online holatini serverdan olish
static void lora_check() {
    String resp = http_get("/api/public/lora-status");
    if (resp.isEmpty()) { g_lora_ok = false; return; }
    StaticJsonDocument<64> doc;
    if (deserializeJson(doc, resp)) { g_lora_ok = false; return; }
    g_lora_ok = doc["online"] | false;
}

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
    else LOG_PRINTLN("Buffer to'ldi — eng eski o'qish o'chirildi");
}

static void buf_flush() {
    if (off_count == 0 || !server_ok) return;
    LOG_PRINTF("Buffer: %d ta o'qish yuborilmoqda\n", off_count);
    int start = (off_head - off_count + OFFLINE_BUF_SIZE) % OFFLINE_BUF_SIZE;
    int sent  = 0;
    for (int i = 0; i < off_count; i++) {
        if (!http_post("/api/readings", off_buf[(start + i) % OFFLINE_BUF_SIZE])) break;
        sent++;
        delay(50);
    }
    off_count -= sent;
    if (off_count < 0) off_count = 0;
    if (sent > 0) LOG_PRINTF("Buffer: %d ta yuborildi\n", sent);
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
#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
    Serial.begin(115200);
    delay(200);
#endif

    // Device ID = WiFi MAC
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(device_id, sizeof(device_id), "%02X%02X%02X%02X%02X%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    LOG_PRINTLN();
    LOG_PRINTLN("╔══════════════════════════════════════════╗");
    LOG_PRINTLN("║       Meter Monitor v" FW_VERSION "            ║");

#ifdef SENSOR_ELECTRICITY
    LOG_PRINTLN("║       Sensor: Elektr (TE71/TE73)         ║");
#elif defined(SENSOR_WATER)
    LOG_PRINTLN("║       Sensor: Suv bosimi (2x ADC)        ║");
#elif defined(SENSOR_GAS)
    LOG_PRINTLN("║       Sensor: Gaz bosimi (1x ADC)        ║");
#elif defined(SENSOR_SOIL)
    LOG_PRINTLN("║       Sensor: Tuproq namligi (ADC)       ║");
#elif defined(SENSOR_SOUND)
    LOG_PRINTLN("║       Sensor: Ovoz (mikrofon ADC)        ║");
#endif

    LOG_PRINTLN("╚══════════════════════════════════════════╝");
    LOG_PRINTF("Qurilma ID : %s\n", device_id);

    // NVS dan config yuklash
    cfg_load();
    LOG_PRINTF("Server     : %s\n", g_cfg.server_url);
    LOG_PRINTF("Rejim      : %s\n", g_cfg.test_mode ? "TEST" : "PRODUCTION");
    LOG_PRINTF("Token      : %s\n",
        g_cfg.device_token[0] ? "✓ sozlangan" : "✗ YO'Q — WiFiManager da kiriting!");

    // BOOT tugmasi (GPIO0) 3s bosilsa → WiFi reset
    pinMode(0, INPUT_PULLUP);
    if (digitalRead(0) == LOW) {
        delay(3000);
        if (digitalRead(0) == LOW) {
            LOG_PRINTLN("[BOOT] WiFi sozlamalari o'chirilmoqda...");
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
    // sensor_init() LCD init ham qiladi va WiFi holatini ko'rsatadi
    sensor_init();
    LOG_PRINTLN("WiFi → pause (RS-485 ulanish)");
    wifi_pause();

    bool meter_found = false;
    for (int attempt = 1; attempt <= 3; attempt++) {
        LOG_PRINTF("  Urinish %d/3...", attempt);
        if (sensor_connect()) {
            LOG_PRINTLN(" OK");
            dlms_get_string(1, OBIS_SERIAL, 2,
                            g_sensor_meta.meter_serial,
                            sizeof(g_sensor_meta.meter_serial));
            LOG_PRINTF("  Seriya: %s\n", g_sensor_meta.meter_serial);
            sensor_detect_type();
            cfg_save_meter_serial(g_sensor_meta.meter_serial);
            meter_found = true;
            break;
        }
        LOG_PRINTLN(" XATO");
        delay(500);
    }
    if (!meter_found)
        LOG_PRINTLN("Diqqat: hisoblagich topilmadi! Offline rejimda davom etiladi.");

    LOG_PRINTLN("WiFi → resume");
    wifi_resume();

#else
    // Analog sensor (suv/gaz/soil/sound): WiFi o'chirish shart emas
    // disp_init() birinchi — LCD kalibrovka/boshlash vaqtida ko'rinishi uchun
    disp_init();
    sensor_init();
#endif

    server_ok = server_check();
    if (server_ok) {
        registered = do_register();
        buf_flush();
    }
#ifdef SENSOR_ELECTRICITY
    // Display 2-qator: WiFi + server + LoRa holati
    if (server_ok) lora_check();
    disp_show_status(WiFi.status() == WL_CONNECTED, server_ok, g_lora_ok);
#endif

    // ── Serial monitor xulosa ───────────────────────────────────────────────
    LOG_PRINTLN();
    LOG_PRINTLN("┌──────────────────────────────────────────────┐");
    LOG_PRINTF( "│  Qurilma ID : %-30s│\n", device_id);
#ifdef SENSOR_ELECTRICITY
    LOG_PRINTF( "│  Hisoblagich: %-30s│\n",
        g_sensor_meta.meter_serial[0] ? g_sensor_meta.meter_serial : "topilmadi");
    LOG_PRINTF( "│  Tur        : %-30s│\n",
        g_sensor_meta.sensor_type[0]  ? g_sensor_meta.sensor_type  : "aniqlanmadi");
#endif
    LOG_PRINTF( "│  Server     : %-30s│\n", g_cfg.server_url);
    LOG_PRINTF( "│  Rejim      : %-30s│\n", g_cfg.test_mode ? "TEST" : "PRODUCTION");
    LOG_PRINTLN("└──────────────────────────────────────────────┘");
    LOG_PRINTLN("Tayyor!\n");
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
            LOG_PRINTLN("Server qaytdi!");
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
            LOG_PRINT("Ulanilmoqda...");
            if (!sensor_connect()) {
                LOG_PRINTLN(" XATO!");
                wifi_resume();
                meter_fail_count++;
                if (meter_fail_count >= 3) {
                    meter_retry_ms = min(meter_retry_ms * 2, METER_RETRY_MAX_MS);
                    LOG_PRINTF("Keyingi urinish %lu s dan keyin\n", meter_retry_ms / 1000);
                }
                return;
            }
            meter_fail_count = 0;
            meter_retry_ms   = READ_INTERVAL_MS;
            LOG_PRINTLN(" OK");
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
            LOG_PRINTF("Relay %s: %s\n",
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
            LOG_PRINTLN("O'qish xato");
#ifdef SENSOR_ELECTRICITY
            dlms_disconnect();
#endif
            last_health_ms = millis();
            return;
        }

        disp_show_reading(d);

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
                    LOG_PRINTF("Yuborilmadi → buffer: %d/%d\n", off_count, OFFLINE_BUF_SIZE);
                }
            } else {
                buf_push(json);
                LOG_PRINTF("Server xato → buffer: %d/%d\n", off_count, OFFLINE_BUF_SIZE);
            }
        } else {
            buf_push(json);
            LOG_PRINTF("WiFi yo'q → buffer: %d/%d\n", off_count, OFFLINE_BUF_SIZE);
        }

#ifdef SENSOR_ELECTRICITY
        if (server_ok) lora_check();
        disp_show_status(wifi_ok, server_ok, g_lora_ok);
#else
        disp_show_status(wifi_ok, server_ok, false);
#endif

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

#endif // ADS1115_TEST
