#pragma once
/**
 * display/lcd.h — LCD 16x2 I2C driver
 *
 * Override: -DLCD_SDA=21  -DLCD_SCL=22  -DLCD_ADDR=0x27
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#ifndef LCD_ADDR
  #define LCD_ADDR  0x27
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
static unsigned long g_lcd_last_refresh = 0;

static void lcd_init() {
    Wire.begin(LCD_SDA, LCD_SCL);
    g_lcd.init();
    g_lcd.backlight();
    g_lcd.clear();
    g_lcd_ok = true;
    g_lcd_last_refresh = millis();
    LOG_PRINTF("  LCD 16x2 I2C (0x%02X, SDA=%d, SCL=%d): OK\n",
               LCD_ADDR, LCD_SDA, LCD_SCL);
}

// Har 60s da LCD ni qayta init (qotib qolishdan himoya)
static void lcd_refresh_if_needed() {
    if (!g_lcd_ok) return;
    if (millis() - g_lcd_last_refresh >= 60000) {
        g_lcd_last_refresh = millis();
        g_lcd.init();
        g_lcd.backlight();
    }
}

static void lcd_row(uint8_t row, const char* text) {
    if (!g_lcd_ok) return;
    lcd_refresh_if_needed();
    char buf[LCD_COLS + 1];
    snprintf(buf, sizeof(buf), "%-*s", LCD_COLS, text);
    g_lcd.setCursor(0, row);
    g_lcd.print(buf);
}
