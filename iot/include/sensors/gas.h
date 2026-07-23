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
// ─── Pulse sensor setting ───────────────────────────────────────────────────
#define PIN_GAS_PULSE         26     // GPIO26 gas flow pulse input
#define GAS_M3_PER_PULSE       0.01f  // 10 litr per pulse = 0.01 m3 (o'zgartirish mumkin)
#define DEBOUNCE_DELAY_MS     50     // Shovqindan saqlash millisoniyalari

static volatile unsigned long g_gas_pulse_count = 0;
static volatile unsigned long g_last_gas_pulse_ms = 0;
static float g_initial_volume_m3 = 0.0f;
static unsigned long g_last_read_pulses = 0;
static unsigned long g_last_read_time_ms = 0;

static void IRAM_ATTR gas_pulse_isr() {
    unsigned long now = millis();
    if (now - g_last_gas_pulse_ms > DEBOUNCE_DELAY_MS) {
        g_gas_pulse_count++;
        g_last_gas_pulse_ms = now;
    }
}

// ─── SensorData (gaz) ─────────────────────────────────────────────────────────
struct SensorData {
    float pressure_bar;  // Gaz bosimi, bar
    float flow_rate;     // Oqim tezligi, m3/h
    float volume_m3;     // Jami hajm, m3
    float temperature_c; // Harorat, C
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

    // Pulse sensor
    pinMode(PIN_GAS_PULSE, INPUT_PULLUP);
    
    // Preferencesdan yuklash
    Preferences prefs;
    prefs.begin("gas", false);
    g_gas_pulse_count = prefs.getULong("pulses", 0);
    g_initial_volume_m3 = prefs.getFloat("base_vol", 0.0f);
    prefs.end();

    attachInterrupt(digitalPinToInterrupt(PIN_GAS_PULSE), gas_pulse_isr, FALLING);
    g_last_read_pulses = g_gas_pulse_count;
    g_last_read_time_ms = millis();

    analogRead(PIN_PRESSURE_GAS);
    LOG_PRINTLN("Gaz bosim va impuls sensorlari tayyor");
    LOG_PRINTF("  Pin: GPIO%d | Impuls: GPIO%d | Max: %.1f bar\n", PIN_PRESSURE_GAS, PIN_GAS_PULSE, SENSOR_MAX_BAR);
}

static bool sensor_connect() {
    return true;
}

static bool sensor_read(SensorData& d) {
    if (g_cfg.test_mode) {
        d.pressure_bar  = 0.02f + (random(0, 100) / 5000.0f);     // 0.02 - 0.04 bar (low pressure)
        d.flow_rate     = 1.5f + (random(0, 100) / 100.0f);       // 1.5 - 2.5 m3/h
        
        static float sim_volume = 1250.450f;
        sim_volume += (d.flow_rate / 3600.0f) * 30.0f;            // 30 soniyada o'tgan hajm m3 da
        d.volume_m3     = sim_volume;
        d.temperature_c = 22.0f + (random(0, 10) / 10.0f);        // 22.0 - 23.0 C
        d.valid = true;
        
        LOG_PRINTF("[TEST MODE] Gaz: bosim=%.3f bar | oqim=%.3f m3/h | hajm=%.3f m3\n",
                      d.pressure_bar, d.flow_rate, d.volume_m3);
        return true;
    }

    // Real rejimda o'qish
    unsigned long current_pulses = g_gas_pulse_count;
    unsigned long time_now = millis();
    unsigned long time_diff_ms = time_now - g_last_read_time_ms;
    unsigned long pulse_diff = current_pulses - g_last_read_pulses;

    d.pressure_bar  = _adc_to_bar(PIN_PRESSURE_GAS);

    // Oqim tezligi: m3/h
    if (time_diff_ms > 0) {
        float m3 = (float)pulse_diff * GAS_M3_PER_PULSE;
        d.flow_rate = (m3 / (float)time_diff_ms) * 3600000.0f;
    } else {
        d.flow_rate = 0.0f;
    }

    // Jami hajm: m3
    d.volume_m3 = g_initial_volume_m3 + ((float)current_pulses * GAS_M3_PER_PULSE);
    d.temperature_c = NAN;
    d.valid = true;

    g_last_read_pulses = current_pulses;
    g_last_read_time_ms = time_now;

    // Har 10 impulsda yoki 5 daqiqada Preferences-ga saqlaymiz
    static unsigned long last_saved_pulses = 0;
    static unsigned long last_saved_time_ms = 0;
    if (current_pulses - last_saved_pulses >= 10 || (time_now - last_saved_time_ms > 300000UL)) {
        Preferences prefs;
        prefs.begin("gas", false);
        prefs.putULong("pulses", current_pulses);
        prefs.end();
        last_saved_pulses = current_pulses;
        last_saved_time_ms = time_now;
    }

    LOG_PRINTF("Gaz: bosim=%.3f bar | oqim=%.3f m3/h | jami=%.3f m3 (pulses=%lu)\n",
                  d.pressure_bar, d.flow_rate, d.volume_m3, current_pulses);
    return true;
}

#ifndef LORA_NODE
static bool sensor_do_register(const char* device_id, const char* fw_version) {
    const char* s_type = "gas_pulse_flow";
    return app_register(device_id, "gas", s_type, "", fw_version, 0);
}

static String sensor_build_json(const char* device_id,
                                 const char* fw_ver,
                                 const SensorData& d) {
    StaticJsonDocument<256> doc;
    doc["device_id"]    = device_id;
    doc["utility_type"] = "gas";
    doc["sensor_type"]  = "gas_pulse_flow";
    doc["fw_version"]   = fw_ver;
    if (g_cfg.test_mode) doc["is_test_device"] = true;

    if (!isnan(d.pressure_bar))  doc["pressure_bar"] = serialized(String(d.pressure_bar, 3));
    if (!isnan(d.flow_rate))     doc["flow_rate"]    = serialized(String(d.flow_rate, 3));
    if (!isnan(d.volume_m3))     doc["volume_m3"]    = serialized(String(d.volume_m3, 3));
    if (!isnan(d.temperature_c)) doc["temperature_c"] = serialized(String(d.temperature_c, 1));

    String out;
    serializeJson(doc, out);
    return out;
}
#endif  // !LORA_NODE

void sensor_set_volume(float val) {
    Preferences prefs;
    prefs.begin("gas", false);
    prefs.putFloat("base_vol", val);
    prefs.putULong("pulses", 0);
    prefs.end();

    g_gas_pulse_count = 0;
    g_initial_volume_m3 = val;
    g_last_read_pulses = 0;
    LOG_PRINTF("Gaz base hajmi %.3f m3 qilib o'rnatildi\n", val);
}
