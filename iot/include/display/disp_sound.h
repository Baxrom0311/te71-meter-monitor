#pragma once
/**
 * display/disp_sound.h — LCD display moduli ovoz sensori uchun
 *
 * Standart 3-funksiya interfeysi:
 *   disp_init()                    → lcd_init() + "Kalibrovka..." (sensor_init dan oldin)
 *   disp_show_reading(d)           → 0-qator: "Ovoz:   45.3 %" yoki "Ovoz:     -- %"
 *   disp_show_status(wifi, srv, l) → 1-qator: "W:OK S:OK L:--"
 *
 * Talab: SensorData from sensors/sound.h (float level, bool valid)
 */

#include "display/lcd.h"

static void disp_init() {
    lcd_init();
    lcd_row(0, "Ovoz Sensori");
    lcd_row(1, "Kalibrovka...");  // sensor_init() 5s kalibrovka qiladi
}

static void disp_show_reading(const SensorData& d) {
    char row0[LCD_COLS + 1];
    if (d.valid)
        snprintf(row0, sizeof(row0), "Ovoz: %6.1f %%", d.level);
    else
        snprintf(row0, sizeof(row0), "Ovoz:      -- %%");
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
