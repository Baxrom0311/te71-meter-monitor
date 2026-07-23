#pragma once
/**
 * core/wifi.h — WiFi boshqaruvi (non-blocking)
 *
 * wifi_quick()   — Setup: tez ulanish
 * wifi_setup()   — Setup: WiFiManager portal
 * wifi_loop()    — Loop: non-blocking qayta ulanish
 * wifi_pause()   — RS-485 uchun radio to'xtatish
 * wifi_resume()  — Radio qayta yoqish
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <esp_wifi.h>
#include "core/log.h"
#include "core/config.h"

#define WIFI_RECONNECT_MS  15000UL

static unsigned long _wifi_reconnect_ms = 0;

static void wifi_quick(const char* ssid, const char* pass) {
    WiFi.mode(WIFI_STA);
    WiFi.begin();
    unsigned long t = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t < 6000) yield();
    if (WiFi.status() == WL_CONNECTED) return;
    WiFi.disconnect(true);
    t = millis(); while (millis() - t < 300) yield();
    WiFi.begin(ssid, pass);
    t = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t < 10000) yield();
}

// Non-blocking — faqat reconnect buyrug'i, blokirovka yo'q
static void wifi_loop() {
    if (WiFi.status() == WL_CONNECTED) return;
    unsigned long now = millis();
    if (now - _wifi_reconnect_ms < WIFI_RECONNECT_MS) return;
    _wifi_reconnect_ms = now;
    WiFi.reconnect();
    LOG_PRINTLN("WiFi: qayta ulanish...");
}

static void wifi_pause() {
    esp_wifi_stop();
    unsigned long t = millis();
    while (millis() - t < 80) yield();
}

static bool wifi_resume() {
    esp_wifi_start();
    WiFi.reconnect();
    unsigned long t = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t < 3000) yield();
    return WiFi.status() == WL_CONNECTED;
}

static void wifi_setup(const char* ap_name, const char* ap_pass,
                       const char* device_mac = "",
                       const char* meter_serial = "") {
    char info_html[320];
    snprintf(info_html, sizeof(info_html),
        "<p style='background:#1e293b;border:1px solid #334155;border-radius:8px;"
        "padding:10px;font-size:12px;color:#94a3b8;margin-bottom:8px'>"
        "<b style='color:#60a5fa'>ID:</b> %s<br>"
        "<b style='color:#60a5fa'>Meter:</b> %s<br>"
        "<b style='color:#60a5fa'>Rejim:</b> %s</p>",
        device_mac[0] ? device_mac : "...",
        meter_serial[0] ? meter_serial : "...",
        g_cfg.test_mode ? "TEST" : "PROD"
    );

    WiFiManagerParameter p_info(info_html);
    WiFiManagerParameter p_srv("server", "Server URL", g_cfg.server_url, 99);
    WiFiManagerParameter p_tok("token", "API token", g_cfg.device_token, 63);
    WiFiManagerParameter p_prov("prov_token", "Provisioning Token", g_cfg.provisioning_token, 63);
    WiFiManagerParameter p_mode("mode", "Rejim: prod/test", g_cfg.test_mode ? "test" : "prod", 8);

    WiFiManager wm;
    wm.setTitle("Meter Monitor");
    wm.addParameter(&p_info);
    wm.addParameter(&p_srv);
    wm.addParameter(&p_tok);
    wm.addParameter(&p_prov);
    wm.addParameter(&p_mode);
    wm.setConnectTimeout(20);
    wm.setConfigPortalTimeout(180);
    wm.setSaveConfigCallback([&]() {
        cfg_save(p_srv.getValue(), p_tok.getValue(),
                 p_mode.getValue(), p_prov.getValue());
    });
    wm.setCustomHeadElement(
        "<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0}"
        ".wrap{background:#1e293b;border-radius:12px}"
        "input{background:#0f172a!important;color:#e2e8f0!important;"
        "border:1px solid #334155!important}"
        "button{background:#3b82f6!important}</style>"
    );

    wm.autoConnect(ap_name, ap_pass);

    if (WiFi.status() == WL_CONNECTED) {
        WiFi.setSleep(false);
        LOG_PRINTF("WiFi: %s (%ddBm)\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else {
        LOG_PRINTLN("WiFi: offline");
    }
}
