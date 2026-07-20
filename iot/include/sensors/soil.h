#pragma once
/**
 * soil.h — Yerto'la namligi sensori + LCD 16x2 I2C ekran
 *
 * Sensor: Kapasitiv tuproq namligi sensori (Capacitive Soil Moisture v1.2/v2.0)
 *   - Chiqish: 0-3.3V analog (quruq = yuqori V, nam = past V)
 *
 * Ekran: LCD 16x2 I2C (0x27 yoki 0x3F)
 *   - 1-qator: namlik foizi
 *   - 2-qator: WiFi / server holati
 *
 * Ulanish:
 *   Sensor VCC  → 3.3V       LCD VCC  → 5V (yoki 3.3V)
 *   Sensor GND  → GND        LCD GND  → GND
 *   Sensor AOUT → GPIO34     LCD SDA  → GPIO21
 *                             LCD SCL  → GPIO22
 *
 * Kalibrovka:
 *   SOIL_ADC_DRY — havoda (0% nam) → ~3100–3500
 *   SOIL_ADC_WET — suvda (100% nam) → ~1200–1500
 *
 * Build:
 *   pio run -e soil
 *   pio run -e soil_debug
 */

#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

// ─── ADC pin ──────────────────────────────────────────────────────────────────
#define PIN_SOIL_ADC       34     // GPIO34 = ADC1_CH6 (faqat kirish)

// ─── Kalibrovka ───────────────────────────────────────────────────────────────
#define SOIL_ADC_DRY      3200   // Havoda (0%) — kattaroq qiymat
#define SOIL_ADC_WET      1400   // Suvda (100%) — kichikroq qiymat
#define SOIL_ADC_SAMPLES    16   // Shovqin kamaytirish uchun o'rtacha

// ─── LCD sozlamalari ──────────────────────────────────────────────────────────
#define LCD_ADDR          0x27   // Ko'pchilik modullarda 0x27; ishlamasa 0x3F
#define LCD_COLS            16
#define LCD_ROWS             2
#define LCD_SDA             21   // GPIO21
#define LCD_SCL             22   // GPIO22

static LiquidCrystal_I2C g_lcd(LCD_ADDR, LCD_COLS, LCD_ROWS);
static bool g_lcd_ok = false;

// ─── SensorData ───────────────────────────────────────────────────────────────
struct SensorData {
    float humidity;  // 0.0 – 100.0 %
    bool  valid;
};

// ─── LCD yordamchi: 16 belgiga to'ldirish ─────────────────────────────────────
static void lcd_print_row(uint8_t row, const char* text) {
    if (!g_lcd_ok) return;
    char buf[LCD_COLS + 1];
    snprintf(buf, sizeof(buf), "%-*s", LCD_COLS, text);
    g_lcd.setCursor(0, row);
    g_lcd.print(buf);
}

// ─── LCD: namlik ko'rsatish ───────────────────────────────────────────────────
static void lcd_show_humidity(float pct, bool valid) {
    if (!g_lcd_ok) return;
    char row0[LCD_COLS + 1];
    if (valid) {
        snprintf(row0, sizeof(row0), "Namlik: %5.1f %%", pct);
    } else {
        snprintf(row0, sizeof(row0), "Namlik:    -- %%");
    }
    lcd_print_row(0, row0);
}

// ─── LCD: holat ko'rsatish (2-qator) ──────────────────────────────────────────
static void lcd_show_status(const char* line2) {
    if (!g_lcd_ok) return;
    lcd_print_row(1, line2);
}

// ─── Sensor API ───────────────────────────────────────────────────────────────
static void sensor_init() {
    // ADC sozlash
    analogReadResolution(12);        // 12-bit: 0–4095
    analogSetAttenuation(ADC_11db);  // 0–3.3V diapazon
    pinMode(PIN_SOIL_ADC, INPUT);

    // Birinchi warming-up o'qish
    for (int i = 0; i < 5; i++) {
        analogRead(PIN_SOIL_ADC);
        delay(10);
    }

    // LCD ishga tushirish
    Wire.begin(LCD_SDA, LCD_SCL);
    g_lcd.init();
    g_lcd.backlight();
    g_lcd_ok = true;

    // Splash ekran
    lcd_print_row(0, "Meter Monitor");
    lcd_print_row(1, "WiFi ulanmoqda..");

    LOG_PRINTF("Yerto'la namligi sensori tayyor (GPIO%d)\n", PIN_SOIL_ADC);
    LOG_PRINTF("  Kalibrovka: quruq=%d, nam=%d\n", SOIL_ADC_DRY, SOIL_ADC_WET);
    LOG_PRINTF("  LCD 16x2 I2C (0x%02X) %s\n", LCD_ADDR, g_lcd_ok ? "OK" : "topilmadi");
}

static bool sensor_connect() {
    return true;  // Analog sensor — har doim ulangan
}

static bool sensor_read(SensorData& d) {
    if (g_cfg.test_mode) {
        static float sim_hum = 55.0f;
        sim_hum += (random(-10, 11)) * 0.5f;
        if (sim_hum < 10.0f) sim_hum = 10.0f;
        if (sim_hum > 90.0f) sim_hum = 90.0f;
        d.humidity = sim_hum;
        d.valid    = true;
        LOG_PRINTF("[TEST] Yerto'la namligi: %.1f%%\n", d.humidity);
        lcd_show_humidity(d.humidity, true);
        return true;
    }

    // O'rtacha ADC o'qish (shovqin kamaytirish)
    long sum = 0;
    for (int i = 0; i < SOIL_ADC_SAMPLES; i++) {
        sum += analogRead(PIN_SOIL_ADC);
        delayMicroseconds(500);
    }
    int raw = (int)(sum / SOIL_ADC_SAMPLES);

    // ADC → namlik % (teskari: quruq = yuqori ADC)
    float pct = (float)(SOIL_ADC_DRY - raw) / (float)(SOIL_ADC_DRY - SOIL_ADC_WET) * 100.0f;
    if (pct < 0.0f)   pct = 0.0f;
    if (pct > 100.0f) pct = 100.0f;

    d.humidity = pct;
    d.valid    = true;

    LOG_PRINTF("Yerto'la: raw=%d → namlik=%.1f%%\n", raw, d.humidity);

    // LCD 1-qatorda namlik ko'rsatish
    lcd_show_humidity(d.humidity, true);

    return true;
}

// Soil sensorida hajm hisobi yo'q — bo'sh stub (common.h extern talab qiladi)
void sensor_set_volume(float) {}

static bool sensor_do_register(const char* device_id, const char* fw_version) {
    return app_register(device_id, "soil", "capacitive_soil_moisture", "", fw_version, 0);
}

static String sensor_build_json(const char* device_id,
                                 const char* fw_ver,
                                 const SensorData& d) {
    StaticJsonDocument<256> doc;
    doc["device_id"]    = device_id;
    doc["utility_type"] = "soil";
    doc["sensor_type"]  = "capacitive_soil_moisture";
    doc["fw_version"]   = fw_ver;
    if (g_cfg.test_mode) doc["is_test_device"] = true;
    if (d.valid) doc["humidity"] = serialized(String(d.humidity, 1));
    String out;
    serializeJson(doc, out);
    return out;
}
