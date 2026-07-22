#pragma once
/**
 * display/disp_elec.h — LCD display module for electricity sensor
 *
 * Thin wrapper around electricity.h's existing LCD functions.
 * electricity.h's sensor_init() already initialises the LCD and
 * sensor_read() already calls lcd_show_electricity() internally,
 * so only disp_show_status() has real work to do here.
 *
 * Implements the standard 3-function display interface:
 *   disp_init()                       → no-op (electricity.h sensor_init() handles LCD)
 *   disp_show_reading(d)              → no-op (electricity.h sensor_read() calls lcd_show_electricity())
 *   disp_show_status(wifi, srv, lora) → formats "W:OK S:OK L:--" and calls lcd_show_status()
 *
 * Requires: g_elec_lcd_ok, elec_lcd_row(), lcd_show_status() from sensors/electricity.h
 */

static inline void disp_init() {
    // electricity.h's sensor_init() initialises and drives the LCD.
    // Nothing to do here.
}

static inline void disp_show_reading(const SensorData& /*d*/) {
    // electricity.h's sensor_read() calls lcd_show_electricity(d) internally.
    // Nothing to do here.
}

static void disp_show_status(bool wifi_ok, bool srv_ok, bool lora_ok) {
    char s[ELEC_LCD_COLS + 1];
    snprintf(s, sizeof(s), "W:%-2s S:%-2s L:%-2s",
             wifi_ok ? "OK" : "--",
             srv_ok  ? "OK" : "--",
             lora_ok ? "OK" : "--");
    lcd_show_status(s);
}
