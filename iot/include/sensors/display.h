#pragma once
/**
 * display.h — Meter Monitor OLED ekran qurilmasi
 *
 * Hardware: SSD1306 OLED 128x64, I2C (SDA=GPIO21, SCL=GPIO22)
 *
 * Funksiya:
 *   - WiFiManager orqali WiFi ga ulanadi (soil/water/gas bilan bir xil)
 *   - Har 30s da backenddan /api/public/display/kpi ni o'qiydi
 *   - Ekranda elektr/suv/gaz/tuproq ko'rsatkichlarini ko'rsatadi
 *   - Readings yuborilmaydi, LoRa yo'q — faqat WiFi
 *
 * Build:
 *   pio run -e display
 *   pio run -e display_debug
 *
 * Ulanish:
 *   SSD1306 VCC  → 3.3V
 *   SSD1306 GND  → GND
 *   SSD1306 SDA  → GPIO21
 *   SSD1306 SCL  → GPIO22
 *   SSD1306 ADDR → 0x3C (odatda)
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>

// ─── OLED sozlamalari ─────────────────────────────────────────────────────────
#define OLED_WIDTH      128
#define OLED_HEIGHT      64
#define OLED_RESET       -1
#define OLED_I2C_ADDR  0x3C   // Ko'pchilik SSD1306 modullari; agar ishlamasa 0x3D

// ─── App sozlamalari ──────────────────────────────────────────────────────────
#define WIFI_AP_NAME   "DisplaySetup"
#define WIFI_AP_PASS   "meter1234"
#define REFRESH_MS     30000UL   // Har 30s da backend dan yangilash
#define CMD_POLL_MS    300000UL  // Har 5 daqiqada OTA tekshiruv

static Adafruit_SSD1306 g_oled(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET);
static bool g_oled_ok = false;

// ─── Ko'rsatiladigan ma'lumotlar ──────────────────────────────────────────────
struct KpiData {
    float power_w;
    float energy_kwh;
    float pressure_bottom;
    float pressure_top;
    float flow_water;
    float gas_pressure;
    float gas_flow;
    float soil_humidity;
    bool  elec_ok;
    bool  water_ok;
    bool  gas_ok;
    bool  soil_ok;
};

static KpiData g_kpi = {};

// ─── OLED yordamchi funksiyalar ───────────────────────────────────────────────
static void oled_clear_show() {
    if (!g_oled_ok) return;
    g_oled.clearDisplay();
}

static void oled_commit() {
    if (!g_oled_ok) return;
    g_oled.display();
}

// ─── Splash ekran (WiFi ulanish jarayonida) ───────────────────────────────────
static void oled_splash() {
    if (!g_oled_ok) return;
    g_oled.clearDisplay();
    g_oled.setTextSize(1);
    g_oled.setTextColor(SSD1306_WHITE);
    g_oled.setCursor(4, 4);
    g_oled.println("METER MONITOR v" FW_VERSION);
    g_oled.drawLine(0, 14, 127, 14, SSD1306_WHITE);
    g_oled.setCursor(10, 20);
    g_oled.println("WiFi ga ulanmoqda...");
    g_oled.setCursor(10, 34);
    g_oled.print("AP: ");
    g_oled.println(WIFI_AP_NAME);
    g_oled.setCursor(10, 46);
    g_oled.print("Parol: ");
    g_oled.println(WIFI_AP_PASS);
    g_oled.display();
}

// ─── Asosiy ko'rsatish ekrani ──────────────────────────────────────────────────
static void oled_show_kpi(bool wifi_ok) {
    if (!g_oled_ok) return;
    g_oled.clearDisplay();
    g_oled.setTextSize(1);
    g_oled.setTextColor(SSD1306_WHITE);

    // --- Sarlavha ---
    g_oled.setCursor(0, 0);
    g_oled.print("METER MONITOR");
    g_oled.setCursor(84, 0);
    g_oled.print(wifi_ok ? " [WiFi]" : " [Uziq]");
    g_oled.drawLine(0, 9, 127, 9, SSD1306_WHITE);

    // --- Elektr ---
    g_oled.setCursor(0, 12);
    g_oled.print("E:");
    if (g_kpi.elec_ok) {
        char buf[24];
        snprintf(buf, sizeof(buf), "%4.0fW %5.1fkWh", g_kpi.power_w, g_kpi.energy_kwh);
        g_oled.print(buf);
    } else {
        g_oled.print(" -- ");
    }

    // --- Suv ---
    g_oled.setCursor(0, 23);
    g_oled.print("S:");
    if (g_kpi.water_ok) {
        char buf[24];
        snprintf(buf, sizeof(buf), "%.2f/%.2f bar", g_kpi.pressure_bottom, g_kpi.pressure_top);
        g_oled.print(buf);
    } else {
        g_oled.print(" -- ");
    }

    // --- Gaz ---
    g_oled.setCursor(0, 34);
    g_oled.print("G:");
    if (g_kpi.gas_ok) {
        char buf[24];
        snprintf(buf, sizeof(buf), "%.3f bar", g_kpi.gas_pressure);
        g_oled.print(buf);
    } else {
        g_oled.print(" -- ");
    }

    // --- Tuproq namligi ---
    g_oled.setCursor(0, 45);
    g_oled.print("T:");
    if (g_kpi.soil_ok) {
        char buf[20];
        snprintf(buf, sizeof(buf), "%.1f%% namlik", g_kpi.soil_humidity);
        g_oled.print(buf);
    } else {
        g_oled.print(" -- ");
    }

    // --- Pastki chiziq: IP / Offline ---
    g_oled.drawLine(0, 55, 127, 55, SSD1306_WHITE);
    g_oled.setCursor(0, 57);
    if (wifi_ok) {
        g_oled.print(WiFi.localIP().toString());
    } else {
        g_oled.print("WiFi yo'q — qayta ulanmoqda");
    }

    g_oled.display();
}

// ─── Backend dan KPI olish ────────────────────────────────────────────────────
static bool fetch_kpi() {
    if (WiFi.status() != WL_CONNECTED) return false;

    String resp = http_get("/api/public/display/kpi");
    if (resp.isEmpty()) {
        LOG_PRINTLN("KPI: javob kelmadi");
        return false;
    }

    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, resp);
    if (err) {
        LOG_PRINTF("KPI JSON xato: %s\n", err.c_str());
        return false;
    }

    // Elektr
    JsonObject elec = doc["electricity"];
    float pw = elec["power_w"]    | -1.0f;
    float en = elec["energy_kwh"] | -1.0f;
    if (pw >= 0 || en >= 0) {
        g_kpi.power_w    = pw >= 0 ? pw : 0;
        g_kpi.energy_kwh = en >= 0 ? en : 0;
        g_kpi.elec_ok    = true;
    }

    // Suv
    JsonObject water = doc["water"];
    float pb = water["pressure_bottom_bar"] | -1.0f;
    float pt = water["pressure_top_bar"]    | -1.0f;
    if (pb >= 0 || pt >= 0) {
        g_kpi.pressure_bottom = pb >= 0 ? pb : 0;
        g_kpi.pressure_top    = pt >= 0 ? pt : 0;
        g_kpi.water_ok        = true;
    }

    // Gaz
    JsonObject gas = doc["gas"];
    float gp = gas["pressure_bar"] | -1.0f;
    if (gp >= 0) {
        g_kpi.gas_pressure = gp;
        g_kpi.gas_ok       = true;
    }

    // Tuproq namligi
    JsonObject soil = doc["soil"];
    float sh = soil["humidity"] | -1.0f;
    if (sh >= 0) {
        g_kpi.soil_humidity = sh;
        g_kpi.soil_ok       = true;
    }

    LOG_PRINTF("KPI: E=%.0fW, S=%.2f/%.2fbar, G=%.3fbar, T=%.1f%%\n",
               g_kpi.power_w, g_kpi.pressure_bottom, g_kpi.pressure_top,
               g_kpi.gas_pressure, g_kpi.soil_humidity);
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Setup & Loop (main.cpp dan chaqiriladi)
// ─────────────────────────────────────────────────────────────────────────────
static char _disp_id[20]         = "";
static unsigned long _last_ref   = 0;
static unsigned long _last_ota   = 0;

void setup() {
#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
    Serial.begin(115200);
    delay(200);
#endif

    // OLED ishga tushirish
    Wire.begin(21, 22);  // SDA=GPIO21, SCL=GPIO22
    g_oled_ok = g_oled.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR);
    if (!g_oled_ok) {
        LOG_PRINTLN("OLED topilmadi! SDA=21 SCL=22 tekshiring.");
    } else {
        g_oled.clearDisplay();
        g_oled.display();
    }

    // Device ID = WiFi MAC
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(_disp_id, sizeof(_disp_id), "%02X%02X%02X%02X%02X%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    LOG_PRINTLN("╔══════════════════════════════════════════╗");
    LOG_PRINTLN("║       Meter Monitor v" FW_VERSION "            ║");
    LOG_PRINTLN("║       Qurilma: OLED ekran (SSD1306)      ║");
    LOG_PRINTLN("╚══════════════════════════════════════════╝");
    LOG_PRINTF("Qurilma ID : %s\n", _disp_id);

    // Splash
    oled_splash();

    // NVS config yuklash
    cfg_load();
    LOG_PRINTF("Server: %s\n", g_cfg.server_url);

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

    // WiFi ulanish (soil/water/gas bilan bir xil)
#ifndef DEFAULT_WIFI_SSID
  #define DEFAULT_WIFI_SSID "12"
#endif
#ifndef DEFAULT_WIFI_PASS
  #define DEFAULT_WIFI_PASS "12345678"
#endif
    wifi_quick(DEFAULT_WIFI_SSID, DEFAULT_WIFI_PASS);
    wifi_setup(WIFI_AP_NAME, WIFI_AP_PASS, _disp_id, "");

    bool wifi_ok = (WiFi.status() == WL_CONNECTED);

    // Birinchi ma'lumot olish
    if (wifi_ok) {
        fetch_kpi();
        _last_ota = millis();
        ota_check(_disp_id, FW_VERSION);
    }

    oled_show_kpi(wifi_ok);
    _last_ref = millis();

    LOG_PRINTLN("Tayyor!\n");
}

void loop() {
    unsigned long now = millis();

    bool wifi_ok = (WiFi.status() == WL_CONNECTED);

    // WiFi yo'q — qayta ulanishga urinish
    if (!wifi_ok) {
        WiFi.reconnect();
        delay(2000);
        oled_show_kpi(false);
        return;
    }

    // Har 30s da KPI yangilash
    if (now - _last_ref >= REFRESH_MS || _last_ref == 0) {
        _last_ref = now;
        fetch_kpi();
        oled_show_kpi(true);
    }

    // Har 5 daqiqada OTA tekshiruv
    if (now - _last_ota >= CMD_POLL_MS) {
        _last_ota = now;
        ota_check(_disp_id, FW_VERSION);
    }

    delay(500);
}
