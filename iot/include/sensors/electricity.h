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
#include "mbedtls/gcm.h"

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
static bool    dlms_connected  = false;
static bool    dlms_simulated  = false;  // true = real meter yo'q, test simulyatsiya
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
    if (!dlms_txrx(2000) || dlms_rx_len < 6) {
        LOG_PRINTLN("  SNRM: timeout/short");
        return false;
    }
    LOG_PRINTF("  SNRM resp(%d):", (int)dlms_rx_len);
    for (size_t i = 0; i < dlms_rx_len && i < 12; i++) LOG_PRINTF(" %02X", dlms_rx[i]);
    LOG_PRINTLN("");
    // RS-485 dan kelgan frame oldida 0x00 null byte bo'lishi mumkin
    // Frame: [00?] 7E A0 len dest src ctrl ...
    // 7E 0xA0 ni topib, undan 5 pozitsiyada ctrl byte ni tekshiramiz
    // UA ctrl = 0x63 (F=0) yoki 0x73 (F=1)
    // DM ctrl = 0x0F yoki 0x1F → rad
    for (size_t i = 0; i + 5 < dlms_rx_len; i++) {
        if (dlms_rx[i] == 0x7E && dlms_rx[i+1] == 0xA0) {
            uint8_t ctrl = dlms_rx[i+5];
            if (ctrl == 0x63 || ctrl == 0x73) return true;
            LOG_PRINTF("  SNRM: not UA (ctrl=0x%02X)\n", ctrl);
            return false;
        }
    }
    LOG_PRINTLN("  SNRM: HDLC frame topilmadi");
    return false;
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

// ─── HLS5 GMAC yordamchi funksiyalar ─────────────────────────────────────────

// AARE javobidan s-to-c challenge ni ajratib olish
// AARE: responding-authentication-value = AA [len] 80 [data_len] [s-to-c bytes]
// NOT A4 (AP-title) — bu keng tarqalgan xato!
static size_t dlms_extract_stoc(uint8_t* stoc, size_t max) {
    for (size_t i = 0; i + 3 < dlms_rx_len; i++) {
        if (dlms_rx[i] == 0xAA && dlms_rx[i+2] == 0x80) {
            uint8_t slen = dlms_rx[i+3];
            if (slen > 0 && slen <= max && i + 4 + slen <= dlms_rx_len) {
                memcpy(stoc, dlms_rx + i + 4, slen);
                return slen;
            }
        }
    }
    return 0;
}

// HLS5 GMAC hisoblash: SC(1) || IC(4) || AES_GCM_tag(12) = 17 bayt
//   AK = Authentication Key (16 bayt, standart = barcha nol)
//   systitle = Client System Title (8 bayt)
//   ic = Invocation Counter (0 dan boshlash)
//   s_chal = server dan kelgan challenge (AARE A4 tegidan)
static bool hls5_gmac(const uint8_t ak[16], const uint8_t systitle[8], uint32_t ic,
                       const uint8_t* s_chal, size_t s_len, uint8_t out[17]) {
    // IV = SysTitle(8) || IC(4)
    uint8_t iv[12];
    memcpy(iv, systitle, 8);
    iv[8]=(ic>>24)&0xFF; iv[9]=(ic>>16)&0xFF; iv[10]=(ic>>8)&0xFF; iv[11]=ic&0xFF;

    // AAD = SC(1) || s_chal
    uint8_t aad[64];
    aad[0] = 0x10;  // SC = authentication only, unicast
    if (s_len > 63) s_len = 63;
    memcpy(aad + 1, s_chal, s_len);

    mbedtls_gcm_context gcm;
    mbedtls_gcm_init(&gcm);
    int ret = mbedtls_gcm_setkey(&gcm, MBEDTLS_CIPHER_ID_AES, ak, 128);
    if (ret) { mbedtls_gcm_free(&gcm); return false; }
    uint8_t tag[16];
    ret = mbedtls_gcm_crypt_and_tag(&gcm, MBEDTLS_GCM_ENCRYPT,
        0, iv, 12, aad, 1 + s_len, NULL, NULL, 12, tag);
    mbedtls_gcm_free(&gcm);
    if (ret) return false;

    out[0] = 0x10;  // SC
    out[1]=(ic>>24)&0xFF; out[2]=(ic>>16)&0xFF;
    out[3]=(ic>>8)&0xFF;  out[4]=ic&0xFF;
    memcpy(out + 5, tag, 12);  // 12 baytlik GMAC teg
    return true;
}

// HLS5 ni yakunlash: ACTION (Class 15, OBIS 0.0.40.0.0.255, method 1)
// data = OCTET-STRING (09 11 SC IC[4] GMAC[12]) = 19 bayt
static bool hls5_complete(const uint8_t resp17[17]) {
    static const uint8_t OBIS_ASSOC[6] = {0x00,0x00,0x28,0x00,0x00,0xFF}; // 0.0.40.0.0.255
    // PDU = C3 01 invoke 00 0F obis[6] method=01 has-data=01 09 11 resp[17] → 33 bayt
    uint8_t pdu[33]; size_t pp = 0;
    pdu[pp++]=0xC3; pdu[pp++]=0x01; pdu[pp++]=dlms_invoke++;
    pdu[pp++]=0x00; pdu[pp++]=0x0F;         // class 15
    memcpy(pdu+pp, OBIS_ASSOC, 6); pp+=6;
    pdu[pp++]=0x01;                          // method 1
    pdu[pp++]=0x01;                          // has-data = 1
    pdu[pp++]=0x09; pdu[pp++]=0x11;         // OCTET-STRING, 17 bayt
    memcpy(pdu+pp, resp17, 17); pp+=17;     // pp = 33
    uint8_t info[3+33];
    memcpy(info, DLMS_LLC, 3); memcpy(info+3, pdu, pp);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, dlms_next_ctrl(), info, 3+pp);
    if (!dlms_txrx(3000)) { LOG_PRINTLN("  HLS5-ACTION timeout"); return false; }
    size_t plen; const uint8_t* r = dlms_find_pdu(&plen);
    LOG_PRINTF("  HLS5-ACTION(%d):", (int)plen);
    for (size_t i = 0; r && i < plen && i < 16; i++) LOG_PRINTF(" %02X", r[i]);
    LOG_PRINTLN("");
    if (!r || plen < 4) return false;
    return (r[0] == 0xC7 && r[3] == 0x00);  // ACTION-Response, success
}

// Manager client — LOW auth, parol "00000000"
// DLMS standart: Manager = Client Address 1 = HDLC SAP 0x03
// TE73 manual va AI qidiruv: Client=1, LOW Security, pwd="00000000"
static bool dlms_connect_manager() {
    // AARQ: ctx01 + LOW auth (mechanism 1), body = 54 = 0x36
    // app_ctx(11) + acse(4) + mech_LOW(9) + auth(12) + ui(18) = 54
    static const uint8_t pwd[8] = {'0','0','0','0','0','0','0','0'};  // "00000000"
    uint8_t aarq[64]; size_t p = 0;
    aarq[p++]=0x60; aarq[p++]=0x36;  // body = 54
    const uint8_t ac[]={0xA1,0x09,0x06,0x07,0x60,0x85,0x74,0x05,0x08,0x01,0x01}; // ctx01
    memcpy(aarq+p, ac, 11); p+=11;
    const uint8_t as[]={0x8A,0x02,0x07,0x80};
    memcpy(aarq+p, as, 4); p+=4;
    const uint8_t mh[]={0x8B,0x07,0x60,0x85,0x74,0x05,0x08,0x02,0x01}; // mechanism 1 = LOW
    memcpy(aarq+p, mh, 9); p+=9;
    // auth value: AC [len+2] 80 [len] [password]
    aarq[p++]=0xAC; aarq[p++]=0x0A; aarq[p++]=0x80; aarq[p++]=0x08;
    memcpy(aarq+p, pwd, 8); p+=8;
    const uint8_t ui[]={0xBE,0x10,0x04,0x0E,0x01,0x00,0x00,0x00,
                        0x06,0x5F,0x1F,0x04,0x00,0x00,0x7E,0x1F,0x04,0xB0};
    memcpy(aarq+p, ui, 18); p+=18;
    // ac(11)+as(4)+mh(9)+auth(4+8=12)+ui(18) = 54 = 0x36 ✓

    // Client 1 = HDLC SAP 0x03 (DLMS standart: Management client = Client Address 1)
    dlms_client   = DLMS_CLIENT_READER;  // 0x03 — Client 1, xuddi Reader bilan bir xil SAP
    dlms_send_seq = dlms_recv_seq = 0;
    delay(500);

    LOG_PRINT("  Mgr SNRM (SAP=03, Client1, LOW)...");
    if (!dlms_snrm()) { LOG_PRINTLN("XATO"); return false; }
    LOG_PRINTLN("OK");

    bool ok = dlms_aarq(aarq, p);
    LOG_PRINTF("  AARE(%d):", (int)dlms_rx_len);
    for (size_t i = 0; i < dlms_rx_len && i < 80; i++)
        LOG_PRINTF(" %02X", dlms_rx[i]);
    LOG_PRINTLN(ok ? " QABUL" : " rad");

    if (ok) LOG_PRINTLN("  Manager ulandi (Client1, LOW auth)");
    else {
        hdlc_build(DLMS_SERVER_ADDR, dlms_client, 0x53, nullptr, 0);
        dlms_txrx(500); dlms_connected = false;
        LOG_PRINTLN("  Manager ulanmadi");
    }
    return ok;
}

// Reader client (Client 1, HLS5) — ulangandan keyin HLS5 completion ham sinab ko'riladi
// Ba'zi metrlar completion talab qiladi, ba'zilari qilmaydi
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
    bool ok = dlms_aarq(aarq, p);
    // AARE logini har doim ko'rish (muvaffaqiyatsiz bo'lganda ham)
    LOG_PRINTF("  Reader AARE(%d):", (int)dlms_rx_len);
    for (size_t i = 0; i < dlms_rx_len && i < 80; i++) LOG_PRINTF(" %02X", dlms_rx[i]);
    LOG_PRINTLN(ok ? " QABUL" : " rad");
    if (!ok) return false;

    // HLS5 completion: s-to-c ajratib, GMAC hisob, ACTION yuborish
    static const uint8_t ak[16]     = {0};  // default AK = nollar
    static const uint8_t syst[8]    = {'E','S','P','3','2','0','0','0'};
    uint8_t stoc[32];
    size_t stoc_len = dlms_extract_stoc(stoc, sizeof(stoc));
    LOG_PRINTF("  Reader s-to-c(%d):", (int)stoc_len);
    for (size_t i = 0; i < stoc_len; i++) LOG_PRINTF(" %02X", stoc[i]);
    LOG_PRINTLN("");
    if (stoc_len > 0) {
        uint8_t resp[17];
        if (hls5_gmac(ak, syst, 0, stoc, stoc_len, resp)) {
            LOG_PRINT("  Reader GMAC:");
            for (int i = 0; i < 17; i++) LOG_PRINTF(" %02X", resp[i]);
            LOG_PRINTLN("");
            if (hls5_complete(resp)) LOG_PRINTLN("  Reader HLS5 to'liq ulandi!");
            else                     LOG_PRINTLN("  Reader HLS5 completion xato");
        }
    }
    return true;
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
    // ACTION PDU: C3 01 invoke cls[2] obis[6] method 01 0F 00
    // connection.py: data=b"\x0F\x00" (has-data=1, int8=0) — ishlaydigan versiya
    uint8_t pdu[15];
    pdu[0]=0xC3; pdu[1]=0x01; pdu[2]=dlms_invoke++;
    pdu[3]=cls>>8; pdu[4]=cls&0xFF;
    memcpy(pdu+5, obis, 6);
    pdu[11]=method; pdu[12]=0x01; pdu[13]=0x0F; pdu[14]=0x00;  // has-data=1, int8(0)
    uint8_t info[18];
    memcpy(info, DLMS_LLC, 3); memcpy(info+3, pdu, 15);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, dlms_next_ctrl(), info, 18);
    if (!dlms_txrx(5000)) return false;
    size_t plen; const uint8_t* resp = dlms_find_pdu(&plen);
    if (!resp || plen < 4) {
        LOG_PRINTF("Relay DLMS javob yo'q (plen=%d)\n", (int)plen);
        return false;
    }
    // C7 01 invoke 00 = success | C7 01 invoke 01 = error
    LOG_PRINTF("Relay DLMS javob: %02X %02X %02X %02X\n",
               resp[0], resp[1], resp[2], resp[3]);
    if (resp[0] == 0xC7 && resp[3] == 0x00) return true;
    // Xato kodini chiqarish (resp[3] = result, resp[4+] = error detail)
    if (resp[0] == 0xC7 && resp[3] != 0x00 && plen > 4)
        LOG_PRINTF("Relay xato kodi: %02X\n", resp[4]);
    return false;
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

// Metrga ulanish: Reader(HLS5) → Public
// Manager (LOW) TE73 da authentication-failure beradi — ishlatilmaydi
static bool sensor_try_baud(uint32_t baud) {
    Serial2.end(); delay(50);
    Serial2.begin(baud, SERIAL_8N1, PIN_RX, PIN_TX); delay(100);
    // 1. Reader (Client 1, HLS5) — to'liq auth, relay uchun zarur
    if (dlms_connect_reader()) return true;
    dlms_disconnect();
    delay(300);
    // 2. Public (Client 16, auth yo'q) — faqat o'qish (fallback)
    if (dlms_connect_public()) return true;
    return false;
}

static bool sensor_connect() {
    LOG_PRINT("  9600...");
    if (sensor_try_baud(9600)) { g_sensor_meta.meter_baud = 9600; return true; }
    dlms_disconnect();
    LOG_PRINT(" 4800...");
    if (sensor_try_baud(4800)) { g_sensor_meta.meter_baud = 4800; return true; }
    dlms_disconnect();

    if (g_cfg.test_mode) {
        LOG_PRINTLN("\n[TEST MODE] Hisoblagich topilmadi. Mock/Simulyatsiya ishga tushirildi!");
        dlms_connected = true;
        dlms_simulated = true;
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
    LOG_PRINTF("Tur: %s\n", g_sensor_meta.sensor_type);
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

    // Faqat simulyatsiya rejimida (real meter yo'q) dummy ma'lumot generatsiya qilish
    if (g_cfg.test_mode && dlms_simulated) {
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
// Strategiya: Reader (Client 1) + HLS5 completion orqali
//   1) Mavjud reader sessiya (HLS5 to'liq) bilan sinash
//   2) Agar xato → qayta ulanish (yangi HLS5 completion) va sinash
static bool sensor_relay(int method) {
    if (dlms_simulated) {
        LOG_PRINTF("[TEST MODE] Simulyatsiya: rele %s\n", method == 2 ? "ON" : "OFF");
        return true;
    }

    // === 1-urinish: mavjud reader sessiya bilan ===
    if (dlms_connected) {
        LOG_PRINTF("Relay %s: reader bilan sinash...\n", method == 2 ? "ON" : "OFF");
        bool r = dlms_action(70, OBIS_RELAY, (uint8_t)method);
        LOG_PRINTF("Relay %s (reader): %s\n", method == 2 ? "ON" : "OFF", r ? "OK" : "XATO");
        if (r) return true;
    }

    // === 2-urinish: reader qayta ulanish + HLS5 completion ===
    LOG_PRINT("Relay: reader qayta ulanmoqda (HLS5)...");
    dlms_disconnect();
    delay(1000);
    if (!dlms_connect_reader()) {
        LOG_PRINTLN(" XATO — reader ulanmadi");
        return false;
    }
    LOG_PRINTLN(" OK");

    bool result = dlms_action(70, OBIS_RELAY, (uint8_t)method);
    LOG_PRINTF("Relay %s (reader+HLS5): %s\n", method == 2 ? "ON" : "OFF", result ? "OK" : "XATO");
    return result;
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
// LORA_NODE da WiFi/HTTP yo'q — ishlatilmaydi
#ifndef LORA_NODE
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
#endif

void sensor_set_volume(float val) {
    // Electricity does not use pulse counters
}
