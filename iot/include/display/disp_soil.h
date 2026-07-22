#pragma once
/**
 * display/disp_soil.h — LCD display module for soil moisture sensor
 *
 * Implements the standard 3-function display interface:
 *   disp_init()                    → lcd_init() + splash screen
 *   disp_show_reading(d)           → row 0: "Namlik:  55.0 %" or "Namlik:    -- %"
 *   disp_show_status(wifi, srv, lora) → row 1: "W:OK S:OK L:--"
 *
 * Requires: SensorData from sensors/soil.h (has float humidity, bool valid)
 */

#include "display/lcd.h"

static void disp_init() {
    lcd_init();
    lcd_row(0, "Meter Monitor");
    lcd_row(1, "WiFi ulanoqda..");
}

static void disp_show_reading(const SensorData& d) {
    char row0[LCD_COLS + 1];
    if (d.valid)
        snprintf(row0, sizeof(row0), "Namlik: %5.1f %%", d.humidity);
    else
        snprintf(row0, sizeof(row0), "Namlik:    -- %%");
    lcd_row(0, row0);
}

static void disp_show_status(bool wifi_ok, bool srv_ok, bool lora_ok) {
    char s[LCD_COLS + 1];
    snprintf(s, sizeof(s), "W:%-2s S:%-2s L:%-2s",
             wifi_ok ? "OK" : "--",
             srv_ok  ? "OK" : "--",
             lora_ok ? "OK" : "--");
    lcd_row(1, s);
}
