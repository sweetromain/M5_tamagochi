#include "Pet.h"

#include <string.h>

namespace tama {

static const uint32_t MIN = 60;
static const uint32_t HOUR = 3600;
static const uint32_t DAY = 86400;

const Tuning& defaultTuning() {
  static const Tuning t = {
      // Egg     Baby      Child    Teen       Adult
      {1 * MIN, 1 * HOUR, 1 * DAY, 2 * DAY, 5 * DAY, 0},
      // hunger : Baby, Child, Teen, Adult, Senior
      {10 * MIN, 30 * MIN, 45 * MIN, 60 * MIN, 50 * MIN},
      // happy
      {8 * MIN, 25 * MIN, 40 * MIN, 50 * MIN, 40 * MIN},
      // poop
      {15 * MIN, 45 * MIN, 60 * MIN, 90 * MIN, 70 * MIN},
      45 * MIN,  // energy awake
      15 * MIN,  // energy sleeping
      15 * MIN,  // neglect timeout
      12 * HOUR, // starve death
      6 * HOUR,  // sick death
      30 * MIN,  // dying duration
      15 * MIN,  // fake call duration
  };
  return t;
}

static const uint8_t BASE_WEIGHT[] = {5, 10, 20, 30, 25};
static const uint8_t BED_HOUR[] = {0, 20, 21, 22, 20};  // Baby : pas d'heure fixe
static const uint8_t WAKE_HOUR[] = {0, 8, 9, 9, 7};

Pet::Pet() { memset(&d_, 0, sizeof(d_)); }

void Pet::newEgg(uint32_t clock, uint32_t seed, uint16_t generation) {
  memset(&d_, 0, sizeof(d_));
  d_.magic = SAVE_MAGIC;
  d_.version = SAVE_VERSION;
  d_.generation = generation;
  d_.life = Life::Egg;
  d_.clock = clock;
  d_.rng = seed ? seed : 0x12345678;
  d_.hunger = 2;
  d_.happy = 2;
  d_.energy = MAX_STAT;
  d_.weight = BASE_WEIGHT[0];
  d_.tNextFake = 2 * HOUR;
  events_ = 0;
}

bool Pet::loadFrom(const PetData& d) {
  if (d.magic != SAVE_MAGIC || d.version != SAVE_VERSION) return false;
  if ((uint8_t)d.life > (uint8_t)Life::Dead) return false;
  d_ = d;
  return true;
}

uint32_t Pet::random(uint32_t n) {
  // xorshift32
  uint32_t x = d_.rng;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  d_.rng = x;
  return n ? x % n : x;
}

int Pet::stageIndex() const {
  switch (d_.life) {
    case Life::Baby: return 0;
    case Life::Child: return 1;
    case Life::Teen: return 2;
    case Life::Adult: return 3;
    case Life::Senior: return 4;
    default: return -1;
  }
}

bool Pet::isNight() const {
  int s = stageIndex();
  if (s <= 0) return false;
  uint8_t h = hour();
  return h >= BED_HOUR[s] || h < WAKE_HOUR[s];
}

void Pet::tick(uint32_t seconds) {
  for (uint32_t i = 0; i < seconds; ++i) {
    step();
  }
}

void Pet::step() {
  const Tuning& t = defaultTuning();
  d_.clock++;
  if (d_.life == Life::Dead) return;

  d_.stageSec++;
  if (d_.life == Life::Egg) {
    if (d_.stageSec >= t.stageDuration[0]) evolve();
    return;
  }
  d_.ageSec++;
  const int s = stageIndex();

  // ---- Évolution / vieillesse
  if (d_.life == Life::Senior) {
    if (d_.stageSec >= d_.lifespan && !d_.dying) {
      d_.dying = true;
      d_.tSick = 0;
    }
  } else if (d_.stageSec >= t.stageDuration[s + 1] && !d_.sleeping) {
    evolve();
    return;
  }

  // ---- Sommeil
  updateSleep();

  // ---- Faim / joie (en pause pendant le sommeil)
  if (!d_.sleeping) {
    if (++d_.tHunger >= t.hungerEvery[s]) {
      d_.tHunger = 0;
      if (d_.hunger) d_.hunger--;
    }
    uint32_t happyEvery = t.happyEvery[s];
    if (isSick()) happyEvery /= 2;
    if (++d_.tHappy >= happyEvery) {
      d_.tHappy = 0;
      if (d_.happy) d_.happy--;
    }
    if (++d_.tEnergy >= t.energyAwakeEvery) {
      d_.tEnergy = 0;
      if (d_.energy) d_.energy--;
    }
    // Caca
    if (++d_.tPoop >= t.poopEvery[s]) {
      d_.tPoop = 0;
      if (d_.poops < MAX_POOPS) {
        d_.poops++;
        events_ |= EV_POOPED;
      }
    }
  } else {
    if (++d_.tEnergy >= t.energySleepEvery) {
      d_.tEnergy = 0;
      if (d_.energy < MAX_STAT) d_.energy++;
    }
  }

  // ---- Fenêtre des friandises (1 h)
  if (d_.snacksRecent && ++d_.tSnack >= HOUR) {
    d_.tSnack = 0;
    d_.snacksRecent = 0;
  }

  // ---- Saleté -> maladie
  if (d_.poops > 0) {
    if (d_.poops >= MAX_POOPS && !isSick()) becomeSick();
    if (++d_.tDirty >= 30 * MIN) {
      d_.tDirty = 0;
      if (!isSick() && random(4) == 0) becomeSick();
    }
  } else {
    d_.tDirty = 0;
  }

  // ---- Négligence : besoins non satisfaits
  if (d_.hunger == 0) {
    d_.tHungerZero++;
    if (d_.tHungerZero >= t.neglectTimeout && !d_.hungerMistakeCounted) {
      d_.hungerMistakeCounted = true;
      d_.careMistakes++;
      events_ |= EV_CARE_MISTAKE;
    }
    if (d_.tHungerZero >= t.starveDeath) {
      die();
      return;
    }
  } else {
    d_.tHungerZero = 0;
    d_.hungerMistakeCounted = false;
  }
  if (d_.happy == 0) {
    d_.tHappyZero++;
    if (d_.tHappyZero >= t.neglectTimeout && !d_.happyMistakeCounted) {
      d_.happyMistakeCounted = true;
      d_.careMistakes++;
      events_ |= EV_CARE_MISTAKE;
    }
  } else {
    d_.tHappyZero = 0;
    d_.happyMistakeCounted = false;
  }
  if (d_.sleeping && !d_.lightsOff) {
    d_.tLightOn++;
    if (d_.tLightOn >= t.neglectTimeout && !d_.lightMistakeCounted) {
      d_.lightMistakeCounted = true;
      d_.careMistakes++;
      events_ |= EV_CARE_MISTAKE;
    }
  } else {
    d_.tLightOn = 0;
  }

  // ---- Maladie non soignée
  if (isSick() && !d_.dying) {
    if (++d_.tSick >= t.sickDeath) {
      d_.dying = true;
      d_.tSick = 0;
    }
  }
  if (d_.dying) {
    if (++d_.tSick >= t.dyingDuration) {
      die();
      return;
    }
  }

  // ---- Caprices
  if (d_.calls & CALL_FAKE) {
    if (++d_.tFake >= t.fakeCallDuration) {
      d_.calls &= ~CALL_FAKE;
      d_.disciplineMistakes++;
    }
  } else if (!d_.sleeping && d_.discipline < 100) {
    if (d_.tNextFake) d_.tNextFake--;
    if (d_.tNextFake == 0) {
      d_.tNextFake = HOUR + random(2 * HOUR);
      if (d_.calls == 0) {
        d_.calls |= CALL_FAKE;
        d_.tFake = 0;
      }
    }
  }

  if (d_.tPetCooldown) d_.tPetCooldown--;

  updateCalls();
}

void Pet::updateSleep() {
  const int s = stageIndex();
  if (!d_.sleeping) {
    if (d_.energy == 0 || (isNight() && !d_.dying)) {
      d_.sleeping = true;
      d_.lightMistakeCounted = false;
      d_.tLightOn = 0;
      d_.calls &= ~CALL_FAKE;
      events_ |= EV_FELL_ASLEEP;
    }
  } else {
    bool rested = d_.energy >= MAX_STAT;
    bool wake = (s > 0) ? (!isNight() && rested) : rested;
    if (wake) {
      d_.sleeping = false;
      d_.lightsOff = false;  // la lumière se rallume au réveil
      events_ |= EV_WOKE_UP;
    }
  }
}

void Pet::updateCalls() {
  uint8_t before = d_.calls;
  uint8_t c = d_.calls & CALL_FAKE;
  if (d_.hunger == 0) c |= CALL_HUNGER;
  if (d_.happy == 0) c |= CALL_HAPPY;
  if (d_.sleeping && !d_.lightsOff) c |= CALL_LIGHT;
  if (isSick()) c |= CALL_SICK;
  if (d_.poops >= 2) c |= CALL_DIRTY;
  d_.calls = c;
  if ((c & ~before) != 0) events_ |= EV_CALL_STARTED;
}

void Pet::becomeSick() {
  d_.dosesNeeded = 1 + random(2);
  d_.tSick = 0;
  events_ |= EV_GOT_SICK;
}

void Pet::evolve() {
  const Tuning& t = defaultTuning();
  (void)t;
  switch (d_.life) {
    case Life::Egg:
      d_.life = Life::Baby;
      d_.weight = BASE_WEIGHT[0];
      events_ |= EV_HATCHED;
      break;
    case Life::Baby:
      d_.life = Life::Child;
      events_ |= EV_EVOLVED;
      break;
    case Life::Child:
      d_.life = Life::Teen;
      events_ |= EV_EVOLVED;
      break;
    case Life::Teen: {
      d_.life = Life::Adult;
      int score = d_.careMistakes * 2 + d_.disciplineMistakes + (d_.discipline < 50 ? 2 : 0);
      d_.adultKind = score <= 4 ? AdultKind::Good : (score <= 10 ? AdultKind::Mid : AdultKind::Bad);
      events_ |= EV_EVOLVED;
      break;
    }
    case Life::Adult: {
      d_.life = Life::Senior;
      uint32_t span = 2 * DAY + random(2 * DAY);
      uint32_t malus = (uint32_t)d_.careMistakes * 2 * HOUR;
      d_.lifespan = span > malus + 6 * HOUR ? span - malus : 6 * HOUR;
      events_ |= EV_EVOLVED;
      break;
    }
    default:
      return;
  }
  d_.stageSec = 0;
  int s = stageIndex();
  if (s >= 0 && d_.weight < BASE_WEIGHT[s]) d_.weight = BASE_WEIGHT[s];
  d_.tHunger = d_.tHappy = d_.tPoop = 0;
}

void Pet::die() {
  d_.life = Life::Dead;
  d_.sleeping = false;
  d_.dying = false;
  d_.calls = 0;
  d_.dosesNeeded = 0;
  d_.poops = 0;
  events_ |= EV_DIED;
}

bool Pet::rollRefuse() {
  // jusqu'à 12 % de refus quand la discipline est nulle ; un bébé ne fait pas de caprice
  if (d_.life == Life::Baby) return false;
  uint32_t chance = (100 - d_.discipline) / 8;
  if (random(100) < chance) {
    d_.calls |= CALL_FAKE;  // le refus est un caprice : on peut gronder
    d_.tFake = 0;
    return true;
  }
  return false;
}

static inline bool unavailable(const PetData& d) { return d.life == Life::Egg || d.life == Life::Dead; }

Result Pet::feedMeal() {
  if (unavailable(d_)) return Result::Unavailable;
  if (d_.sleeping) return Result::Asleep;
  if (d_.hunger >= MAX_STAT) return Result::Full;
  if (rollRefuse()) return Result::Refused;
  d_.hunger++;
  if (d_.weight < 99) d_.weight++;
  updateCalls();
  return Result::Ok;
}

Result Pet::feedSnack() {
  if (unavailable(d_)) return Result::Unavailable;
  if (d_.sleeping) return Result::Asleep;
  if (rollRefuse()) return Result::Refused;
  if (d_.happy < MAX_STAT) d_.happy++;
  d_.weight = d_.weight > 97 ? 99 : d_.weight + 2;
  d_.snacksRecent++;
  int s = stageIndex();
  bool overweight = s >= 0 && d_.weight > BASE_WEIGHT[s] * 2;
  if (!isSick() && (d_.snacksRecent >= 4 || overweight) && random(2) == 0) becomeSick();
  updateCalls();
  return Result::Ok;
}

Result Pet::clean() {
  if (unavailable(d_)) return Result::Unavailable;
  if (d_.poops == 0) return Result::NotNeeded;
  d_.poops = 0;
  d_.tDirty = 0;
  updateCalls();
  return Result::Ok;
}

Result Pet::giveMedicine() {
  if (unavailable(d_)) return Result::Unavailable;
  if (!isSick()) return Result::NotNeeded;
  d_.dosesNeeded--;
  if (d_.dosesNeeded == 0) {
    d_.tSick = 0;
    d_.dying = false;
    events_ |= EV_CURED;
  }
  updateCalls();
  return Result::Ok;
}

Result Pet::toggleLight() {
  if (d_.life == Life::Dead) return Result::Unavailable;
  d_.lightsOff = !d_.lightsOff;
  updateCalls();
  return Result::Ok;
}

Result Pet::scold() {
  if (unavailable(d_)) return Result::Unavailable;
  if (d_.sleeping) return Result::Asleep;
  if (d_.calls & CALL_FAKE) {
    d_.calls &= ~CALL_FAKE;
    d_.discipline = d_.discipline >= 75 ? 100 : d_.discipline + 25;
    updateCalls();
    return Result::Ok;
  }
  // Gronder sans raison : injuste, il est triste
  if (d_.happy) d_.happy--;
  updateCalls();
  return Result::NotNeeded;
}

Result Pet::caress() {
  if (unavailable(d_)) return Result::Unavailable;
  if (d_.sleeping) return Result::Asleep;
  if (d_.tPetCooldown) return Result::NotNeeded;
  d_.tPetCooldown = 10 * MIN;
  if (d_.happy < MAX_STAT) d_.happy++;
  updateCalls();
  return Result::Ok;
}

Result Pet::canPlay() {
  if (unavailable(d_)) return Result::Unavailable;
  if (d_.sleeping) return Result::Asleep;
  if (d_.energy == 0) return Result::TooTired;
  if (rollRefuse()) return Result::Refused;
  return Result::Ok;
}

void Pet::applyGameResult(bool won) {
  if (won && d_.happy < MAX_STAT) d_.happy++;
  int s = stageIndex();
  uint8_t minW = s >= 0 ? BASE_WEIGHT[s] : 1;
  if (d_.weight > minW) d_.weight--;
  if (d_.energy) d_.energy--;
  updateCalls();
}

}  // namespace tama
