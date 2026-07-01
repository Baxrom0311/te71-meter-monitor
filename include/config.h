// =============================================================================
// TE71 RS-485 Diagnostic Tool - Configuration
// =============================================================================
//
// XAVFSIZLIK ESLATMALARI:
// - MAX485ESA 5V bilan ishlaydi, RO chiqishi ~4.8V
// - RO ESP32 GPIO16'ga TO'G'RIDAN-TO'G'RI ULANMAGAN
// - 10kΩ / 20kΩ kuchlanish bo'luvchi (voltage divider) ishlatilgan
// - A/B belgilari ayrim qurilmalarda TESKARI bo'lishi mumkin
// - Hisoblagichga faqat ma'lum read-only paket yuborish kerak
// - Tasodifiy paketlar tarif, vaqt yoki rele sozlamalariga ta'sir qilishi mumkin
// =============================================================================

#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// --- Pin konfiguratsiyasi ---
static constexpr uint8_t PIN_RS485_RX   = 16;  // UART2 RX <- MAX485 RO (divider orqali)
static constexpr uint8_t PIN_RS485_TX   = 17;  // UART2 TX -> MAX485 DI
static constexpr uint8_t PIN_RS485_DE_RE = 4;  // DE va /RE birlashtirilgan

// --- UART boshlang'ich sozlamalari ---
static constexpr uint32_t DEFAULT_BAUD_RATE   = 9600;
static constexpr uint32_t DEFAULT_SERIAL_MODE = SERIAL_8N1;

// --- Console (USB Serial) ---
static constexpr uint32_t CONSOLE_BAUD = 115200;

// --- Timeout sozlamalari (ms) ---
static constexpr uint32_t DEFAULT_INTERBYTE_TIMEOUT_MS = 30;   // Paket ichidagi baytlar orasidagi max vaqt
static constexpr uint32_t DEFAULT_RESPONSE_TIMEOUT_MS  = 1000; // SEND dan keyin javob kutish

// --- Buffer hajmlari ---
static constexpr size_t RS485_RX_BUF_SIZE  = 512;
static constexpr size_t RS485_TX_BUF_SIZE  = 512;
static constexpr size_t CONSOLE_BUF_SIZE   = 128;

// --- Direction control ---
// GPIO4 HIGH = transmit, GPIO4 LOW = receive
static constexpr uint32_t DIR_SWITCH_DELAY_US = 150; // mikrosekund

#endif // CONFIG_H
