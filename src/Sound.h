// Petites mélodies non bloquantes sur le buzzer du M5StickC Plus2.
#pragma once
#include <M5Unified.h>

enum class Tune : uint8_t { Beep, Eat, Happy, Call, Sick, Win, Lose, Evolve, Death, Hatch, Refuse };

class Sound {
 public:
  struct Note {
    uint16_t freq;  // 0 = silence
    uint16_t ms;
  };
  void setEnabled(bool on) { enabled_ = on; }
  bool enabled() const { return enabled_; }
  void play(Tune t);
  void update(uint32_t nowMs);

 private:
  const Note* notes_ = nullptr;
  uint8_t count_ = 0;
  uint8_t index_ = 0;
  uint32_t nextAt_ = 0;
  bool enabled_ = true;
};
