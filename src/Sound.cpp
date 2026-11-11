#include "Sound.h"

#define NOTE_ARR(name, ...) static const Sound::Note name[] = {__VA_ARGS__}
NOTE_ARR(T_BEEP, {2000, 40});
NOTE_ARR(T_EAT, {600, 60}, {0, 60}, {600, 60}, {0, 60}, {800, 80});
NOTE_ARR(T_HAPPY, {1047, 90}, {1319, 90}, {1568, 140});
NOTE_ARR(T_CALL, {1760, 120}, {0, 80}, {1760, 120}, {0, 80}, {1760, 120});
NOTE_ARR(T_SICK, {500, 200}, {400, 300});
NOTE_ARR(T_WIN, {1047, 100}, {1319, 100}, {1568, 100}, {2093, 250});
NOTE_ARR(T_LOSE, {784, 150}, {659, 150}, {523, 300});
NOTE_ARR(T_EVOLVE, {523, 80}, {659, 80}, {784, 80}, {1047, 80}, {1319, 80}, {1568, 80}, {2093, 300});
NOTE_ARR(T_DEATH, {784, 300}, {698, 300}, {659, 300}, {523, 700});
NOTE_ARR(T_HATCH, {1568, 80}, {0, 40}, {2093, 160});
NOTE_ARR(T_REFUSE, {300, 120}, {0, 60}, {300, 120});

#define SET(arr)                                         \
  do {                                                   \
    notes_ = arr;                                         \
    count_ = sizeof(arr) / sizeof(arr[0]);               \
  } while (0)

void Sound::play(Tune t) {
  if (!enabled_) return;
  switch (t) {
    case Tune::Beep: SET(T_BEEP); break;
    case Tune::Eat: SET(T_EAT); break;
    case Tune::Happy: SET(T_HAPPY); break;
    case Tune::Call: SET(T_CALL); break;
    case Tune::Sick: SET(T_SICK); break;
    case Tune::Win: SET(T_WIN); break;
    case Tune::Lose: SET(T_LOSE); break;
    case Tune::Evolve: SET(T_EVOLVE); break;
    case Tune::Death: SET(T_DEATH); break;
    case Tune::Hatch: SET(T_HATCH); break;
    case Tune::Refuse: SET(T_REFUSE); break;
  }
  index_ = 0;
  nextAt_ = 0;
}

void Sound::update(uint32_t nowMs) {
  if (!notes_ || nowMs < nextAt_) return;
  if (index_ >= count_) {
    notes_ = nullptr;
    return;
  }
  const Note& n = notes_[index_++];
  if (n.freq && enabled_) M5.Speaker.tone(n.freq, n.ms);
  nextAt_ = nowMs + n.ms;
}
