// Conversion date <-> secondes depuis 2000-01-01 00:00 (heure locale, sans fuseau).
#pragma once
#include <stdint.h>

namespace timeutil {

struct DateTime {
  uint16_t year;
  uint8_t month, day, hour, minute, second;
};

// Algorithmes "days from civil" de Howard Hinnant.
inline int32_t daysFromCivil(int y, unsigned m, unsigned d) {
  y -= m <= 2;
  const int era = (y >= 0 ? y : y - 399) / 400;
  const unsigned yoe = (unsigned)(y - era * 400);
  const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + (int)doe - 719468;
}

static const int32_t DAYS_1970_TO_2000 = 10957;

inline uint32_t toSeconds(const DateTime& t) {
  int32_t days = daysFromCivil(t.year, t.month, t.day) - DAYS_1970_TO_2000;
  return (uint32_t)days * 86400u + t.hour * 3600u + t.minute * 60u + t.second;
}

inline DateTime fromSeconds(uint32_t s) {
  int32_t z = (int32_t)(s / 86400) + DAYS_1970_TO_2000 + 719468;
  const int era = (z >= 0 ? z : z - 146096) / 146097;
  const unsigned doe = (unsigned)(z - era * 146097);
  const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  int y = (int)yoe + era * 400;
  const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  const unsigned mp = (5 * doy + 2) / 153;
  const unsigned d = doy - (153 * mp + 2) / 5 + 1;
  const unsigned m = mp + (mp < 10 ? 3 : -9);
  y += (m <= 2);
  uint32_t r = s % 86400;
  return DateTime{(uint16_t)y, (uint8_t)m, (uint8_t)d, (uint8_t)(r / 3600), (uint8_t)((r / 60) % 60),
                  (uint8_t)(r % 60)};
}

}  // namespace timeutil
