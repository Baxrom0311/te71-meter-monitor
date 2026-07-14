#pragma once
/**
 * gas.h — 1x Analog bosim sensori (gaz tizimi)
 *
 * Kirish joyiga 1 ta gaz bosim sensori:
 *   PIN_PRESSURE_GAS — gaz quvuri bosimi
 *
 * Sensor turi: 4-20mA yoki 0-5V analog, 250Ω shunt orqali 0-3.3V
 *   0.5V → 0 bar | 4.5V → SENSOR_MAX_BAR
 *
 * Pinlar (ESP32 ADC1):
 *   GPIO35 = ADC1_CH7 = gaz bosimi (faqat INPUT — output bo'lmaydi)
 *
 * Sensor API (main.cpp dan chaqiriladi):
 *   sensor_init()             — ADC sozlash
 *   sensor_connect() → bool  — har doim true
 *   sensor_read(SensorData&) → bool  — ADC o'qish
 *   sensor_build_json(...)   → String — backend JSON
 *   sensor_do_register(...)  → bool  — backend ro'yxatdan o'tish
 */

#include <Arduino.h>
#include <ArduinoJson.h>

// ─── ADC pin ──────────────────────────────────────────────────────────────────
#define PIN_PRESSURE_GAS   35   // GPIO35 = ADC1_CH7 (faqat input)

// ─── Kalibrovka ───────────────────────────────────────────────────────────────
// Gaz tizimi uchun odatda past bosim: 0.02–0.5 bar (past bosimli uy gazi)
// Yoki 0–5 bar (o'rta bosimli)
// Sensor tipiga qarab o'zgartiring:
#define SENSOR_MAX_BAR      5.0f   // Sensor maksimal bosimi (bar)
#define SENSOR_V_ZERO       0.33f  // 0 bar dagi voltaj (0.5V * 3.3/5)
#define SENSOR_V_FULL       2.97f  // Max bar dagi voltaj (4.5V * 3.3/5)
#define SENSOR_ADC_SAMPLES    16

// ─── SensorData (gaz) ─────────────────────────────────────────────────────────
struct SensorData {
    float pressure_bar;  // Gaz bosimi, bar
    bool  valid;
};

// ─── Yordamchi: ADC → bar ─────────────────────────────────────────────────────
static float _adc_to_bar(int pin) {
    long sum = 0;
    for (int i = 0; i < SENSOR_ADC_SAMPLES; i++) {
        sum += analogRead(pin);
        delayMicroseconds(500);
    }
    float voltage = (sum / (float)SENSOR_ADC_SAMPLES) / 4095.0f * 3.3f;
    float bar = (voltage - SENSOR_V_ZERO) / (SENSOR_V_FULL - SENSOR_V_ZERO) * SENSOR_MAX_BAR;
    return bar < 0.0f ? 0.0f : (bar > SENSOR_MAX_BAR ? SENSOR_MAX_BAR : bar);
}

// ─── Sensor API ───────────────────────────────────────────────────────────────
static void sensor_init() {
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    pinMode(PIN_PRESSURE_GAS, INPUT);
    analogRead(PIN_PRESSURE_GAS);  // isitib olish
    delay(100);
    Serial.println("Gaz bosim sensori tayyor");
    Serial.printf("  Pin: GPIO%d | Max: %.1f bar\n", PIN_PRESSURE_GAS, SENSOR_MAX_BAR);
}

static bool sensor_connect() {
    return true;
}

static bool sensor_read(SensorData& d) {
    d.pressure_bar = _adc_to_bar(PIN_PRESSURE_GAS);
    d.valid = true;
    Serial.printf("Gaz bosimi: %.3f bar\n", d.pressure_bar);
    return true;
}

static bool sensor_do_register(const char* device_id, const char* fw_version) {
    return app_register(device_id, "gas", "gas_pressure", "", fw_version, 0);
}

static String sensor_build_json(const char* device_id,
                                 const char* fw_ver,
                                 const SensorData& d) {
    StaticJsonDocument<192> doc;
    doc["device_id"]    = device_id;
    doc["utility_type"] = "gas";
    doc["sensor_type"]  = "gas_pressure";
    doc["fw_version"]   = fw_ver;
    if (g_cfg.test_mode) doc["is_test_device"] = true;
    doc["pressure_bar"] = serialized(String(d.pressure_bar, 3));
    String out;
    serializeJson(doc, out);
    return out;
}
