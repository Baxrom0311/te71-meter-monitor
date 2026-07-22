#pragma once
/**
 * sound.h — Ovoz darajasi sensori (mikrofon ADC)
 *
 * Barcha parametrlar platformio.ini [build_flags] orqali o'zgartiriladi:
 *
 *   -DPIN_SOUND_ADC=34      → Mikrofon AOUT ulangan GPIO (standart: 34)
 *   -DSOUND_SAMPLES=300     → Amplituda hisoblash uchun namunalar soni
 *   -DSOUND_CALIB_MS=5000   → Startup kalibrovka vaqti (ms)
 *   -DSOUND_FIGHT_REF=200   → "100%" ga mos amplituda (standart: 200)
 *
 * Ulanish:
 *   MAX9814 / KY-038 / KY-037:
 *     VCC  → 3.3V
 *     GND  → GND
 *     AOUT → GPIO[PIN_SOUND_ADC]
 *
 * Display: disp_sound.h (main.cpp tomonidan yuklanadi — sensor bu haqda bilmaydi)
 */

#include <Arduino.h>
#include <ArduinoJson.h>

// ─── ADC pin va parametrlar ───────────────────────────────────────────────────
#ifndef PIN_SOUND_ADC
  #define PIN_SOUND_ADC   34
#endif
#ifndef SOUND_SAMPLES
  #define SOUND_SAMPLES   300
#endif
#ifndef SOUND_CALIB_MS
  #define SOUND_CALIB_MS  5000
#endif
#ifndef SOUND_FIGHT_REF
  #define SOUND_FIGHT_REF 200   // Bu amplituda → ~100% level
#endif

// ─── SensorData ───────────────────────────────────────────────────────────────
struct SensorData {
    float level;  // 0.0 – 100.0 %
    bool  valid;
};

// ─── Ichki holat ──────────────────────────────────────────────────────────────
static float s_noise_floor    = 0.0f;  // Kalibrovkada o'lchangan fon shovqin
static int   s_talk_thr       = 25;    // Oddiy gap chegarasi
static int   s_loud_thr       = 90;    // Baland gap chegarasi
static int   s_fight_thr      = 160;   // Janjal chegarasi
static int   s_fight_ref      = SOUND_FIGHT_REF;  // "100%" mos amplituda

// ─── Amplituda o'qish (max–min, SOUND_SAMPLES namuna) ────────────────────────
static int _sound_amplitude() {
    int lo = 4095, hi = 0;
    for (int i = 0; i < SOUND_SAMPLES; i++) {
        int v = analogRead(PIN_SOUND_ADC);
        if (v < lo) lo = v;
        if (v > hi) hi = v;
        delayMicroseconds(150);
    }
    return hi - lo;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sensor API  (main.cpp dan chaqiriladi)
// ═══════════════════════════════════════════════════════════════════════════════

static void sensor_init() {
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    pinMode(PIN_SOUND_ADC, INPUT);

    // Isitish (warming-up) o'qishlari
    for (int i = 0; i < 5; i++) { analogRead(PIN_SOUND_ADC); delay(10); }

    LOG_PRINTF("Ovoz sensori tayyor (GPIO%d)\n", PIN_SOUND_ADC);
    LOG_PRINTF("  Kalibrovka: %d ms jimlik...\n", SOUND_CALIB_MS);

    // Fon shovqin kalibrovkasi — SOUND_CALIB_MS davomida o'rtacha amplituda
    long total = 0; int count = 0;
    unsigned long t0 = millis();
    while (millis() - t0 < (unsigned long)SOUND_CALIB_MS) {
        total += _sound_amplitude();
        count++;
        delay(30);
    }
    s_noise_floor = (count > 0) ? (float)total / count : 0.0f;

    // Chegaralar — fon shovqinga moslashtiriladi
    s_talk_thr  = (int)(s_noise_floor * 0.7f + 25);
    s_loud_thr  = (int)(s_noise_floor * 1.5f + 80);
    s_fight_thr = (int)(s_noise_floor * 2.0f + 150);
    s_fight_ref = max(s_fight_thr + 40, SOUND_FIGHT_REF);

    LOG_PRINTF("  Fon shovqin  : %.0f\n", s_noise_floor);
    LOG_PRINTF("  Chegaralar   : talk=%d  loud=%d  fight=%d\n",
               s_talk_thr, s_loud_thr, s_fight_thr);
}

static bool sensor_connect() { return true; }

static bool sensor_read(SensorData& d) {
    if (g_cfg.test_mode) {
        static float sim = 25.0f;
        sim += (random(-20, 21)) * 0.5f;
        sim = constrain(sim, 0.0f, 95.0f);
        d = {sim, true};
        LOG_PRINTF("[TEST] Ovoz: %.1f%%\n", d.level);
        return true;
    }

    // 5 ta burst → eng yuqori amplitudani olish (qisqa shovqin hodisalarini ushlab qolish)
    int peak = 0;
    for (int b = 0; b < 5; b++) {
        int amp = _sound_amplitude();
        if (amp > peak) peak = amp;
        delay(25);
    }

    // Fon shovqinni ayirish
    float real = max(0.0f, (float)peak - s_noise_floor);

    // 0–100% ga aylantirish
    float level = constrain(real / (float)s_fight_ref * 100.0f, 0.0f, 100.0f);

    // Holat matni (log uchun)
    const char* status =
        (real < s_talk_thr)  ? "Jim/Fon" :
        (real < s_loud_thr)  ? "Oddiy gap" :
        (real < s_fight_thr) ? "Baland gap" : "JANJAL";

    LOG_PRINTF("Ovoz: peak=%d  real=%.0f → %.1f%%  [%s]\n",
               peak, real, level, status);

    d = {level, true};
    return true;
}

void sensor_set_volume(float) {}  // stub (common.h extern talab qiladi)

static bool sensor_do_register(const char* device_id, const char* fw_version) {
    return app_register(device_id, "sound", "microphone", "", fw_version, 0);
}

static String sensor_build_json(const char* device_id,
                                 const char* fw_ver,
                                 const SensorData& d) {
    StaticJsonDocument<256> doc;
    doc["device_id"]    = device_id;
    doc["utility_type"] = "sound";
    doc["sensor_type"]  = "microphone";
    doc["fw_version"]   = fw_ver;
    if (g_cfg.test_mode) doc["is_test_device"] = true;
    if (d.valid) doc["level"] = serialized(String(d.level, 1));
    String out;
    serializeJson(doc, out);
    return out;
}
