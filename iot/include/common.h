#pragma once
/**
 * common.h — Umumiy framework (barcha WiFi-li sensorlar uchun)
 *
 * Modular tarkib:
 *   core/log.h    — Debug logging
 *   core/config.h — NVS konfiguratsiya
 *   core/wifi.h   — WiFi (non-blocking)
 *   core/http.h   — HTTP + server check + OTA
 *   core/api.h    — Backend API
 */

#include <esp_system.h>
#include <strings.h>

#include "core/log.h"
#include "core/config.h"
#include "core/diag.h"
#include "core/watchdog.h"
#include "core/wifi.h"
#include "core/http.h"
#include "core/api.h"
