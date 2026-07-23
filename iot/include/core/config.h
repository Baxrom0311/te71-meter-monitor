#pragma once
/**
 * core/config.h — NVS konfiguratsiya (AppConfig)
 *
 * Build flags orqali default qiymatlar:
 *   DEFAULT_SERVER_URL, DEFAULT_DEVICE_TOKEN, DEFAULT_TEST_MODE
 */

#include <Arduino.h>
#include <Preferences.h>
#include "core/log.h"

#define CFG_SERVER_LEN   100
#define CFG_TOKEN_LEN     64
#define CFG_SERIAL_LEN    32

struct AppConfig {
    char server_url[CFG_SERVER_LEN];
    char device_token[CFG_TOKEN_LEN];
    char provisioning_token[CFG_TOKEN_LEN];
    char meter_serial[CFG_SERIAL_LEN];
    bool test_mode;
    uint32_t read_interval_ms;   // Backend dan masofaviy o'zgartirish mumkin
};

static AppConfig g_cfg;
static Preferences g_prefs;

// ─── NVS xavfsiz yozish (xato tekshirish bilan) ─────────────────────────────
static bool _nvs_put_str(const char* key, const char* val) {
    size_t w = g_prefs.putString(key, val);
    if (w == 0) { LOG_PRINTF("NVS XATO: '%s' yozib bo'lmadi!\n", key); return false; }
    return true;
}
static bool _nvs_put_bool(const char* key, bool val) {
    size_t w = g_prefs.putBool(key, val);
    if (w == 0) { LOG_PRINTF("NVS XATO: '%s' yozib bo'lmadi!\n", key); return false; }
    return true;
}
static bool _nvs_put_ulong(const char* key, uint32_t val) {
    size_t w = g_prefs.putULong(key, val);
    if (w == 0) { LOG_PRINTF("NVS XATO: '%s' yozib bo'lmadi!\n", key); return false; }
    return true;
}

// NVS sog'lig'ini tekshirish (startup da)
static void nvs_health_check() {
    g_prefs.begin("app", true);  // read-only
    size_t free_entries = g_prefs.freeEntries();
    g_prefs.end();
    LOG_PRINTF("NVS: %d ta bo'sh yozuv\n", (int)free_entries);
    if (free_entries < 10) {
        LOG_PRINTLN("NVS OGOHLANTIRISH: bo'sh joy kam!");
    }
}

static void cfg_load() {
    strncpy(g_cfg.server_url, DEFAULT_SERVER_URL, CFG_SERVER_LEN - 1);
#ifdef DEFAULT_DEVICE_TOKEN
    strncpy(g_cfg.device_token, DEFAULT_DEVICE_TOKEN, CFG_TOKEN_LEN - 1);
#else
    g_cfg.device_token[0] = '\0';
#endif
    g_cfg.provisioning_token[0] = '\0';
    g_cfg.meter_serial[0] = '\0';
#ifdef DEFAULT_TEST_MODE
    g_cfg.test_mode = DEFAULT_TEST_MODE;
#else
    g_cfg.test_mode = false;
#endif

    // Default o'qish intervali (build flag dan)
#ifdef READ_INTERVAL_MS
    g_cfg.read_interval_ms = READ_INTERVAL_MS;
#else
    g_cfg.read_interval_ms = 30000UL;
#endif

    g_prefs.begin("app", true);
    g_prefs.getString("srv", g_cfg.server_url,          CFG_SERVER_LEN);
    g_prefs.getString("tok", g_cfg.device_token,        CFG_TOKEN_LEN);
    g_prefs.getString("prv", g_cfg.provisioning_token,  CFG_TOKEN_LEN);
    g_prefs.getString("msr", g_cfg.meter_serial,        CFG_SERIAL_LEN);
    g_cfg.test_mode = g_prefs.getBool("test", g_cfg.test_mode);
    g_cfg.read_interval_ms = g_prefs.getULong("rint", g_cfg.read_interval_ms);
    g_prefs.end();

    if (strncmp(g_cfg.server_url, "http", 4) != 0) {
        char tmp[CFG_SERVER_LEN];
        strncpy(tmp, g_cfg.server_url, CFG_SERVER_LEN - 1);
        snprintf(g_cfg.server_url, CFG_SERVER_LEN, "http://%s", tmp);
    }
    char* p = strstr(g_cfg.server_url, ":8001");
    if (p) memmove(p, p + 5, strlen(p + 5) + 1);
}

static bool cfg_parse_test_mode(const char* mode) {
    if (!mode) return false;
    return strcasecmp(mode, "test") == 0 ||
           strcmp(mode, "1") == 0 ||
           strcasecmp(mode, "true") == 0 ||
           strcasecmp(mode, "yes") == 0;
}

static void cfg_save(const char* srv, const char* tok,
                     const char* mode, const char* prv) {
    if (srv && srv[0]) strncpy(g_cfg.server_url, srv, CFG_SERVER_LEN - 1);
    if (tok) {
        strncpy(g_cfg.device_token, tok, CFG_TOKEN_LEN - 1);
        g_cfg.device_token[CFG_TOKEN_LEN - 1] = '\0';
    }
    if (prv) {
        strncpy(g_cfg.provisioning_token, prv, CFG_TOKEN_LEN - 1);
        g_cfg.provisioning_token[CFG_TOKEN_LEN - 1] = '\0';
    }
    g_cfg.test_mode = cfg_parse_test_mode(mode);
    g_prefs.begin("app", false);
    _nvs_put_str("srv", g_cfg.server_url);
    if (g_cfg.device_token[0]) _nvs_put_str("tok", g_cfg.device_token);
    else g_prefs.remove("tok");
    if (g_cfg.provisioning_token[0]) _nvs_put_str("prv", g_cfg.provisioning_token);
    else g_prefs.remove("prv");
    _nvs_put_bool("test", g_cfg.test_mode);
    g_prefs.end();
}

static void cfg_save_token(const char* tok) {
    if (!tok || !tok[0]) return;
    strncpy(g_cfg.device_token, tok, CFG_TOKEN_LEN - 1);
    g_prefs.begin("app", false);
    _nvs_put_str("tok", tok);
    g_prefs.end();
    LOG_PRINTLN("Token saqlandi (per-device)");
}

static void cfg_save_meter_serial(const char* serial) {
    if (!serial || !serial[0]) return;
    strncpy(g_cfg.meter_serial, serial, CFG_SERIAL_LEN - 1);
    g_prefs.begin("app", false);
    _nvs_put_str("msr", serial);
    g_prefs.end();
}

static void cfg_save_interval(uint32_t ms) {
    g_cfg.read_interval_ms = ms;
    g_prefs.begin("app", false);
    _nvs_put_ulong("rint", ms);
    g_prefs.end();
    LOG_PRINTF("Interval saqlandi: %lu ms\n", (unsigned long)ms);
}

static void cfg_save_server(const char* url) {
    if (!url || !url[0]) return;
    strncpy(g_cfg.server_url, url, CFG_SERVER_LEN - 1);
    g_cfg.server_url[CFG_SERVER_LEN - 1] = '\0';
    g_prefs.begin("app", false);
    _nvs_put_str("srv", url);
    g_prefs.end();
    LOG_PRINTF("Server saqlandi: %s\n", g_cfg.server_url);
}

static void cfg_save_test_mode(bool mode) {
    g_cfg.test_mode = mode;
    g_prefs.begin("app", false);
    _nvs_put_bool("test", mode);
    g_prefs.end();
    LOG_PRINTF("Test rejim: %s\n", mode ? "ON" : "OFF");
}
