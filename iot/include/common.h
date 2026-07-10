#pragma once
/**
 * common.h — Umumiy app framework (barcha sensor turlari uchun)
 *
 * WiFi (quick-connect + WiFiManager)
 * HTTP GET/POST (X-Device-Token header bilan)
 * NVS config (server URL, device token)
 * Server health check + OTA
 * Backend API: register, send_status, poll_commands
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include <esp_wifi.h>

// ═══════════════════════════════════════════════════════════════════════════════
// NVS Config
// ═══════════════════════════════════════════════════════════════════════════════
#define CFG_SERVER_LEN   100
#define CFG_TOKEN_LEN     64
#define CFG_SERIAL_LEN    32   // Hisoblagich seriya raqami (NVS da saqlanadi)

struct AppConfig {
    char server_url[CFG_SERVER_LEN];
    char device_token[CFG_TOKEN_LEN];
    char meter_serial[CFG_SERIAL_LEN];  // Oxirgi ma'lum seriya — WiFiManager da ko'rsatish uchun
};

static AppConfig g_cfg;
static Preferences g_prefs;

static void cfg_load() {
    // Compile-time default (platformio.ini BUILD_FLAGS orqali)
    strncpy(g_cfg.server_url, DEFAULT_SERVER_URL, CFG_SERVER_LEN - 1);
#ifdef DEFAULT_DEVICE_TOKEN
    strncpy(g_cfg.device_token, DEFAULT_DEVICE_TOKEN, CFG_TOKEN_LEN - 1);
#else
    g_cfg.device_token[0] = '\0';
#endif
    g_cfg.meter_serial[0] = '\0';

    // NVS dan yuklash (WiFiManager orqali saqlangan qiymatlar ustunlik qiladi)
    g_prefs.begin("app", true);
    g_prefs.getString("srv", g_cfg.server_url,    CFG_SERVER_LEN);
    g_prefs.getString("tok", g_cfg.device_token,  CFG_TOKEN_LEN);
    g_prefs.getString("msr", g_cfg.meter_serial,  CFG_SERIAL_LEN);
    g_prefs.end();

    // http:// yo'q bo'lsa qo'shish
    if (strncmp(g_cfg.server_url, "http", 4) != 0) {
        char tmp[CFG_SERVER_LEN];
        strncpy(tmp, g_cfg.server_url, CFG_SERVER_LEN - 1);
        snprintf(g_cfg.server_url, CFG_SERVER_LEN, "http://%s", tmp);
    }
    // Eski :8001 portni olib tashlash
    char* p = strstr(g_cfg.server_url, ":8001");
    if (p) memmove(p, p + 5, strlen(p + 5) + 1);
}

static void cfg_save(const char* srv, const char* tok) {
    if (srv && srv[0]) strncpy(g_cfg.server_url,   srv, CFG_SERVER_LEN - 1);
    if (tok && tok[0]) strncpy(g_cfg.device_token, tok, CFG_TOKEN_LEN  - 1);
    g_prefs.begin("app", false);
    g_prefs.putString("srv", g_cfg.server_url);
    if (g_cfg.device_token[0]) g_prefs.putString("tok", g_cfg.device_token);
    g_prefs.end();
}

// Per-device token ni NVS ga saqlash (register javobidan olinadi)
static void cfg_save_token(const char* tok) {
    if (!tok || !tok[0]) return;
    strncpy(g_cfg.device_token, tok, CFG_TOKEN_LEN - 1);
    g_prefs.begin("app", false);
    g_prefs.putString("tok", tok);
    g_prefs.end();
    Serial.println("Token saqlandi (per-device)");
}

// Hisoblagich seriya raqamini NVS ga saqlash
// (keyingi qayta ishga tushirishda WiFiManager da ko'rsatish uchun)
static void cfg_save_meter_serial(const char* serial) {
    if (!serial || !serial[0]) return;
    strncpy(g_cfg.meter_serial, serial, CFG_SERIAL_LEN - 1);
    g_prefs.begin("app", false);
    g_prefs.putString("msr", serial);
    g_prefs.end();
}

// ═══════════════════════════════════════════════════════════════════════════════
// WiFi
// ═══════════════════════════════════════════════════════════════════════════════
static void wifi_quick(const char* ssid, const char* pass) {
    WiFi.begin(ssid, pass);
    unsigned long t = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t < 8000) delay(300);
}

// WiFi radio to'xtatish (RS-485 RF interferensiyasidan himoya)
static void wifi_pause() {
    esp_wifi_stop();
    delay(80);
}

// WiFi radio qayta yoqish va ulanishni kutish
static bool wifi_resume() {
    esp_wifi_start();
    WiFi.reconnect();
    unsigned long t = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t < 8000) delay(300);
    return WiFi.status() == WL_CONNECTED;
}

// WiFiManager orqali sozlash
// device_info: Serial monitorga chiqariladigan qurilma ma'lumoti (serial raqam)
static void wifi_setup(const char* ap_name, const char* ap_pass,
                       const char* device_mac = "",
                       const char* meter_serial = "") {

    // Parametr label va placeholder matnlari
    // Custom HTML: qurilma MAC va serial ko'rsatish
    char info_html[320];
    snprintf(info_html, sizeof(info_html),
        "<p style='background:#1e293b;border:1px solid #334155;border-radius:8px;"
        "padding:10px;font-size:12px;color:#94a3b8;margin-bottom:8px'>"
        "<b style='color:#60a5fa'>Qurilma ID:</b> %s<br>"
        "<b style='color:#60a5fa'>Hisoblagich:</b> %s<br>"
        "<small>Bu ma'lumotlarni dashboard da qurilmangizni topish uchun ishlating</small>"
        "</p>",
        device_mac[0] ? device_mac : "aniqlanmoqda...",
        meter_serial[0] ? meter_serial : "aniqlanmoqda..."
    );

    WiFiManagerParameter p_info(info_html);
    WiFiManagerParameter p_srv("server",
        "Server manzili (masalan: http://67.205.171.93)",
        g_cfg.server_url, 99);
    WiFiManagerParameter p_tok("token",
        "API token (admin beradi — bo'sh qoldirsa ochiq rejim)",
        g_cfg.device_token, 63);

    WiFiManager wm;
    wm.setTitle("Meter Monitor — Sozlash");
    wm.addParameter(&p_info);
    wm.addParameter(&p_srv);
    wm.addParameter(&p_tok);
    wm.setConnectTimeout(20);
    wm.setConfigPortalTimeout(180);
    wm.setSaveConfigCallback([&]() {
        cfg_save(p_srv.getValue(), p_tok.getValue());
        Serial.printf("Config saqlandi: %s\n", g_cfg.server_url);
    });

    // Custom AP sahifasi sarlavhasi
    wm.setCustomHeadElement(
        "<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0}"
        ".wrap{background:#1e293b;border-radius:12px}"
        "input{background:#0f172a!important;color:#e2e8f0!important;border:1px solid #334155!important}"
        "button{background:#3b82f6!important}</style>"
    );

    wm.autoConnect(ap_name, ap_pass);

    if (WiFi.status() == WL_CONNECTED) {
        WiFi.setSleep(false);
        Serial.printf("WiFi: %s (%d dBm)\n",
            WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else {
        Serial.println("WiFi: offline rejim");
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// HTTP (X-Device-Token header avtomatik qo'shiladi)
// ═══════════════════════════════════════════════════════════════════════════════
static bool http_post(const char* path, const String& body) {
    if (WiFi.status() != WL_CONNECTED) return false;
    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s%s", g_cfg.server_url, path);
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http.setTimeout(8000);
    int code = http.POST(body);
    http.end();
    return code >= 200 && code < 300;
}

static String http_get(const char* path) {
    if (WiFi.status() != WL_CONNECTED) return "";
    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s%s", g_cfg.server_url, path);
    http.begin(url);
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http.setTimeout(5000);
    int code = http.GET();
    String resp = (code == 200) ? http.getString() : "";
    http.end();
    return resp;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Server health check
// ═══════════════════════════════════════════════════════════════════════════════
static bool server_check() {
    if (WiFi.status() != WL_CONNECTED) return false;
    HTTPClient http;
    char url[120];
    snprintf(url, sizeof(url), "%s/health", g_cfg.server_url);
    http.begin(url);
    http.setTimeout(8000);
    int code = http.GET();
    http.end();
    if (code > 0) {
        Serial.printf("Server: OK (HTTP %d)\n", code);
        return true;
    }
    const char* r = "noma'lum";
    if      (code == -1)  r = "ulanmadi (REFUSED)";
    else if (code == -11) r = "timeout";
    else if (code == -4)  r = "WiFi yo'q";
    Serial.printf("Server: XATO (kod=%d, %s)\n", code, r);
    return false;
}

// ═══════════════════════════════════════════════════════════════════════════════
// OTA
// ═══════════════════════════════════════════════════════════════════════════════
static void ota_check(const char* device_id, const char* fw_version) {
    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s/api/ota/check/%s?current_version=%s",
             g_cfg.server_url, device_id, fw_version);
    http.begin(url);
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http.setTimeout(5000);
    int code = http.GET();
    if (code != 200) { http.end(); return; }
    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, http.getString())) { http.end(); return; }
    http.end();
    if (!doc["update"].as<bool>()) return;
    String fw_url = String(g_cfg.server_url) + doc["url"].as<String>();
    Serial.printf("OTA: v%s → yangilash...\n", doc["version"].as<const char*>());
    HTTPClient fw_http;
    fw_http.begin(fw_url);
    if (httpUpdate.update(fw_http) == HTTP_UPDATE_OK) ESP.restart();
}

// ═══════════════════════════════════════════════════════════════════════════════
// Backend API: Register
// Muvaffaqiyatli bo'lsa server per-device token qaytarishi mumkin → NVS ga
// ═══════════════════════════════════════════════════════════════════════════════
static bool app_register(const char* device_id,
                          const char* utility_type,  // "electricity", "water", "gas"
                          const char* meter_type,    // "te71", "te73", "water_v1"
                          const char* meter_serial,
                          const char* fw_version,
                          int baud_rate) {
    if (WiFi.status() != WL_CONNECTED) return false;

    StaticJsonDocument<384> doc;
    doc["device_id"]        = device_id;
    doc["utility_type"]     = utility_type;
    doc["meter_type"]       = meter_type;
    doc["meter_serial"]     = meter_serial;
    doc["software_version"] = fw_version;
    doc["baud_rate"]        = baud_rate;
    doc["ip"]               = WiFi.localIP().toString();
    doc["rssi"]             = WiFi.RSSI();
    doc["chip_model"]       = "ESP32";
    String body;
    serializeJson(doc, body);

    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s/api/register", g_cfg.server_url);
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http.setTimeout(8000);
    int code = http.POST(body);

    bool ok = (code == 200 || code == 201);
    if (ok) {
        // Server per-device token qaytarsa → NVS ga saqlash
        StaticJsonDocument<256> resp;
        if (!deserializeJson(resp, http.getString())) {
            const char* new_tok = resp["device_token"];
            if (new_tok && new_tok[0]) cfg_save_token(new_tok);
        }
        Serial.printf("Ro'yxatdan o'tildi: %s (%s)\n", device_id, meter_type);
    } else {
        Serial.printf("Register xato: HTTP %d\n", code);
    }
    http.end();
    return ok;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Backend API: Device status
// DeviceStatus sxemasi: device_id, ip, rssi, online, software_version
// ═══════════════════════════════════════════════════════════════════════════════
static void app_send_status(const char* device_id, const char* fw_version) {
    StaticJsonDocument<192> doc;
    doc["device_id"]        = device_id;
    doc["software_version"] = fw_version;
    doc["ip"]               = WiFi.localIP().toString();
    doc["rssi"]             = WiFi.RSSI();
    doc["online"]           = true;
    String body;
    serializeJson(doc, body);
    http_post("/api/device-status", body);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Backend API: Command polling
// pending_relay: 0=yo'q, 1=relay_off, 2=relay_on
// ═══════════════════════════════════════════════════════════════════════════════
static void app_poll_commands(const char* device_id, int* pending_relay) {
    char path[80];
    snprintf(path, sizeof(path), "/api/commands/%s", device_id);
    String resp = http_get(path);
    if (resp.isEmpty()) return;

    StaticJsonDocument<512> doc;
    if (deserializeJson(doc, resp)) return;

    for (JsonObject cmd : doc["commands"].as<JsonArray>()) {
        int id = cmd["id"];
        const char* action = cmd["action"];
        if (!action) continue;

        char ack[80];
        snprintf(ack, sizeof(ack), "/api/commands/%d/ack", id);

        if (strcmp(action, "reboot") == 0) {
            http_post(ack, "{}");
            Serial.println("Cmd: reboot");
            delay(200);
            ESP.restart();
        } else if (strcmp(action, "relay_on") == 0) {
            *pending_relay = 2;   // Keyingi DLMS session da bajariladi
            http_post(ack, "{}");
            Serial.println("Cmd: relay_on navbatga olindi");
        } else if (strcmp(action, "relay_off") == 0) {
            *pending_relay = 1;
            http_post(ack, "{}");
            Serial.println("Cmd: relay_off navbatga olindi");
        } else {
            // Noma'lum command — ack qilib o'tkazib yuborish
            http_post(ack, "{}");
            Serial.printf("Cmd: noma'lum '%s' — o'tkazildi\n", action);
        }
    }
}
