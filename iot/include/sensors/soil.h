#pragma once
/**
 * soil.h — Yerto'la namligi sensori (kapasitiv ADC)
 *
 * Barcha parametrlar platformio.ini [build_flags] orqali o'zgartiriladi:
 *
 *   -DPIN_SOIL_ADC=32      → Sensor AOUT ulangan GPIO (default: 34)
 *   -DSOIL_ADC_DRY=3300    → Havoda o'lchangan quruq qiymat (default: 3300)
 *   -DSOIL_ADC_WET=1400    → Suvda o'lchangan nam qiymat (default: 1400)
 *
 * Ulanish:
 *   Sensor VCC  → 3.3V
 *   Sensor GND  → GND
 *   Sensor AOUT → GPIO[PIN_SOIL_ADC]
 *
 * Display: disp_soil.h (main.cpp tomonidan yuklanadi — sensor bu haqda bilmaydi)
 */

#include <Arduino.h>
#include <ArduinoJson.h>

// ─── ADC pin va kalibrovka (platformio.ini dan override qilish mumkin) ────────
#ifndef PIN_SOIL_ADC
  #define PIN_SOIL_ADC    34      // GPIO34 = ADC1_CH6
#endif
#ifndef SOIL_ADC_DRY
  #define SOIL_ADC_DRY  3300     // Havoda o'lchab belgilang
#endif
#ifndef SOIL_ADC_WET
  #define SOIL_ADC_WET  1400     // Suvda o'lchab belgilang
#endif
#define SOIL_ADC_SAMPLES  16    // Shovqin uchun o'rtacha

// ─── SensorData ───────────────────────────────────────────────────────────────
struct SensorData {
    float humidity;  // 0.0 – 100.0 %
    bool  valid;
};

// ═══════════════════════════════════════════════════════════════════════════════
// Sensor API  (main.cpp dan chaqiriladi)
// ═══════════════════════════════════════════════════════════════════════════════

static void sensor_init() {
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    pinMode(PIN_SOIL_ADC, INPUT);

    // Isitish (warming-up) o'qishlari
    for (int i = 0; i < 5; i++) { analogRead(PIN_SOIL_ADC); delay(10); }

    LOG_PRINTF("Tuproq namligi sensori tayyor (GPIO%d)\n", PIN_SOIL_ADC);
    LOG_PRINTF("  Kalibrovka: quruq=%d, nam=%d\n", SOIL_ADC_DRY, SOIL_ADC_WET);
}

static bool sensor_connect() { return true; }

static bool sensor_read(SensorData& d) {
    if (g_cfg.test_mode) {
        static float sim = 55.0f;
        sim += (random(-10, 11)) * 0.5f;
        sim = constrain(sim, 10.0f, 90.0f);
        d = {sim, true};
        LOG_PRINTF("[TEST] Namlik: %.1f%%\n", d.humidity);
        return true;
    }

    long sum = 0;
    for (int i = 0; i < SOIL_ADC_SAMPLES; i++) {
        sum += analogRead(PIN_SOIL_ADC);
        delayMicroseconds(500);
    }
    int raw = (int)(sum / SOIL_ADC_SAMPLES);

    float pct = (float)(SOIL_ADC_DRY - raw) / (float)(SOIL_ADC_DRY - SOIL_ADC_WET) * 100.0f;
    pct = constrain(pct, 0.0f, 100.0f);

    d = {pct, true};
    LOG_PRINTF("Tuproq: raw=%d → %.1f%%  (quruq=%d, nam=%d)\n",
               raw, pct, SOIL_ADC_DRY, SOIL_ADC_WET);
    return true;
}

void sensor_set_volume(float) {}  // stub (common.h extern talab qiladi)

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
