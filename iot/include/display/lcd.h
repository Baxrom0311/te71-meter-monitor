#pragma once
/**
 * display/lcd.h — Generic LCD 16x2 I2C driver
 *
 * Provides lcd_init() and lcd_row(row, text).
 * Override via build flags:
 *   -DLCD_SDA=21  -DLCD_SCL=22  -DLCD_ADDR=0x27
 *
 * Used by disp_soil.h, disp_elec.h, etc.
 * Do NOT include directly in sensor headers.
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#ifndef LCD_ADDR
  #define LCD_ADDR  0x27   // Ko'pchilikda 0x27; ishlamasa 0x3F
#endif
#ifndef LCD_SDA
  #define LCD_SDA   21
#endif
#ifndef LCD_SCL
  #define LCD_SCL   22
#endif
#define LCD_COLS  16
#define LCD_ROWS   2

static LiquidCrystal_I2C g_lcd(LCD_ADDR, LCD_COLS, LCD_ROWS);
static bool g_lcd_ok = false;

static void lcd_row(uint8_t row, const char* text) {
    if (!g_lcd_ok) return;
    char buf[LCD_COLS + 1];
    snprintf(buf, sizeof(buf), "%-*s", LCD_COLS, text);
    g_lcd.setCursor(0, row);
    g_lcd.print(buf);
}

static void lcd_init() {
    Wire.begin(LCD_SDA, LCD_SCL);
    g_lcd.init();
    g_lcd.backlight();
    g_lcd_ok = true;
    LOG_PRINTF("  LCD 16x2 I2C (0x%02X, SDA=%d, SCL=%d): OK\n",
               LCD_ADDR, LCD_SDA, LCD_SCL);
}
