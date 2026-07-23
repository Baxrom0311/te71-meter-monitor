#pragma once
/**
 * core/log.h — Debug logging makroslari
 *
 * APP_DEBUG yoki CORE_DEBUG_LEVEL > 0 → Serial.print ishlaydi,
 * aks holda kompilyatsiya qilinmaydi (flash hajm tejaladi).
 */

#if CORE_DEBUG_LEVEL > 0 || defined(APP_DEBUG)
  #define LOG_PRINT(x)       Serial.print(x)
  #define LOG_PRINTLN(x)     Serial.println(x)
  #define LOG_PRINTF(x, ...) Serial.printf(x, ##__VA_ARGS__)
#else
  #define LOG_PRINT(x)
  #define LOG_PRINTLN(x)
  #define LOG_PRINTF(x, ...)
#endif
