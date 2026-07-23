#pragma once
/**
 * core/api.h — Backend API (register, status, commands)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include "core/log.h"
#include "core/config.h"
#include "core/http.h"

extern void sensor_set_volume(float val);

static bool app_register(const char* device_id,
                          const char* utility_type,
                          const char* meter_type,
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
    if (g_cfg.test_mode) doc["is_test_device"] = true;
    if (g_cfg.provisioning_token[0])
        doc["provisioning_token"] = g_cfg.provisioning_token;
    String body;
    serializeJson(doc, body);

    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s/api/register", g_cfg.server_url);
    if (!http_begin_url(http, url)) return false;
    http.addHeader("Content-Type", "application/json");
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http.setTimeout(5000);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    int code = http.POST(body);

    bool ok = (code == 200 || code == 201);
    if (ok) {
        StaticJsonDocument<256> resp;
        String reg_body = http_safe_body(http);
        if (reg_body.length() > 0 && !deserializeJson(resp, reg_body)) {
            const char* new_tok = resp["device_token"];
            if (new_tok && new_tok[0]) {
                cfg_save_token(new_tok);
                if (g_cfg.provisioning_token[0]) {
                    g_cfg.provisioning_token[0] = '\0';
                    g_prefs.begin("app", false);
                    g_prefs.remove("prv");
                    g_prefs.end();
                }
            }
        }
    } else {
        LOG_PRINTF("Register: %d\n", code);
        if (code == 401) {
            strncpy(g_cfg.device_token, DEFAULT_DEVICE_TOKEN, CFG_TOKEN_LEN - 1);
            g_cfg.device_token[CFG_TOKEN_LEN - 1] = '\0';
            g_prefs.begin("app", false);
            g_prefs.remove("tok");
            if (g_cfg.provisioning_token[0]) {
                g_cfg.provisioning_token[0] = '\0';
                g_prefs.remove("prv");
            }
            g_prefs.end();
        }
    }
    http.end();
    return ok;
}

static void app_send_status(const char* device_id, const char* fw_version) {
    StaticJsonDocument<512> doc;
    doc["device_id"]        = device_id;
    doc["software_version"] = fw_version;
    doc["ip"]               = WiFi.localIP().toString();
    doc["rssi"]             = WiFi.RSSI();
    doc["online"]           = true;

    // Diagnostika
    doc["heap_free"]        = ESP.getFreeHeap();
    doc["uptime_s"]         = (uint32_t)(millis() / 1000);
    doc["sensor_errors"]    = g_diag_sensor_errors;
    doc["wifi_drops"]       = g_diag_wifi_drops;
    doc["read_interval_ms"] = g_cfg.read_interval_ms;
    if (g_diag_last_error[0])
        doc["last_error"] = g_diag_last_error;

    String body;
    serializeJson(doc, body);
    http_post("/api/device-status", body);
}

static void app_poll_commands(const char* device_id, int* pending_relay) {
    char path[80];
    snprintf(path, sizeof(path), "/api/commands/%s", device_id);
    String resp = http_get(path);
    if (resp.isEmpty()) return;

    StaticJsonDocument<1024> doc;
    if (deserializeJson(doc, resp)) return;

    for (JsonObject cmd : doc["commands"].as<JsonArray>()) {
        int id = cmd["id"];
        const char* action = cmd["action"];
        if (!action) continue;

        char ack[80];
        snprintf(ack, sizeof(ack), "/api/commands/%d/ack", id);

        if (strcmp(action, "reboot") == 0) {
            http_post(ack, "{}");
            ESP.restart();
        } else if (strcmp(action, "relay_on") == 0) {
            if (pending_relay) *pending_relay = 2;
            http_post(ack, "{}");
        } else if (strcmp(action, "relay_off") == 0) {
            if (pending_relay) *pending_relay = 1;
            http_post(ack, "{}");
        } else if (strcmp(action, "set_volume") == 0) {
            float val = cmd["params"]["volume"].as<float>();
            sensor_set_volume(val);
            http_post(ack, "{\"ok\":true}");
        } else if (strcmp(action, "set_interval") == 0) {
            uint32_t val = cmd["params"]["interval_ms"] | (uint32_t)0;
            if (val >= 5000 && val <= 3600000) {
                cfg_save_interval(val);
                http_post(ack, "{\"ok\":true}");
            } else {
                http_post(ack, "{\"error\":\"interval 5s-3600s\"}");
            }
        } else if (strcmp(action, "set_server") == 0) {
            const char* url = cmd["params"]["url"];
            if (url && strlen(url) > 8) {
                cfg_save_server(url);
                http_post(ack, "{\"ok\":true,\"reboot\":true}");
                ESP.restart();
            } else {
                http_post(ack, "{\"error\":\"invalid url\"}");
            }
        } else if (strcmp(action, "set_test_mode") == 0) {
            bool val = cmd["params"]["enabled"] | false;
            cfg_save_test_mode(val);
            http_post(ack, "{\"ok\":true}");
        } else {
            http_post(ack, "{}");
        }
    }
}
