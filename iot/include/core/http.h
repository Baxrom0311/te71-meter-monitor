#pragma once
/**
 * core/http.h — HTTP yordamchi + server check + OTA
 *
 * TLS: ISRG Root X1 (Let's Encrypt) sertifikati orqali tekshiriladi.
 *       -DTLS_INSECURE → sertifikat tekshirilmaydi (faqat debug)
 *
 * OTA: Watchdog to'xtatiladi, yuklanadi, firmware tasdiqlanadi.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <ArduinoJson.h>
#include "core/log.h"
#include "core/config.h"

// ─── TLS sertifikat (ISRG Root X1 — Let's Encrypt, 2035 gacha) ──────────────
#ifndef TLS_INSECURE
static const char TLS_ROOT_CA[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6
UA5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+s
WT8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qy
HB5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+U
CvdHEaJ6JSrjkMzMIkBjUMhKdH+BuRCObFy2yDDoDkjn/33m/aMyCyAM1PVHPhIE
vGP7w26fJoIEdp9O7KpXf1Jjj+O9v2p4EFyMp0WaWc+4HPBpblXn/7y/rkX/AoT+
/kUJe+SZIF7VIrZ4XvJRxCJaGiUyFqrZ5H7hFDcOFPJgKyOavXGvZbCIFbVODqGe
j/qh+86ntjjdh/p3RjTvql+3NVf2kG3aNj/TtHPhvCVlRALNs25Dk5P0PSPeA9k5
e8V4RFVWBG4tCdp2+rSZEBLxOhXPQcfX3K32SCRRSk1oAYi4vO2KraCxMpxkLsab
7HyNzLcnKjFmKFhwH+JPOSP0wNXLAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAP
BgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjAN
BgkqhkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V
9lZLubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk
6ZGQ3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcO
j/KKNFtY2PwByVS5uCbMiogZiUvsNm+K+PY/2jUBhK9CuOK1bZCBxSIpwfHnL3r/
GVTskbYuOP6san1jUEsmp3vtuMIv/zEjZ3hyAr/0lmluAXSwLw3RQFRkXV9MzLTnf
N7TQLY8lBMpmHuEOnTRkfp6Dw+p7WoL4NMM/LxVQJBjOxhGKx9/qB0BO0ODB5nx
BNHBH6ozmYHo3aZPjPHaXJtFC2jbNUG+gg6Mo3bwU+hA9gCa9FuK8EBxPyL2JOH0
Jlk/Pl6UMR8CUBKEbNQ2jI2C/u1DOdcl3v6D9sj5p0UGe2oHYA4TwXpK8w6VjJHF
MXuKTCOhQWFW+kQ7MAfqaBcixS6YH3dg2JN1sXpHOqHlRI7mIFVLMfVl4/9stSe/
sFzLel0pUg//clO5aCJ3JZ5yiUt5qP3zEvFcpHE15CWkPTNSl0wQaDclGQRH5dVN
+VbDaYmFKGBu0HVQz9xSf7ACZA0MSOH4P/sftaXTbH/v3vlDQnY5j/j1Bqasbfb
OW0=
-----END CERTIFICATE-----
)EOF";
#endif  // TLS_INSECURE

static WiFiClientSecure g_secure_client;

static bool http_begin_url(HTTPClient& http, const char* url) {
    if (strncmp(url, "https://", 8) == 0) {
#ifdef TLS_INSECURE
        g_secure_client.setInsecure();
#else
        g_secure_client.setCACert(TLS_ROOT_CA);
#endif
        return http.begin(g_secure_client, url);
    }
    return http.begin(url);
}

// HTTP javob hajmi limiti (default: 4KB — heap himoyasi)
#ifndef HTTP_MAX_RESPONSE
  #define HTTP_MAX_RESPONSE  4096
#endif

static void http_prepare(HTTPClient& http, uint16_t timeout_ms) {
    http.setTimeout(timeout_ms);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
}

// Xavfsiz getString — hajm limitidan oshsa bo'sh qaytaradi
static String http_safe_body(HTTPClient& http) {
    int len = http.getSize();
    if (len > HTTP_MAX_RESPONSE) {
        LOG_PRINTF("HTTP: javob juda katta (%d > %d) — o'tkazib yuborildi\n",
                   len, HTTP_MAX_RESPONSE);
        return "";
    }
    // Content-Length yo'q bo'lsa (-1), chunked transfer — stream dan o'qish
    if (len < 0) {
        String body = http.getString();
        if ((int)body.length() > HTTP_MAX_RESPONSE) {
            LOG_PRINTF("HTTP: chunked javob juda katta (%d)\n", (int)body.length());
            return "";
        }
        return body;
    }
    return http.getString();
}

static bool http_post(const char* path, const String& body) {
    if (WiFi.status() != WL_CONNECTED) return false;
    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s%s", g_cfg.server_url, path);
    if (!http_begin_url(http, url)) return false;
    http.addHeader("Content-Type", "application/json");
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http.setTimeout(5000);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    int code = http.POST(body);
    if (code < 200 || code >= 300)
        LOG_PRINTF("POST %s: %d %s\n", path, code, http_safe_body(http).c_str());
    http.end();
    return code >= 200 && code < 300;
}

static String http_get(const char* path) {
    if (WiFi.status() != WL_CONNECTED) return "";
    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s%s", g_cfg.server_url, path);
    if (!http_begin_url(http, url)) return "";
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http.setTimeout(5000);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    int code = http.GET();
    String resp = (code == 200) ? http_safe_body(http) : "";
    if (code < 200 || code >= 300)
        LOG_PRINTF("GET %s: %d\n", path, code);
    http.end();
    return resp;
}

static bool server_check() {
    if (WiFi.status() != WL_CONNECTED) return false;
    HTTPClient http;
    char url[120];
    snprintf(url, sizeof(url), "%s/health", g_cfg.server_url);
    if (!http_begin_url(http, url)) return false;
    http.setTimeout(5000);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    int code = http.GET();
    http.end();
    return code >= 200 && code < 300;
}

static void ota_check(const char* device_id, const char* fw_version) {
    HTTPClient http;
    char url[220];
    snprintf(url, sizeof(url), "%s/api/ota/check/%s?current_version=%s",
             g_cfg.server_url, device_id, fw_version);
    if (!http_begin_url(http, url)) return;
    if (g_cfg.device_token[0])
        http.addHeader("X-Device-Token", g_cfg.device_token);
    http.setTimeout(5000);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    int code = http.GET();
    if (code != 200) { http.end(); return; }
    StaticJsonDocument<256> doc;
    String ota_resp = http_safe_body(http);
    if (ota_resp.isEmpty() || deserializeJson(doc, ota_resp)) { http.end(); return; }
    http.end();
    if (!doc["update"].as<bool>()) return;
    String fw_url = String(g_cfg.server_url) + doc["url"].as<String>();
    LOG_PRINTF("OTA: v%s yuklanmoqda...\n", doc["version"].as<const char*>());

    // Watchdog to'xtatish (OTA uzoq davom etishi mumkin)
    wdt_pause();

    if (fw_url.startsWith("https://")) {
        WiFiClientSecure fw_client;
#ifdef TLS_INSECURE
        fw_client.setInsecure();
#else
        fw_client.setCACert(TLS_ROOT_CA);
#endif
        if (httpUpdate.update(fw_client, fw_url) == HTTP_UPDATE_OK) ESP.restart();
    } else {
        HTTPClient fw_http;
        fw_http.begin(fw_url);
        if (httpUpdate.update(fw_http) == HTTP_UPDATE_OK) ESP.restart();
    }

    // OTA muvaffaqiyatsiz bo'ldi — watchdog qaytarish
    LOG_PRINTLN("OTA: yuklash xato!");
    wdt_resume();
}
