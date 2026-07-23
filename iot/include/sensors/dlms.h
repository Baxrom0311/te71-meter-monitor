#pragma once
/**
 * sensors/dlms.h — DLMS/COSEM HDLC protokol (RS-485)
 *
 * FCS16, HDLC frame, TX/RX, SNRM/AARQ/DISC, GET/ACTION
 * HLS5 GMAC, Manager LOW, Reader HLS5
 */

#include <Arduino.h>
#include "mbedtls/gcm.h"
#include "core/log.h"

// ─── RS-485 pinlar ────────────────────────────────────────────────────────────
#define PIN_RX   16
#define PIN_TX   17
#define PIN_DE    4

// ─── DLMS sabitlar ────────────────────────────────────────────────────────────
#define DLMS_SERVER_ADDR    0x03
#define DLMS_CLIENT_PUBLIC  0x21
#define DLMS_CLIENT_READER  0x03
static const uint8_t DLMS_LLC[] = {0xE6, 0xE6, 0x00};

// ─── DLMS holat ───────────────────────────────────────────────────────────────
static bool    dlms_connected  = false;
static bool    dlms_simulated  = false;
static uint8_t dlms_client     = DLMS_CLIENT_READER;
static uint8_t dlms_send_seq   = 0;
static uint8_t dlms_recv_seq   = 0;
static uint8_t dlms_invoke     = 0xC0;

static uint8_t dlms_tx[300];
static size_t  dlms_tx_len;
static uint8_t dlms_rx[300];
static size_t  dlms_rx_len;

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
        uint16_t tot = 7;
        uint8_t fd[5] = {(uint8_t)(0xA0|(tot>>8)),(uint8_t)(tot&0xFF),dest,src,ctrl};
        uint16_t f = fcs16(fd, 5);
        dlms_tx[0]=0x7E; memcpy(dlms_tx+1,fd,5);
        dlms_tx[6]=f&0xFF; dlms_tx[7]=f>>8; dlms_tx[8]=0x7E;
        dlms_tx_len = 9;
    } else {
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
    delayMicroseconds(200);
    Serial2.write(dlms_tx, dlms_tx_len);
    Serial2.flush();
    delayMicroseconds(600);
    digitalWrite(PIN_DE, LOW);
    delayMicroseconds(300);

    uint32_t t = millis();
    while (millis() - t < timeout_ms) {
        while (Serial2.available() && dlms_rx_len < sizeof(dlms_rx))
            dlms_rx[dlms_rx_len++] = Serial2.read();
        if (dlms_rx_len > 4 && dlms_rx[dlms_rx_len-1] == 0x7E) break;
        yield();
    }
    return dlms_rx_len > 4;
}

static const uint8_t* dlms_find_pdu(size_t* plen) {
    for (size_t i = 0; i+2 < dlms_rx_len; i++) {
        if (dlms_rx[i]==0xE6 && dlms_rx[i+1]==0xE7 && dlms_rx[i+2]==0x00) {
            int rem = (int)dlms_rx_len - (int)i - 3 - 3;
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
        case 0x0F: return (float)(int8_t)d[1];
        case 0x10: return (float)(int16_t)(((uint16_t)d[1]<<8)|d[2]);
        case 0x11: return (float)d[1];
        case 0x12: return (float)(((uint16_t)d[1]<<8)|d[2]);
        case 0x16: return (float)(int8_t)d[1];
        default:
            LOG_PRINTF("dlms_parse: 0x%02X?\n", d[0]);
            return NAN;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DLMS ulanish
// ═══════════════════════════════════════════════════════════════════════════════
static uint8_t dlms_next_ctrl() {
    uint8_t c = ((dlms_send_seq&7)<<5) | 0x10 | ((dlms_recv_seq&7)<<1);
    dlms_send_seq = (dlms_send_seq + 1) % 8;
    dlms_recv_seq = (dlms_recv_seq + 1) % 8;
    return c;
}

static bool dlms_snrm() {
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, 0x93, nullptr, 0);
    if (!dlms_txrx(2000) || dlms_rx_len < 6) return false;
    for (size_t i = 0; i + 5 < dlms_rx_len; i++) {
        if (dlms_rx[i] == 0x7E && dlms_rx[i+1] == 0xA0) {
            uint8_t ctrl = dlms_rx[i+5];
            if (ctrl == 0x63 || ctrl == 0x73) return true;
            return false;
        }
    }
    return false;
}

static bool dlms_aarq(const uint8_t* aarq, size_t alen) {
    uint8_t info[128];
    memcpy(info, DLMS_LLC, 3);
    memcpy(info+3, aarq, alen);
    uint8_t ctrl = ((dlms_send_seq&7)<<5) | 0x10 | ((dlms_recv_seq&7)<<1);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, ctrl, info, 3+alen);
    if (!dlms_txrx(3000)) return false;
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

// ─── Public client (Client 16, no auth) ───────────────────────────────────────
static bool dlms_connect_public() {
    dlms_client = DLMS_CLIENT_PUBLIC;
    dlms_send_seq = dlms_recv_seq = 0;
    if (!dlms_snrm()) return false;
    static const uint8_t aarq[] = {
        0x60,0x1D,0xA1,0x09,0x06,0x07,0x60,0x85,0x74,0x05,0x08,0x01,0x01,
        0xBE,0x10,0x04,0x0E,0x01,0x00,0x00,0x00,0x06,0x5F,0x1F,0x04,0x00,
        0x00,0x7E,0x1F,0x04,0xB0
    };
    return dlms_aarq(aarq, sizeof(aarq));
}

// ─── HLS5 GMAC ───────────────────────────────────────────────────────────────
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

static bool hls5_gmac(const uint8_t ak[16], const uint8_t systitle[8],
                       uint32_t ic, const uint8_t* s_chal, size_t s_len,
                       uint8_t out[17]) {
    uint8_t iv[12];
    memcpy(iv, systitle, 8);
    iv[8]=(ic>>24)&0xFF; iv[9]=(ic>>16)&0xFF; iv[10]=(ic>>8)&0xFF; iv[11]=ic&0xFF;

    uint8_t aad[64];
    aad[0] = 0x10;
    if (s_len > 63) s_len = 63;
    memcpy(aad + 1, s_chal, s_len);

    mbedtls_gcm_context gcm;
    mbedtls_gcm_init(&gcm);
    if (mbedtls_gcm_setkey(&gcm, MBEDTLS_CIPHER_ID_AES, ak, 128)) {
        mbedtls_gcm_free(&gcm); return false;
    }
    uint8_t tag[16];
    int ret = mbedtls_gcm_crypt_and_tag(&gcm, MBEDTLS_GCM_ENCRYPT,
        0, iv, 12, aad, 1 + s_len, NULL, NULL, 12, tag);
    mbedtls_gcm_free(&gcm);
    if (ret) return false;

    out[0] = 0x10;
    out[1]=(ic>>24)&0xFF; out[2]=(ic>>16)&0xFF;
    out[3]=(ic>>8)&0xFF;  out[4]=ic&0xFF;
    memcpy(out + 5, tag, 12);
    return true;
}

static bool hls5_complete(const uint8_t resp17[17]) {
    static const uint8_t OBIS_ASSOC[6] = {0x00,0x00,0x28,0x00,0x00,0xFF};
    uint8_t pdu[33]; size_t pp = 0;
    pdu[pp++]=0xC3; pdu[pp++]=0x01; pdu[pp++]=dlms_invoke++;
    pdu[pp++]=0x00; pdu[pp++]=0x0F;
    memcpy(pdu+pp, OBIS_ASSOC, 6); pp+=6;
    pdu[pp++]=0x01; pdu[pp++]=0x01;
    pdu[pp++]=0x09; pdu[pp++]=0x11;
    memcpy(pdu+pp, resp17, 17); pp+=17;
    uint8_t info[3+33];
    memcpy(info, DLMS_LLC, 3); memcpy(info+3, pdu, pp);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, dlms_next_ctrl(), info, 3+pp);
    if (!dlms_txrx(3000)) return false;
    size_t plen; const uint8_t* r = dlms_find_pdu(&plen);
    if (!r || plen < 4) return false;
    return (r[0] == 0xC7 && r[3] == 0x00);
}

// ─── Manager client (LOW auth, "00000000") ────────────────────────────────────
static bool dlms_connect_manager() {
    static const uint8_t pwd[8] = {'0','0','0','0','0','0','0','0'};
    uint8_t aarq[64]; size_t p = 0;
    aarq[p++]=0x60; aarq[p++]=0x36;
    const uint8_t ac[]={0xA1,0x09,0x06,0x07,0x60,0x85,0x74,0x05,0x08,0x01,0x01};
    memcpy(aarq+p, ac, 11); p+=11;
    const uint8_t as[]={0x8A,0x02,0x07,0x80};
    memcpy(aarq+p, as, 4); p+=4;
    const uint8_t mh[]={0x8B,0x07,0x60,0x85,0x74,0x05,0x08,0x02,0x01};
    memcpy(aarq+p, mh, 9); p+=9;
    aarq[p++]=0xAC; aarq[p++]=0x0A; aarq[p++]=0x80; aarq[p++]=0x08;
    memcpy(aarq+p, pwd, 8); p+=8;
    const uint8_t ui[]={0xBE,0x10,0x04,0x0E,0x01,0x00,0x00,0x00,
                        0x06,0x5F,0x1F,0x04,0x00,0x00,0x7E,0x1F,0x04,0xB0};
    memcpy(aarq+p, ui, 18); p+=18;

    dlms_client   = DLMS_CLIENT_READER;
    dlms_send_seq = dlms_recv_seq = 0;
    unsigned long t = millis(); while (millis() - t < 500) yield();

    if (!dlms_snrm()) return false;
    bool ok = dlms_aarq(aarq, p);
    if (!ok) {
        hdlc_build(DLMS_SERVER_ADDR, dlms_client, 0x53, nullptr, 0);
        dlms_txrx(500); dlms_connected = false;
    }
    return ok;
}

// ─── Reader client (Client 1, HLS5) ──────────────────────────────────────────
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
    if (!dlms_aarq(aarq, p)) return false;

    // HLS5 completion
    static const uint8_t ak[16]  = {0};
    static const uint8_t syst[8] = {'E','S','P','3','2','0','0','0'};
    uint8_t stoc[32];
    size_t stoc_len = dlms_extract_stoc(stoc, sizeof(stoc));
    if (stoc_len > 0) {
        uint8_t resp[17];
        if (hls5_gmac(ak, syst, 0, stoc, stoc_len, resp))
            hls5_complete(resp);
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
// DLMS GET/ACTION
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

static bool dlms_get_scaled(const uint8_t obis[6], float* out) {
    float raw = NAN;
    if (!dlms_get_float(3, obis, 2, &raw)) return false;
    if (!out) return true;

    uint8_t pdu[13];
    pdu[0]=0xC0; pdu[1]=0x01; pdu[2]=dlms_invoke++;
    pdu[3]=0x00; pdu[4]=0x03;
    memcpy(pdu+5, obis, 6); pdu[11]=0x03; pdu[12]=0x00;
    uint8_t info[16];
    memcpy(info, DLMS_LLC, 3); memcpy(info+3, pdu, 13);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, dlms_next_ctrl(), info, 16);

    int8_t scaler = 0;
    if (dlms_txrx(3000)) {
        size_t plen; const uint8_t* resp = dlms_find_pdu(&plen);
        if (resp && plen >= 10 && resp[0]==0xC4 && resp[3]==0x00 &&
            resp[4]==0x02 && resp[5]==0x02 && resp[6]==0x16)
            scaler = (int8_t)resp[7];
    }

    if (scaler == 0) { *out = raw; }
    else if (scaler > 0) {
        float m = 1.0f;
        for (int i = 0; i < scaler; i++) m *= 10.0f;
        *out = raw * m;
    } else {
        float m = 1.0f;
        for (int i = 0; i < -scaler; i++) m *= 10.0f;
        *out = raw / m;
    }
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

static bool dlms_action(uint16_t cls, const uint8_t obis[6], uint8_t method) {
    if (!dlms_connected) return false;
    uint8_t pdu[15];
    pdu[0]=0xC3; pdu[1]=0x01; pdu[2]=dlms_invoke++;
    pdu[3]=cls>>8; pdu[4]=cls&0xFF;
    memcpy(pdu+5, obis, 6);
    pdu[11]=method; pdu[12]=0x01; pdu[13]=0x0F; pdu[14]=0x00;
    uint8_t info[18];
    memcpy(info, DLMS_LLC, 3); memcpy(info+3, pdu, 15);
    hdlc_build(DLMS_SERVER_ADDR, dlms_client, dlms_next_ctrl(), info, 18);
    if (!dlms_txrx(5000)) return false;
    size_t plen; const uint8_t* resp = dlms_find_pdu(&plen);
    if (!resp || plen < 4) return false;
    return (resp[0] == 0xC7 && resp[3] == 0x00);
}
