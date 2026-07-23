#pragma once
/**
 * display/disp_sound.h — LCD 16x2 ovoz sensori uchun
 *
 * 0-qator: "Ovoz:  12.3 %"
 * 1-qator: "W:OK S:OK"
 *
 * Faqat o'zgargan bo'lsa LCD ga yozadi (titrash yo'q, I2C trafik kam)
 */

#include "display/lcd.h"

static char _disp_row0[LCD_COLS + 1] = "";
static char _disp_row1[LCD_COLS + 1] = "";

static void disp_init() {
    lcd_init();
    lcd_row(0, "Ovoz Sensori");
    lcd_row(1, "Yuklanmoqda...");
}

static void disp_show_reading(const SensorData& d) {
    char buf[LCD_COLS + 1];
    if (d.valid)
        snprintf(buf, sizeof(buf), "Ovoz: %5.1f %%", d.level);
    else
        snprintf(buf, sizeof(buf), "Ovoz:    -- %%");

    if (strcmp(buf, _disp_row0) != 0) {
        lcd_row(0, buf);
        strncpy(_disp_row0, buf, sizeof(_disp_row0) - 1);
        _disp_row0[sizeof(_disp_row0) - 1] = '\0';
    }
}

static void disp_show_status(bool wifi_ok, bool srv_ok, bool) {
    char buf[LCD_COLS + 1];
    snprintf(buf, sizeof(buf), "W:%-2s S:%-2s",
             wifi_ok ? "OK" : "--",
             srv_ok  ? "OK" : "--");

    if (strcmp(buf, _disp_row1) != 0) {
        lcd_row(1, buf);
        strncpy(_disp_row1, buf, sizeof(_disp_row1) - 1);
        _disp_row1[sizeof(_disp_row1) - 1] = '\0';
    }
}
