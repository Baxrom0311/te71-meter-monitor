#pragma once
/**
 * display/disp_none.h — No-op display module
 *
 * Used when HAVE_LCD is not defined, or when no display module exists
 * for the selected sensor. All three interface functions are empty macros.
 */

#define disp_init()                  do {} while(0)
#define disp_show_reading(d)         do {} while(0)
#define disp_show_status(w, s, l)    do {} while(0)
