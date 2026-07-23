#pragma once
/**
 * core/diag.h — Diagnostika va NTP vaqt sinxronlash
 *
 * Xato hisoblagichlar + NTP timestamp
 * Backend ga /api/device-status orqali yuboriladi.
 */

#include <Arduino.h>
#include <time.h>
#include "core/log.h"

// ─── Xato hisoblagichlar ──────────────────────────────────────────────────────
static uint16_t g_diag_sensor_errors = 0;
static uint16_t g_diag_wifi_drops    = 0;
static char     g_diag_last_error[64] = "";

static void diag_error(const char* msg) {
    strncpy(g_diag_last_error, msg, sizeof(g_diag_last_error) - 1);
    g_diag_last_error[sizeof(g_diag_last_error) - 1] = '\0';
    LOG_PRINTF("XATO: %s\n", msg);
}

// ─── NTP vaqt sinxronlash ─────────────────────────────────────────────────────
static void ntp_init() {
    configTime(0, 0, "pool.ntp.org", "time.google.com");  // UTC
    LOG_PRINTLN("NTP: sinxronlash boshlandi");
}

static bool ntp_valid() {
    return time(nullptr) > 1609459200;  // > 2021-01-01
}

// ISO 8601 UTC timestamp → "2025-01-15T14:30:00Z"
static bool diag_timestamp(char* buf, size_t len) {
    time_t now = time(nullptr);
    if (now < 1609459200) return false;
    struct tm* t = gmtime(&now);
    snprintf(buf, len, "%04d-%02d-%02dT%02d:%02d:%02dZ",
             t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
             t->tm_hour, t->tm_min, t->tm_sec);
    return true;
}
