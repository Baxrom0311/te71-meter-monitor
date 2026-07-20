#pragma once
/**
 * soil.h — Kapasitiv tuproq namligi sensori (analog ADC)
 *
 * Sensor: Kapasitiv tuproq namligi sensori (Capacitive Soil Moisture Sensor v1.2/v2.0)
 *   - Chiqish: 0-3.3V analog (quruq = yuqori kuchlanish, nam = past kuchlanish)
 *   - Quvvat: 3.3V yoki 5V
 *
 * Kalibrovka:
 *   ADC_DRY  = havoda (quruq, 0% nam) dagi ADC qiymati  → ~3100-3500
 *   ADC_WET  = suvga botirish (100% nam) dagi ADC qiymati → ~1200-1500
 *   Haqiqiy ishlatilganda ushbu qiymatlarni o'zingizning sensoringizga sozlang.
 *
 * Ulanish:
 *   Sensor VCC  → ESP32 3.3V (yoki 5V, agar sensor 5V qo'llab-quvvatlasa)
 *   Sensor GND  → ESP32 GND
 *   Sensor AOUT → ESP32 GPIO34 (ADC1_CH6 — faqat kirish, WiFi bilan muammosiz)
 *
 * Build:
 *   pio run -e soil
 *   pio run -e soil_debug
 */

#include <Arduino.h>
#include <ArduinoJson.h>

// ─── ADC pin ──────────────────────────────────────────────────────────────────
#define PIN_SOIL_ADC       34    // GPIO34 = ADC1_CH6 (faqat kirish)

// ─── Kalibrovka qiymatlari ────────────────────────────────────────────────────
// Sensoringizga moslashtiring (Serial monitor orqali raw qiymatni ko'ring)
#define SOIL_ADC_DRY      3200  // Havoda (0% nam) → bu raqam kattaroq bo'ladi
#define SOIL_ADC_WET      1400  // Suvda (100% nam) → bu raqam kichikroq bo'ladi
#define SOIL_ADC_SAMPLES    16  // Shovqin kamaytirish uchun o'rtacha namunalar

// ─── SensorData (tuproq namligi) ──────────────────────────────────────────────
struct SensorData {
    float humidity;   // Tuproq namligi: 0.0 – 100.0 %
    bool  valid;
};

// ─── Sensor API ───────────────────────────────────────────────────────────────
static void sensor_init() {
    analogReadResolution(12);        // 12-bit: 0–4095
    analogSetAttenuation(ADC_11db);  // 0–3.3V diapazon
    pinMode(PIN_SOIL_ADC, INPUT);

    // Birinchi warming-up o'qish (ADC stabilizatsiya uchun)
    for (int i = 0; i < 5; i++) {
        analogRead(PIN_SOIL_ADC);
        delay(10);
    }

    LOG_PRINTF("Tuproq namligi sensori tayyor (GPIO%d)\n", PIN_SOIL_ADC);
    LOG_PRINTF("  Kalibrovka: quruq=%d, nam=%d\n", SOIL_ADC_DRY, SOIL_ADC_WET);
}

static bool sensor_connect() {
    return true;  // Analog sensor — har doim ulangan
}

static bool sensor_read(SensorData& d) {
    if (g_cfg.test_mode) {
        // Simulyatsiya: 30–70% orasida tasodifiy o'zgarish
        static float sim_hum = 55.0f;
        sim_hum += (random(-10, 11)) * 0.5f;
        if (sim_hum < 10.0f) sim_hum = 10.0f;
        if (sim_hum > 90.0f) sim_hum = 90.0f;
        d.humidity = sim_hum;
        d.valid    = true;
        LOG_PRINTF("[TEST MODE] Tuproq namligi: %.1f%%\n", d.humidity);
        return true;
    }

    // O'rtacha ADC o'qish
    long sum = 0;
    for (int i = 0; i < SOIL_ADC_SAMPLES; i++) {
        sum += analogRead(PIN_SOIL_ADC);
        delayMicroseconds(500);
    }
    int raw = (int)(sum / SOIL_ADC_SAMPLES);

    // ADC → namlik foiziga o'tkazish (teskari: quruq = yuqori ADC)
    float pct = (float)(SOIL_ADC_DRY - raw) / (float)(SOIL_ADC_DRY - SOIL_ADC_WET) * 100.0f;
    if (pct < 0.0f)   pct = 0.0f;
    if (pct > 100.0f) pct = 100.0f;

    d.humidity = pct;
    d.valid    = true;

    LOG_PRINTF("Tuproq: raw=%d → namlik=%.1f%%\n", raw, d.humidity);
    return true;
}

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
