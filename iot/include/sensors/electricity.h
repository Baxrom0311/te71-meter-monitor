#pragma once
/**
 * sensors/electricity.h — TE71/TE73 RS-485 DLMS sensor
 *
 * API:
 *   sensor_init()                → RS-485 + LCD sozlash
 *   sensor_connect()    → bool   → DLMS ulanish
 *   sensor_read(d)      → bool   → Ma'lumot o'qish
 *   sensor_relay(m)     → bool   → Relay boshqarish
 *   sensor_build_json() → String → JSON yaratish
 *   sensor_do_register()→ bool   → Backend registratsiya
 *
 * DLMS protokol sensors/dlms.h da ajratilgan.
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include "sensors/dlms.h"

// ─── LCD 16x2 konstantalar ───────────────────────────────────────────────────
#define ELEC_LCD_COLS  16
#define ELEC_LCD_ROWS   2
#define ELEC_LCD_SDA   21
#define ELEC_LCD_SCL   22

// ─── LCD drayver (WiFi firmware — o'zi boshqaradi, LoRa node — display modul) ──
#if !defined(LORA_NODE) || defined(HAVE_LCD)
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

static LiquidCrystal_I2C* g_elec_lcd = nullptr;
static bool g_elec_lcd_ok = false;

static void elec_lcd_row(uint8_t row, const char* text) {
    if (!g_elec_lcd_ok || !g_elec_lcd) return;
    char buf[ELEC_LCD_COLS + 1];
    snprintf(buf, sizeof(buf), "%-*s", ELEC_LCD_COLS, text);
    g_elec_lcd->setCursor(0, row);
    g_elec_lcd->print(buf);
}

static void lcd_show_status(const char* line2) {
    elec_lcd_row(1, line2);
}
#else
static void elec_lcd_row(uint8_t, const char*) {}
static void lcd_show_status(const char*) {}
#endif

// ─── OBIS kodlar ──────────────────────────────────────────────────────────────
static const uint8_t OBIS_RELAY[6]   = {0x00,0x00,0x60,0x03,0x0A,0xFF};
static const uint8_t OBIS_SERIAL[6]  = {0x00,0x00,0x60,0x01,0x00,0xFF};
static const uint8_t OBIS_VL1[6]     = {0x01,0x00,0x20,0x07,0x00,0xFF};
static const uint8_t OBIS_VL2[6]     = {0x01,0x00,0x34,0x07,0x00,0xFF};
static const uint8_t OBIS_VL3[6]     = {0x01,0x00,0x48,0x07,0x00,0xFF};
static const uint8_t OBIS_IL1[6]     = {0x01,0x00,0x1F,0x07,0x00,0xFF};
static const uint8_t OBIS_IL2[6]     = {0x01,0x00,0x33,0x07,0x00,0xFF};
static const uint8_t OBIS_IL3[6]     = {0x01,0x00,0x47,0x07,0x00,0xFF};
static const uint8_t OBIS_POWER[6]   = {0x01,0x00,0x0F,0x07,0x00,0xFF};
static const uint8_t OBIS_FREQ[6]    = {0x01,0x00,0x0E,0x07,0x00,0xFF};
static const uint8_t OBIS_PF[6]      = {0x01,0x00,0x0D,0x07,0x00,0xFF};
static const uint8_t OBIS_ENERGY[6]  = {0x01,0x00,0x01,0x08,0x00,0xFF};

// ─── SensorData ───────────────────────────────────────────────────────────────
struct SensorData {
    float voltage_l1, voltage_l2, voltage_l3;
    float current_l1, current_l2, current_l3;
    float power_w;
    float frequency;
    float energy_kwh;
    float pf;
    char  sensor_type[8];
    char  meter_serial[32];
    int   meter_baud;
    bool  valid;
};

static SensorData g_sensor_meta;

// ─── LCD: elektr ko'rsatkichlari ──────────────────────────────────────────────
#ifndef LORA_NODE
static void lcd_show_electricity(const SensorData& d) {
    if (!g_elec_lcd_ok || !d.valid) return;
    char row0[ELEC_LCD_COLS + 1];
    float v = isnan(d.voltage_l1) ? 0.0f : d.voltage_l1;
    float i = isnan(d.current_l1) ? 0.0f : d.current_l1;
    float p = isnan(d.power_w)    ? 0.0f : d.power_w;
    snprintf(row0, sizeof(row0), "%.0fV %.1fA %.0fW", v, i, p);
    elec_lcd_row(0, row0);
}
#else
static void lcd_show_electricity(const SensorData&) {}
#endif

// ═══════════════════════════════════════════════════════════════════════════════
// Sensor API
// ═══════════════════════════════════════════════════════════════════════════════
static void sensor_init() {
    fcs_init_table();
    pinMode(PIN_DE, OUTPUT);
    digitalWrite(PIN_DE, LOW);
    Serial2.begin(9600, SERIAL_8N1, PIN_RX, PIN_TX);
    g_sensor_meta.meter_baud       = 9600;
    g_sensor_meta.meter_serial[0]  = '\0';
    g_sensor_meta.sensor_type[0]   = '\0';

#ifndef LORA_NODE
    Wire.begin(ELEC_LCD_SDA, ELEC_LCD_SCL);
    unsigned long t = millis(); while (millis() - t < 50) yield();
    uint8_t lcd_addr = 0;
    for (uint8_t a : {0x27u, 0x3Fu, 0x20u, 0x38u}) {
        Wire.beginTransmission(a);
        if (Wire.endTransmission() == 0) { lcd_addr = a; break; }
    }
    if (lcd_addr) {
        g_elec_lcd = new LiquidCrystal_I2C(lcd_addr, ELEC_LCD_COLS, ELEC_LCD_ROWS);
        g_elec_lcd->init();
        g_elec_lcd->backlight();
        g_elec_lcd->clear();
        g_elec_lcd_ok = true;
        elec_lcd_row(0, "Meter Monitor");
        elec_lcd_row(1, "Yuklanmoqda...");
    }
#endif
}

static bool sensor_try_baud(uint32_t baud) {
    Serial2.end();
    unsigned long t = millis(); while (millis() - t < 50) yield();
    Serial2.begin(baud, SERIAL_8N1, PIN_RX, PIN_TX);
    t = millis(); while (millis() - t < 100) yield();
    if (dlms_connect_reader()) return true;
    dlms_disconnect();
    t = millis(); while (millis() - t < 300) yield();
    if (dlms_connect_public()) return true;
    return false;
}

static bool sensor_connect() {
    if (sensor_try_baud(9600)) { g_sensor_meta.meter_baud = 9600; return true; }
    dlms_disconnect();
    if (sensor_try_baud(4800)) { g_sensor_meta.meter_baud = 4800; return true; }
    dlms_disconnect();

    if (g_cfg.test_mode) {
        dlms_connected = true;
        dlms_simulated = true;
        g_sensor_meta.meter_baud = 9600;
        if (!g_sensor_meta.meter_serial[0])
            strncpy(g_sensor_meta.meter_serial, "202032000525", sizeof(g_sensor_meta.meter_serial));
        strncpy(g_sensor_meta.sensor_type, "te71", sizeof(g_sensor_meta.sensor_type));
        return true;
    }
    return false;
}

static void sensor_detect_type() {
    float vl2 = NAN;
    dlms_get_scaled(OBIS_VL2, &vl2);
    bool is_te73 = !isnan(vl2) && vl2 > 10.0f;
    strncpy(g_sensor_meta.sensor_type, is_te73 ? "te73" : "te71",
            sizeof(g_sensor_meta.sensor_type));
}

static bool sensor_read(SensorData& d) {
    strncpy(d.sensor_type,  g_sensor_meta.sensor_type,  sizeof(d.sensor_type));
    strncpy(d.meter_serial, g_sensor_meta.meter_serial, sizeof(d.meter_serial));
    d.meter_baud = g_sensor_meta.meter_baud;

    d.voltage_l1 = d.voltage_l2 = d.voltage_l3 = NAN;
    d.current_l1 = d.current_l2 = d.current_l3 = NAN;
    d.power_w = d.frequency = d.energy_kwh = d.pf = NAN;
    d.valid = false;

    if (!dlms_connected) return false;

    if (g_cfg.test_mode && dlms_simulated) {
        d.voltage_l1 = 218.5f + (random(0, 100) / 25.0f);
        d.current_l1 = 2.5f + (random(0, 100) / 20.0f);
        d.power_w = d.voltage_l1 * d.current_l1 * 0.98f;
        d.frequency = 49.95f + (random(0, 10) / 100.0f);
        static float sim_energy = 124.500f;
        sim_energy += d.power_w / (1000.0f * 120.0f);
        d.energy_kwh = sim_energy;
        d.pf = 0.98f;
        d.valid = true;
        lcd_show_electricity(d);
        return true;
    }

    dlms_get_scaled(OBIS_VL1,    &d.voltage_l1);
    dlms_get_scaled(OBIS_IL1,    &d.current_l1);
    dlms_get_scaled(OBIS_POWER,  &d.power_w);
    dlms_get_scaled(OBIS_FREQ,   &d.frequency);
    dlms_get_scaled(OBIS_ENERGY, &d.energy_kwh);
    dlms_get_scaled(OBIS_PF,     &d.pf);

    if (strcmp(d.sensor_type, "te73") == 0) {
        dlms_get_scaled(OBIS_VL2, &d.voltage_l2);
        dlms_get_scaled(OBIS_VL3, &d.voltage_l3);
        dlms_get_scaled(OBIS_IL2, &d.current_l2);
        dlms_get_scaled(OBIS_IL3, &d.current_l3);
    }

    // Fizik oraliq validatsiyasi
    if (!isnan(d.voltage_l1) && (d.voltage_l1 < 50.0f || d.voltage_l1 > 500.0f)) d.voltage_l1 = NAN;
    if (!isnan(d.voltage_l2) && (d.voltage_l2 < 50.0f || d.voltage_l2 > 500.0f)) d.voltage_l2 = NAN;
    if (!isnan(d.voltage_l3) && (d.voltage_l3 < 50.0f || d.voltage_l3 > 500.0f)) d.voltage_l3 = NAN;
    if (!isnan(d.current_l1) && (d.current_l1 < 0.0f || d.current_l1 > 200.0f))  d.current_l1 = NAN;
    if (!isnan(d.current_l2) && (d.current_l2 < 0.0f || d.current_l2 > 200.0f))  d.current_l2 = NAN;
    if (!isnan(d.current_l3) && (d.current_l3 < 0.0f || d.current_l3 > 200.0f))  d.current_l3 = NAN;
    if (!isnan(d.frequency)  && (d.frequency < 40.0f || d.frequency > 65.0f))     d.frequency = NAN;
    if (!isnan(d.pf)         && (d.pf < -1.0f || d.pf > 1.0f))                   d.pf = NAN;

    d.valid = (!isnan(d.voltage_l1) || !isnan(d.power_w));
    if (d.valid) lcd_show_electricity(d);
    return d.valid;
}

static bool sensor_relay(int method) {
    if (dlms_simulated) return true;

    if (dlms_connected) {
        if (dlms_action(70, OBIS_RELAY, (uint8_t)method)) return true;
    }

    dlms_disconnect();
    unsigned long t = millis(); while (millis() - t < 1000) yield();
    if (!dlms_connect_reader()) return false;
    return dlms_action(70, OBIS_RELAY, (uint8_t)method);
}

static String sensor_build_json(const char* device_id,
                                 const char* fw_version,
                                 const SensorData& d) {
    StaticJsonDocument<512> doc;
    doc["device_id"]    = device_id;
    doc["utility_type"] = "electricity";
    doc["sensor_type"]  = d.sensor_type;
    doc["meter_serial"] = d.meter_serial;
    doc["fw_version"]   = fw_version;
    if (g_cfg.test_mode) doc["is_test_device"] = true;

    if (!isnan(d.voltage_l1) && d.voltage_l1 > 0) doc["voltage_l1"] = serialized(String(d.voltage_l1, 2));
    if (!isnan(d.voltage_l2) && d.voltage_l2 > 0) doc["voltage_l2"] = serialized(String(d.voltage_l2, 2));
    if (!isnan(d.voltage_l3) && d.voltage_l3 > 0) doc["voltage_l3"] = serialized(String(d.voltage_l3, 2));
    if (!isnan(d.current_l1)) doc["current_l1"] = serialized(String(d.current_l1, 3));
    if (!isnan(d.current_l2)) doc["current_l2"] = serialized(String(d.current_l2, 3));
    if (!isnan(d.current_l3)) doc["current_l3"] = serialized(String(d.current_l3, 3));
    if (!isnan(d.power_w))    doc["power_w"]    = (int)d.power_w;
    if (!isnan(d.frequency) && d.frequency > 0) doc["frequency"] = serialized(String(d.frequency, 2));
    if (!isnan(d.energy_kwh)) doc["energy_kwh"] = serialized(String(d.energy_kwh, 3));
    if (!isnan(d.pf) && d.pf > 0) doc["pf"]    = serialized(String(d.pf, 3));

    String out;
    serializeJson(doc, out);
    return out;
}

#ifndef LORA_NODE
static bool sensor_do_register(const char* device_id, const char* fw_version) {
    return app_register(device_id, "electricity",
        g_sensor_meta.sensor_type[0] ? g_sensor_meta.sensor_type : "te71",
        g_sensor_meta.meter_serial, fw_version, g_sensor_meta.meter_baud);
}
#endif

void sensor_set_volume(float) {}
