#pragma once
/**
 * electricity.h — TE71/TE73 RS-485 DLMS/COSEM sensor
 *
 * Sensor interfeysi (main.cpp dan ishlatiladigan funksiyalar):
 *   sensor_init()             → RS-485 pinlari, FCS jadval
 *   sensor_connect() → bool   → meter ga DLMS ulanish
 *   sensor_read(SensorData&) → bool  → ma'lumotlarni o'qish
 *   sensor_relay(method)      → bool  → relay boshqaruv (1=off, 2=on)
 *   sensor_build_json(...)    → String → backend uchun JSON
 *
 * Ichki (umumiy.h dan ko'rinmaydi):
 *   dlms_*  → HDLC/DLMS protokol
 */

#include <Arduino.h>
#include <ArduinoJson.h>

// ─── RS-485 pinlar ────────────────────────────────────────────────────────────
#define PIN_RX   16
#define PIN_TX   17
#define PIN_DE    4

// ─── DLMS sabitlar ────────────────────────────────────────────────────────────
#define DLMS_SERVER_ADDR    0x03
#define DLMS_CLIENT_PUBLIC  0x21
#define DLMS_CLIENT_READER  0x03
static const uint8_t DLMS_LLC[] = {0xE6, 0xE6, 0x00};

// ─── OBIS kodlar (TE71 + TE73) ────────────────────────────────────────────────
static const uint8_t OBIS_RELAY[6]   = {0x00,0x00,0x60,0x03,0x0A,0xFF}; // Class 70
static const uint8_t OBIS_SERIAL[6]  = {0x00,0x00,0x60,0x01,0x00,0xFF}; // Class 1
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

// ─── SensorData (elektr) ──────────────────────────────────────────────────────
struct SensorData {
    // Elektr o'lchamlar
    float voltage_l1, voltage_l2, voltage_l3;  // V
    float current_l1, current_l2, current_l3;  // A
    float power_w;                              // W
    float frequency;                            // Hz
    float energy_kwh;                           // kWh
    float pf;                                   // Power factor

    // Qurilma meta
    char  sensor_type[8];    // "te71" yoki "te73"
    char  meter_serial[32];  // Hisoblagich seriya raqami
    int   meter_baud;        // Ulanish baud rate
    bool  valid;             // O'qish muvaffaqiyatlimi
};

// ─── DLMS ichki holat ─────────────────────────────────────────────────────────
static bool    dlms_connected = false;
static uint8_t dlms_client    = DLMS_CLIENT_READER;
static uint8_t dlms_send_seq  = 0;
static uint8_t dlms_recv_seq  = 0;
static uint8_t dlms_invoke    = 0xC0;

static uint8_t dlms_tx[300];
static size_t  dlms_tx_len;
static uint8_t dlms_rx[300];
static size_t  dlms_rx_len;

// Global sensor holatini saqlash (sensor_type va serial ni connect dan keyin)
static SensorData g_sensor_meta;  // type, serial, baud saqlanadi

// ═══════════════════════════════════════════════════════════════════════════════
// FCS16
// ═══════════════════════════════════════════════════════════════════════════════
static uint16_t fcs_tbl[256];
static bool     fcs_ready = false;

static void fcs_init_table() {
    if (fcs_ready) return;
    for (int i = 0; i < 256; i++) {
        uint16_t v = i;
        for (int j = 0; j < 8; j++)
            v = (v & 1) ? ((v >> 1) ^ 0x8408) : (v >> 1);
        fcs_tbl[i] = v;
    }
    fcs_ready = true;
}

static uint16_t fcs16(const uint8_t* d, size_t n) {
    uint16_t f = 0xFFFF;
    for (size_t i = 0; i < n; i++)
        f = (f >> 8) ^ fcs_tbl[(f ^ d[i]) & 0xFF];
    return f ^ 0xFFFF;
}

// ═══════════════════════════════════════════════════════════════════════════════
// HDLC frame builder
// ═══════════════════════════════════════════════════════════════════════════════
static void hdlc_build(uint8_t dest, uint8_t src, uint8_t ctrl,
                        const uint8_t* info, size_t ilen) {
    if (ilen == 0) {
        // U-frame (SNRM, DISC)
        uint16_t tot = 7;
        uint8_t fd[5] = {(uint8_t)(0xA0|(tot>>8)),(uint8_t)(tot&0xFF),dest,src,ctrl};
        uint16_t f = fcs16(fd, 5);
        dlms_tx[0]=0x7E; memcpy(dlms_tx+1,fd,5);
        dlms_tx[6]=f&0xFF; dlms_tx[7]=f>>8; dlms_tx[8]=0x7E;
        dlms_tx_len = 9;
    } else {
        // I-frame
        uint16_t tot = 9 + (uint16_t)ilen;
        uint8_t fmt[2] = {(uint8_t)(0xA0|(tot>>8)),(uint8_t)(tot&0xFF)};
        uint8_t hh[5]  = {fmt[0],fmt[1],dest,src,ctrl};
        uint16_t hcs   = fcs16(hh, 5);
        dlms_tx[0]=0x7E; dlms_tx[1]=fmt[0]; dlms_tx[2]=fmt[1];
        dlms_tx[3]=dest; dlms_tx[4]=src;    dlms_tx[5]=ctrl;
        dlms_tx[6]=hcs&0xFF; dlms_tx[7]=hcs>>8;
        memcpy(dlms_tx+8, info, ilen);
        uint16_t fcs = fcs16(dlms_tx+1, 7+ilen);
        dlms_tx[8+ilen]  = fcs&0xFF;
        dlms_tx[9+ilen]  = fcs>>8;
        dlms_tx[10+ilen] = 0x7E;
        dlms_tx_len = 11 + ilen;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// RS-485 TX/RX
// ═══════════════════════════════════════════════════════════════════════════════
static bool dlms_txrx(uint32_t timeout_ms = 3000) {
    while (Serial2.available()) Serial2.read();
    dlms_rx_len = 0;

    digitalWrite(PIN_DE, HIGH);
    delayMicroseconds(200);        // DE stable
    Serial2.write(dlms_tx, dlms_tx_len);
    Serial2.flush();               // TX tugaguncha kutish
    delayMicroseconds(600);        // Bus settling
    digitalWrite(PIN_DE, LOW);
    delayMicroseconds(300);        // RE enable

    uint32_t t = millis();
    while (millis() - t < timeout_ms) {
        while (Serial2.available() && dlms_rx_len < sizeof(dlms_rx))
            dlms_rx[dlms_rx_len++] = Serial2.read();
        if (dlms_rx_len > 4 && dlms_rx[dlms_rx_len-1] == 0x7E) break;
        delay(2);
    }
    return dlms_rx_len > 4;
}

// LLC+PDU qismini topish (E6 E7 00 dan keyin)
static const uint8_t* dlms_find_pdu(size_t* plen) {
    for (size_t i = 0; i+2 < dlms_rx_len; i++) {
        if (dlms_rx[i]==0xE6 && dlms_rx[i+1]==0xE7 && dlms_rx[i+2]==0x00) {
            int rem = (int)dlms_rx_len - (int)i - 3 - 3;  // 3=LLC, 3=FCS+FLAG
            *plen = rem > 0 ? (size_t)rem : 0;
            return dlms_rx + i + 3;
        }
    }
    *plen = 0; return nullptr;
}

static float dlms_parse_float(const uint8_t* d, size_t len) {
    if (len < 2) return NAN;
    switch (d[0]) {
        case 0x05: return (float)(int32_t)(((uint32_t)d[1]<<24)|((uint32_t)d[2]<<16)|
                                           ((uint32_t)d[3]<<8)|d[4]);
        case 0x06: return (float)(((uint32_t)d[1]<<24)|((uint32_t)d[2]<<16)|
                                  ((uint32_t)d[3]<<8)|d[4]);
        case 0x12: return (float)(((uint16_t)d[1]<<8)|d[2]);
        case 0x16: return (float)d[1];
        default:   return NAN;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DLMS ulanish (SNRM + AARQ)
// ═══════════════════════════════════════════════════════════════════════════════
static uint8_t dlms_next_ctrl() {
    uint8_t c = ((dlms_send_seq&7)<<5) | 0x10 | ((dlms_recv_seq&7)<<1);
    dlms_send_seq = (dlms_send_seq + 1) % 8;
    dlms_recv_seq = (dlms_recv_seq + 1) % 8;
    return c;
}

static bool dlms_snrm() {
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, 0x93, nullptr, 0);
    return dlms_txrx(2000) && dlms_rx_len > 4;
}

static bool dlms_aarq(const uint8_t* aarq, size_t alen) {
    uint8_t info[128];
    memcpy(info, DLMS_LLC, 3);
    memcpy(info+3, aarq, alen);
    uint8_t ctrl = ((dlms_send_seq&7)<<5) | 0x10 | ((dlms_recv_seq&7)<<1);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, ctrl, info, 3+alen);
    if (!dlms_txrx(3000)) return false;
    // AARE javobida A2 03 02 01 00 = result: accepted
    for (size_t i = 0; i+4 < dlms_rx_len; i++) {
        if (dlms_rx[i]==0xA2 && dlms_rx[i+1]==0x03 && dlms_rx[i+2]==0x02 &&
            dlms_rx[i+3]==0x01 && dlms_rx[i+4]==0x00) {
            dlms_connected = true;
            dlms_send_seq  = 1;
            dlms_recv_seq  = 1;
            dlms_invoke    = 0xC0;
            return true;
        }
    }
    return false;
}

// Public client (Client 16, no auth)
static bool dlms_connect_public() {
    dlms_client = DLMS_CLIENT_PUBLIC;
    dlms_send_seq = dlms_recv_seq = 0;
    if (!dlms_snrm()) return false;
    static const uint8_t aarq[] = {
        0x60,0x1D,0xA1,0x09,0x06,0x07,0x60,0x85,0x74,0x05,0x08,0x01,0x01,
        0xBE,0x10,0x04,0x0E,0x01,0x00,0x00,0x00,0x06,0x5F,0x1F,0x04,0x00,0x00,0x7E,0x1F,0x04,0xB0
    };
    return dlms_aarq(aarq, sizeof(aarq));
}

// Reader client (Client 1, HLS5)
static bool dlms_connect_reader() {
    dlms_client = DLMS_CLIENT_READER;
    dlms_send_seq = dlms_recv_seq = 0;
    if (!dlms_snrm()) return false;
    static const uint8_t ctos[16] = {
        0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,
        0x99,0xAA,0xBB,0xCC,0xDD,0xEE,0xFF,0x00
    };
    uint8_t aarq[72]; size_t p = 0;
    aarq[p++]=0x60; aarq[p++]=0x3E;
    const uint8_t ac[]={0xA1,0x09,0x06,0x07,0x60,0x85,0x74,0x05,0x08,0x01,0x01};
    memcpy(aarq+p, ac, 11); p+=11;
    const uint8_t as[]={0x8A,0x02,0x07,0x80};
    memcpy(aarq+p, as, 4);  p+=4;
    const uint8_t mh[]={0x8B,0x07,0x60,0x85,0x74,0x05,0x08,0x02,0x05};
    memcpy(aarq+p, mh, 9);  p+=9;
    aarq[p++]=0xAC; aarq[p++]=0x12; aarq[p++]=0x80; aarq[p++]=0x10;
    memcpy(aarq+p, ctos, 16); p+=16;
    const uint8_t ui[]={0xBE,0x10,0x04,0x0E,0x01,0x00,0x00,0x00,
                        0x06,0x5F,0x1F,0x04,0x00,0x00,0x7E,0x1F,0x04,0xB0};
    memcpy(aarq+p, ui, 18); p+=18;
    return dlms_aarq(aarq, p);
}

static void dlms_disconnect() {
    if (!dlms_connected) return;
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, 0x53, nullptr, 0);
    dlms_txrx(1000);
    dlms_connected = false;
    dlms_send_seq  = 0;
    dlms_recv_seq  = 0;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DLMS GET attribute
// ═══════════════════════════════════════════════════════════════════════════════
static bool dlms_get_float(uint16_t cls, const uint8_t obis[6],
                            uint8_t attr, float* out) {
    if (!dlms_connected) return false;
    uint8_t pdu[13];
    pdu[0]=0xC0; pdu[1]=0x01; pdu[2]=dlms_invoke++;
    pdu[3]=cls>>8; pdu[4]=cls&0xFF;
    memcpy(pdu+5, obis, 6); pdu[11]=attr; pdu[12]=0x00;
    uint8_t info[16];
    memcpy(info, DLMS_LLC, 3); memcpy(info+3, pdu, 13);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, dlms_next_ctrl(), info, 16);
    if (!dlms_txrx(3000)) return false;
    size_t plen; const uint8_t* resp = dlms_find_pdu(&plen);
    if (!resp || plen<5 || resp[0]!=0xC4 || resp[3]!=0x00) return false;
    if (out) *out = dlms_parse_float(resp+4, plen-4);
    return true;
}

static bool dlms_get_string(uint16_t cls, const uint8_t obis[6],
                             uint8_t attr, char* out, size_t out_sz) {
    if (!dlms_connected) return false;
    uint8_t pdu[13];
    pdu[0]=0xC0; pdu[1]=0x01; pdu[2]=dlms_invoke++;
    pdu[3]=cls>>8; pdu[4]=cls&0xFF;
    memcpy(pdu+5, obis, 6); pdu[11]=attr; pdu[12]=0x00;
    uint8_t info[16];
    memcpy(info, DLMS_LLC, 3); memcpy(info+3, pdu, 13);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, dlms_next_ctrl(), info, 16);
    if (!dlms_txrx(3000)) return false;
    size_t plen; const uint8_t* resp = dlms_find_pdu(&plen);
    if (!resp || plen<5 || resp[0]!=0xC4 || resp[3]!=0x00) return false;
    const uint8_t* d = resp+4; size_t dlen = plen-4;
    if (dlen>=2 && (d[0]==0x09 || d[0]==0x0A)) {
        uint8_t slen = d[1];
        size_t cp = slen < out_sz-1 ? slen : out_sz-1;
        memcpy(out, d+2, cp); out[cp] = '\0';
        return true;
    }
    return false;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DLMS ACTION (Class 70 relay: method 1=off, method 2=on)
// ═══════════════════════════════════════════════════════════════════════════════
static bool dlms_action(uint16_t cls, const uint8_t obis[6], uint8_t method) {
    if (!dlms_connected) return false;
    // ACTION PDU: C3 01 invoke cls[2] obis[6] method has-data=01 integer(0)
    uint8_t pdu[15];
    pdu[0]=0xC3; pdu[1]=0x01; pdu[2]=dlms_invoke++;
    pdu[3]=cls>>8; pdu[4]=cls&0xFF;
    memcpy(pdu+5, obis, 6);
    pdu[11]=method; pdu[12]=0x01;  // has-data = true
    pdu[13]=0x0F;   pdu[14]=0x00;  // integer(0)
    uint8_t info[18];
    memcpy(info, DLMS_LLC, 3); memcpy(info+3, pdu, 15);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, dlms_next_ctrl(), info, 18);
    if (!dlms_txrx(5000)) return false;
    size_t plen; const uint8_t* resp = dlms_find_pdu(&plen);
    // C7 01 invoke 00 = success
    return resp && plen>=4 && resp[0]==0xC7 && resp[3]==0x00;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sensor API (main.cpp dan chaqiriladigan)
// ═══════════════════════════════════════════════════════════════════════════════

// RS-485 pinlarini va FCS jadvalini sozlash
static void sensor_init() {
    fcs_init_table();
    pinMode(PIN_DE, OUTPUT);
    digitalWrite(PIN_DE, LOW);
    Serial2.begin(9600, SERIAL_8N1, PIN_RX, PIN_TX);
    g_sensor_meta.meter_baud    = 9600;
    g_sensor_meta.meter_serial[0] = '\0';
    g_sensor_meta.sensor_type[0]  = '\0';
}

// Metrga ulanish (Reader, keyin Public fallback)
static bool sensor_try_baud(uint32_t baud) {
    Serial2.end(); delay(50);
    Serial2.begin(baud, SERIAL_8N1, PIN_RX, PIN_TX); delay(100);
    if (dlms_connect_reader()) return true;
    dlms_disconnect();
    if (dlms_connect_public()) return true;
    return false;
}

static bool sensor_connect() {
    Serial.print("  9600...");
    if (sensor_try_baud(9600)) { g_sensor_meta.meter_baud = 9600; return true; }
    dlms_disconnect();
    Serial.print(" 4800...");
    if (sensor_try_baud(4800)) { g_sensor_meta.meter_baud = 4800; return true; }
    dlms_disconnect();

    if (g_cfg.test_mode) {
        Serial.println("\n[TEST MODE] Hisoblagich topilmadi. Mock/Simulyatsiya ishga tushirildi!");
        dlms_connected = true;
        g_sensor_meta.meter_baud = 9600;
        if (!g_sensor_meta.meter_serial[0]) {
            strncpy(g_sensor_meta.meter_serial, "202032000525", sizeof(g_sensor_meta.meter_serial));
        }
        strncpy(g_sensor_meta.sensor_type, "te71", sizeof(g_sensor_meta.sensor_type));
        return true;
    }
    return false;
}

// TE71 / TE73 auto-detect: L2 kuchlanish mavjudmi?
static void sensor_detect_type() {
    float vl2 = NAN;
    dlms_get_float(3, OBIS_VL2, 2, &vl2);
    bool is_te73 = !isnan(vl2) && vl2 > 10;  // mV da — 10mV < = noise
    strncpy(g_sensor_meta.sensor_type, is_te73 ? "te73" : "te71",
            sizeof(g_sensor_meta.sensor_type));
    Serial.printf("Tur: %s\n", g_sensor_meta.sensor_type);
}

// Barcha ma'lumotlarni o'qish → SensorData
static bool sensor_read(SensorData& d) {
    // sensor_type va meter_serial g_sensor_meta dan copy
    strncpy(d.sensor_type,   g_sensor_meta.sensor_type,   sizeof(d.sensor_type));
    strncpy(d.meter_serial,  g_sensor_meta.meter_serial,  sizeof(d.meter_serial));
    d.meter_baud = g_sensor_meta.meter_baud;

    d.voltage_l1 = d.voltage_l2 = d.voltage_l3 = NAN;
    d.current_l1 = d.current_l2 = d.current_l3 = NAN;
    d.power_w = d.frequency = d.energy_kwh = d.pf = NAN;
    d.valid = false;

    if (!dlms_connected) return false;

    // Test rejimida va simulyatsiya hisoblagich serial bo'lsa, dummy ma'lumot generatsiya qilish
    if (g_cfg.test_mode && strcmp(d.meter_serial, "202032000525") == 0) {
        d.voltage_l1 = 218.5f + (random(0, 100) / 25.0f); // 218.5 - 222.5 V
        d.current_l1 = 2.5f + (random(0, 100) / 20.0f);   // 2.5 - 7.5 A
        d.power_w = d.voltage_l1 * d.current_l1 * 0.98f;
        d.frequency = 49.95f + (random(0, 10) / 100.0f);   // 49.95 - 50.05 Hz
        
        static float sim_energy = 124.500f;
        sim_energy += d.power_w / (1000.0f * 120.0f); // har o'qishda bir oz oshadi
        d.energy_kwh = sim_energy;
        d.pf = 0.98f;
        d.valid = true;
        return true;
    }

    dlms_get_float(3, OBIS_VL1,    2, &d.voltage_l1);
    dlms_get_float(3, OBIS_IL1,    2, &d.current_l1);
    dlms_get_float(3, OBIS_POWER,  2, &d.power_w);
    dlms_get_float(3, OBIS_FREQ,   2, &d.frequency);
    dlms_get_float(3, OBIS_ENERGY, 2, &d.energy_kwh);
    dlms_get_float(3, OBIS_PF,     2, &d.pf);

    if (strcmp(d.sensor_type, "te73") == 0) {
        dlms_get_float(3, OBIS_VL2, 2, &d.voltage_l2);
        dlms_get_float(3, OBIS_VL3, 2, &d.voltage_l3);
        dlms_get_float(3, OBIS_IL2, 2, &d.current_l2);
        dlms_get_float(3, OBIS_IL3, 2, &d.current_l3);
    }

    // Scaler: mV→V, mA→A, mHz→Hz, Wh→kWh
    if (!isnan(d.voltage_l1)) d.voltage_l1 /= 1000.0f;
    if (!isnan(d.voltage_l2)) d.voltage_l2 /= 1000.0f;
    if (!isnan(d.voltage_l3)) d.voltage_l3 /= 1000.0f;
    if (!isnan(d.current_l1)) d.current_l1 /= 1000.0f;
    if (!isnan(d.current_l2)) d.current_l2 /= 1000.0f;
    if (!isnan(d.current_l3)) d.current_l3 /= 1000.0f;
    if (!isnan(d.frequency))  d.frequency  /= 1000.0f;
    if (!isnan(d.energy_kwh)) d.energy_kwh /= 1000.0f;
    if (!isnan(d.pf))         d.pf         /= 1000.0f;

    d.valid = (!isnan(d.voltage_l1) || !isnan(d.power_w));
    return d.valid;
}

// Relay buyrug'i: method 1=off(disconnect), 2=on(reconnect)
static bool sensor_relay(int method) {
    if (g_cfg.test_mode && strcmp(g_sensor_meta.meter_serial, "202032000525") == 0) {
        Serial.printf("[TEST MODE] Simulyatsiya qilingan rele %s qilindi!\n", method == 2 ? "ON" : "OFF");
        return true;
    }
    return dlms_action(70, OBIS_RELAY, (uint8_t)method);
}

// Backend uchun JSON (MeterReading sxemasiga mos)
static String sensor_build_json(const char* device_id,
                                 const char* fw_version,
                                 const SensorData& d) {
    StaticJsonDocument<512> doc;
    doc["device_id"]    = device_id;
    doc["utility_type"] = "electricity";
    doc["sensor_type"]  = d.sensor_type;   // "te71" | "te73"
    doc["meter_serial"] = d.meter_serial;
    doc["fw_version"]   = fw_version;
    if (g_cfg.test_mode) doc["is_test_device"] = true;

    // Faqat valid qiymatlarni yozish (NaN = qo'shmaslik)
    if (!isnan(d.voltage_l1) && d.voltage_l1 > 0)
        doc["voltage_l1"] = serialized(String(d.voltage_l1, 2));
    if (!isnan(d.voltage_l2) && d.voltage_l2 > 0)
        doc["voltage_l2"] = serialized(String(d.voltage_l2, 2));
    if (!isnan(d.voltage_l3) && d.voltage_l3 > 0)
        doc["voltage_l3"] = serialized(String(d.voltage_l3, 2));
    if (!isnan(d.current_l1))
        doc["current_l1"] = serialized(String(d.current_l1, 3));
    if (!isnan(d.current_l2))
        doc["current_l2"] = serialized(String(d.current_l2, 3));
    if (!isnan(d.current_l3))
        doc["current_l3"] = serialized(String(d.current_l3, 3));
    if (!isnan(d.power_w))
        doc["power_w"] = (int)d.power_w;
    if (!isnan(d.frequency) && d.frequency > 0)
        doc["frequency"] = serialized(String(d.frequency, 2));
    if (!isnan(d.energy_kwh))
        doc["energy_kwh"] = serialized(String(d.energy_kwh, 3));
    if (!isnan(d.pf) && d.pf > 0)
        doc["pf"] = serialized(String(d.pf, 3));

    String out;
    serializeJson(doc, out);
    return out;
}

// Backend uchun registratsiya (main.cpp dan chaqiriladi)
static bool sensor_do_register(const char* device_id, const char* fw_version) {
    return app_register(
        device_id,
        "electricity",
        g_sensor_meta.sensor_type[0] ? g_sensor_meta.sensor_type : "te71",
        g_sensor_meta.meter_serial,
        fw_version,
        g_sensor_meta.meter_baud
    );
}
