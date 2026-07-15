#pragma once
/**
 * water.h — 2x Analog bosim sensori (suv tizimi)
 *
 * Har bir kirish joyiga 2 ta bosim sensori:
 *   - Pastki (kirish joyi, boiler xona): PIN_PRESSURE_BOTTOM
 *   - Yuqori (oxirgi qavat): PIN_PRESSURE_TOP
 *
 * Sensor turi: 4-20mA yoki 0-5V analog, 250Ω shunt orqali 0-3.3V ga keltirilgan
 *   0.5V → 0 bar (sensor minimum)
 *   4.5V → SENSOR_MAX_BAR (sensor maximum)
 *
 * Pinlar (ESP32 ADC1 — WiFi bilan to'qnashmaydi):
 *   GPIO32 = ADC1_CH4 = pastki bosim
 *   GPIO33 = ADC1_CH5 = yuqori bosim
 *
 * Sensor API (main.cpp dan chaqiriladi):
 *   sensor_init()             — ADC sozlash
 *   sensor_connect() → bool  — har doim true (analog sensor)
 *   sensor_read(SensorData&) → bool  — ADC o'qish
 *   sensor_build_json(...)   → String — backend JSON
 *   sensor_do_register(...)  → bool  — backend ga ro'yxatdan o'tish
 */

#include <Arduino.h>
#include <ArduinoJson.h>

// ─── ADC pinlar (ADC1 — WiFi bilan muammosiz ishlaydi) ───────────────────────
#define PIN_PRESSURE_BOTTOM  32   // GPIO32 = ADC1_CH4
#define PIN_PRESSURE_TOP     33   // GPIO33 = ADC1_CH5

// ─── Kalibrovka ───────────────────────────────────────────────────────────────
// 4-20mA sensor → 250Ω shunt → 1V–5V → voltage divider → 0.66V–3.30V
// Yoki to'g'ridan 0-5V sensor → voltage divider (2:3) → 0-3.3V
// Sozlash uchun ushbu qiymatlarni o'zgartiring:
#define SENSOR_MAX_BAR     10.0f   // Sensor maksimal bosimi (bar)
#define SENSOR_V_ZERO       0.33f  // 0 bar dagi voltaj (V) — 0.5V * 3.3/5 = 0.33V
#define SENSOR_V_FULL       2.97f  // Max bar dagi voltaj (V) — 4.5V * 3.3/5 = 2.97V
#define SENSOR_ADC_SAMPLES    16   // Shovqun kamaytirish uchun o'rtacha namuna soni

// ─── SensorData (suv) ─────────────────────────────────────────────────────────
// ─── Pulse sensor setting ───────────────────────────────────────────────────
#define PIN_WATER_PULSE       25     // GPIO25 water flow pulse input
#define WATER_LITERS_PER_PULSE  10.0f  // 10 litr per pulse (o'zgartirish mumkin)
#define DEBOUNCE_DELAY_MS     50     // Shovqindan saqlash millisoniyalari

static volatile unsigned long g_water_pulse_count = 0;
static volatile unsigned long g_last_water_pulse_ms = 0;
static float g_initial_volume_m3 = 0.0f;
static unsigned long g_last_read_pulses = 0;
static unsigned long g_last_read_time_ms = 0;

static void IRAM_ATTR water_pulse_isr() {
    unsigned long now = millis();
    if (now - g_last_water_pulse_ms > DEBOUNCE_DELAY_MS) {
        g_water_pulse_count++;
        g_last_water_pulse_ms = now;
    }
}

// ─── SensorData (suv) ─────────────────────────────────────────────────────────
struct SensorData {
    float pressure_bottom_bar;  // Kirish joyi (pastki) bosimi, bar
    float pressure_top_bar;     // Yuqori qavat bosimi, bar
    float flow_rate;            // Oqim tezligi, L/min
    float volume_m3;            // Jami hajm, m3
    float temperature_c;        // Harorat, C
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
    analogReadResolution(12);        // 12-bit: 0–4095
    analogSetAttenuation(ADC_11db);  // 0–3.3V diapazon
    pinMode(PIN_PRESSURE_BOTTOM, INPUT);
    pinMode(PIN_PRESSURE_TOP,    INPUT);

    // Pulse sensor
    pinMode(PIN_WATER_PULSE, INPUT_PULLUP);
    
    // Preferencesdan yuklash
    Preferences prefs;
    prefs.begin("water", false);
    g_water_pulse_count = prefs.getULong("pulses", 0);
    g_initial_volume_m3 = prefs.getFloat("base_vol", 0.0f);
    prefs.end();

    attachInterrupt(digitalPinToInterrupt(PIN_WATER_PULSE), water_pulse_isr, FALLING);
    g_last_read_pulses = g_water_pulse_count;
    g_last_read_time_ms = millis();

    // Birinchi ADC o'qish
    analogRead(PIN_PRESSURE_BOTTOM);
    analogRead(PIN_PRESSURE_TOP);
    delay(100);
    Serial.println("Suv bosim va impuls sensorlari tayyor");
    Serial.printf("  Pastki: GPIO%d | Yuqori: GPIO%d | Impuls: GPIO%d\n",
                  PIN_PRESSURE_BOTTOM, PIN_PRESSURE_TOP, PIN_WATER_PULSE);
}

static bool sensor_connect() {
    return true;
}

static bool sensor_read(SensorData& d) {
    if (g_cfg.test_mode) {
        d.pressure_bottom_bar = 3.2f + (random(0, 100) / 200.0f);  // 3.2 - 3.7 bar
        d.pressure_top_bar    = 1.8f + (random(0, 100) / 200.0f);  // 1.8 - 2.3 bar
        d.flow_rate           = 12.5f + (random(0, 100) / 25.0f);  // 12.5 - 16.5 L/min
        
        static float sim_volume = 48.250f;
        sim_volume += (d.flow_rate / 60.0f) * (30.0f / 1000.0f);   // 30 soniyada o'tgan hajm
        d.volume_m3           = sim_volume;
        d.temperature_c       = 18.5f + (random(0, 10) / 10.0f);   // 18.5 - 19.5 C
        d.valid = true;
        
        Serial.printf("[TEST MODE] Suv: pastki=%.3f bar | yuqori=%.3f bar | oqim=%.3f L/min | hajm=%.3f m3\n",
                      d.pressure_bottom_bar, d.pressure_top_bar, d.flow_rate, d.volume_m3);
        return true;
    }

    // Real rejimda o'qish
    unsigned long current_pulses = g_water_pulse_count;
    unsigned long time_now = millis();
    unsigned long time_diff_ms = time_now - g_last_read_time_ms;
    unsigned long pulse_diff = current_pulses - g_last_read_pulses;

    d.pressure_bottom_bar = _adc_to_bar(PIN_PRESSURE_BOTTOM);
    d.pressure_top_bar    = _adc_to_bar(PIN_PRESSURE_TOP);

    // Oqim tezligi: L/min
    if (time_diff_ms > 0) {
        float liters = pulse_diff * WATER_LITERS_PER_PULSE;
        d.flow_rate = (liters / (float)time_diff_ms) * 60000.0f;
    } else {
        d.flow_rate = 0.0f;
    }

    // Jami hajm: m3
    d.volume_m3 = g_initial_volume_m3 + ((float)current_pulses * WATER_LITERS_PER_PULSE / 1000.0f);
    d.temperature_c = NAN; // Ichki analog harorat mavjud emas
    d.valid = true;

    g_last_read_pulses = current_pulses;
    g_last_read_time_ms = time_now;

    // Har 10 impulsda yoki 5 daqiqada Preferences-ga saqlaymiz (flash-ni asrash uchun)
    static unsigned long last_saved_pulses = 0;
    static unsigned long last_saved_time_ms = 0;
    if (current_pulses - last_saved_pulses >= 10 || (time_now - last_saved_time_ms > 300000UL)) {
        Preferences prefs;
        prefs.begin("water", false);
        prefs.putULong("pulses", current_pulses);
        prefs.end();
        last_saved_pulses = current_pulses;
        last_saved_time_ms = time_now;
    }

    Serial.printf("Suv: pastki=%.3f bar | yuqori=%.3f bar | oqim=%.3f L/min | jami=%.3f m3 (pulses=%lu)\n",
                  d.pressure_bottom_bar, d.pressure_top_bar, d.flow_rate, d.volume_m3, current_pulses);
    return true;
}

static bool sensor_do_register(const char* device_id, const char* fw_version) {
    const char* s_type = "water_pulse_flow";
    return app_register(device_id, "water", s_type, "", fw_version, 0);
}

static String sensor_build_json(const char* device_id,
                                 const char* fw_ver,
                                 const SensorData& d) {
    StaticJsonDocument<384> doc;
    doc["device_id"]    = device_id;
    doc["utility_type"] = "water";
    doc["sensor_type"]  = "water_pulse_flow";
    doc["fw_version"]   = fw_ver;
    if (g_cfg.test_mode) doc["is_test_device"] = true;

    if (!isnan(d.pressure_bottom_bar)) doc["pressure_bottom_bar"] = serialized(String(d.pressure_bottom_bar, 3));
    if (!isnan(d.pressure_top_bar))    doc["pressure_top_bar"]    = serialized(String(d.pressure_top_bar, 3));
    if (!isnan(d.flow_rate))           doc["flow_rate"]           = serialized(String(d.flow_rate, 3));
    if (!isnan(d.volume_m3))           doc["volume_m3"]           = serialized(String(d.volume_m3, 3));
    if (!isnan(d.temperature_c))       doc["temperature_c"]       = serialized(String(d.temperature_c, 1));

    String out;
    serializeJson(doc, out);
    return out;
}

void sensor_set_volume(float val) {
    Preferences prefs;
    prefs.begin("water", false);
    prefs.putFloat("base_vol", val);
    prefs.putULong("pulses", 0);
    prefs.end();

    g_water_pulse_count = 0;
    g_initial_volume_m3 = val;
    g_last_read_pulses = 0;
    Serial.printf("Suv base hajmi %.3f m3 qilib o'rnatildi\n", val);
}
