/**
 * CE 303 Smart Bridge — IEC 62056-21 Mode C
 *
 * USB (9600 8N1) ↔ RS-485 (300→9600, 7E1)
 *
 * Maxsus USB buyruqlari (Python dan):
 *   ~B300~   → RS-485 ni 300 baud ga o'tkazish (sign-on uchun)
 *   ~B9600~  → RS-485 ni 9600 baud ga o'tkazish (data uchun)
 *   ~B4800~  → RS-485 ni 4800 baud ga o'tkazish
 *   ~BAUD?~  → Joriy baud ni javob berish
 *
 * Boshqa barcha baytlar → shaffof ko'prik
 *
 * Pinlar: GPIO16=RX, GPIO17=TX, GPIO4=DE/RE
 */

#include <Arduino.h>

// ── Pinlar ────────────────────────────────────────────────────────────────────
static constexpr uint8_t PIN_DE_RE = 4;
static constexpr uint8_t PIN_RX485 = 16;
static constexpr uint8_t PIN_TX485 = 17;

// ── Sozlamalar ────────────────────────────────────────────────────────────────
static constexpr uint32_t BAUD_USB   = 9600;
static constexpr uint32_t INTER_BYTE = 50;
static constexpr size_t   BUF_SIZE   = 512;

static uint32_t current_rs485_baud = 300;  // Boshlang'ich: 300 baud

// ── RS-485 boshqarish ─────────────────────────────────────────────────────────
inline void rs485_tx() {
  digitalWrite(PIN_DE_RE, HIGH);
  delayMicroseconds(200);
}
inline void rs485_rx() {
  Serial2.flush();                              // TX tamom bo'lguncha kut
  // 1 char vaqti + margin: 300 baud=33ms, 1200=8ms, 9600=1ms
  uint32_t char_us = 10000000UL / current_rs485_baud + 500;
  delayMicroseconds(char_us);
  digitalWrite(PIN_DE_RE, LOW);
}

void rs485_set_baud(uint32_t baud) {
  current_rs485_baud = baud;
  Serial2.end();
  delay(10);
  Serial2.begin(baud, SERIAL_8N1, PIN_RX485, PIN_TX485);
  delay(10);
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  pinMode(PIN_DE_RE, OUTPUT);
  rs485_rx();

  Serial.begin(BAUD_USB);
  // Boshlash: 300 baud 8N1 (IEC sign-on uchun)
  Serial2.begin(300, SERIAL_8N1, PIN_RX485, PIN_TX485);

  delay(200);
  Serial.println(F("\r\n=== CE303 Smart Bridge ==="));
  Serial.println(F("USB: 9600 8N1 | RS485: 300 7E1 (boshlang'ich)"));
  Serial.println(F("Buyruqlar: ~B300~ ~B9600~ ~B4800~ ~BAUD?~"));
  Serial.println(F("=========================="));
}

// ── Maxsus buyruq tekshirish: ~Bxxxx~ ─────────────────────────────────────────
// buf ichida ~B...~ pattern qidiramiz
bool check_cmd(uint8_t* buf, size_t len, uint32_t* new_baud, bool* query) {
  // Minimal: ~B3~ = 4 bytes
  for (size_t i = 0; i + 2 < len; i++) {
    if (buf[i] == '~' && buf[i+1] == 'B') {
      // '?' query
      if (i+3 < len && buf[i+2] == 'A' && buf[i+3] == 'U') {
        // ~BAUD?~
        *query = true;
        return true;
      }
      // Raqam: ~B300~ yoki ~B9600~ ...
      uint32_t val = 0;
      size_t j = i + 2;
      while (j < len && buf[j] >= '0' && buf[j] <= '9') {
        val = val * 10 + (buf[j] - '0');
        j++;
      }
      if (j < len && buf[j] == '~' && val > 0) {
        *new_baud = val;
        return true;
      }
    }
  }
  return false;
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  static uint8_t  usb_buf[BUF_SIZE];
  static size_t   usb_len  = 0;
  static uint32_t last_usb = 0;

  // ── RS-485 → USB: har doim forward ───────────────────────────────────────
  while (Serial2.available()) {
    Serial.write(Serial2.read());
  }

  // ── USB baytlarni to'plash ────────────────────────────────────────────────
  while (Serial.available()) {
    uint8_t b = Serial.read();
    if (usb_len < BUF_SIZE) usb_buf[usb_len++] = b;
    last_usb = millis();
  }

  // 50ms pauza bo'ldi → frame tugagan
  if (usb_len > 0 && (millis() - last_usb) >= INTER_BYTE) {

    uint32_t new_baud = 0;
    bool     is_query = false;

    if (check_cmd(usb_buf, usb_len, &new_baud, &is_query)) {
      // Maxsus buyruq
      if (is_query) {
        Serial.printf("BAUD:%u\r\n", current_rs485_baud);
      } else {
        rs485_set_baud(new_baud);
        Serial.printf("OK:BAUD:%u\r\n", new_baud);
      }
    } else {
      // Oddiy ma'lumot → RS-485 ga yuborish
      rs485_tx();
      Serial2.write(usb_buf, usb_len);
      Serial2.flush();
      rs485_rx();
    }

    usb_len = 0;
  }
}
