// Logique pure de la créature (aucune dépendance Arduino : testable sur PC).
#pragma once
#include <stdint.h>

namespace tama {

enum class Life : uint8_t { Egg, Baby, Child, Teen, Adult, Senior, Dead };
enum class AdultKind : uint8_t { Good, Mid, Bad };

enum class Result : uint8_t {
  Ok,
  Refused,     // caprice (discipline faible)
  Full,        // n'a plus faim
  NotNeeded,   // rien à nettoyer / pas malade
  Asleep,      // dort
  TooTired,    // pas d'énergie pour jouer
  Unavailable  // oeuf ou mort
};

// Raisons d'appel (bitmask)
enum CallReason : uint8_t {
  CALL_HUNGER = 1 << 0,
  CALL_HAPPY = 1 << 1,
  CALL_LIGHT = 1 << 2,
  CALL_SICK = 1 << 3,
  CALL_FAKE = 1 << 4,  // caprice : à gronder
  CALL_DIRTY = 1 << 5,
};

// Évènements ponctuels à consommer par l'interface (bitmask)
enum Event : uint16_t {
  EV_HATCHED = 1 << 0,
  EV_EVOLVED = 1 << 1,
  EV_POOPED = 1 << 2,
  EV_GOT_SICK = 1 << 3,
  EV_CURED = 1 << 4,
  EV_FELL_ASLEEP = 1 << 5,
  EV_WOKE_UP = 1 << 6,
  EV_DIED = 1 << 7,
  EV_CALL_STARTED = 1 << 8,
  EV_CARE_MISTAKE = 1 << 9,
};

static const uint32_t SAVE_MAGIC = 0x54414D41;  // "TAMA"
static const uint16_t SAVE_VERSION = 1;
static const uint8_t MAX_STAT = 4;
static const uint8_t MAX_POOPS = 4;

// Toutes les données persistantes (sauvegardées telles quelles en NVS).
struct PetData {
  uint32_t magic;
  uint16_t version;
  uint16_t generation;

  Life life;
  AdultKind adultKind;
  uint8_t hunger;      // 0..4 (4 = rassasié)
  uint8_t happy;       // 0..4
  uint8_t energy;      // 0..4
  uint8_t discipline;  // 0..100
  uint8_t weight;
  uint8_t poops;       // 0..4
  uint8_t careMistakes;
  uint8_t disciplineMistakes;
  uint8_t dosesNeeded;  // >0 = malade
  uint8_t snacksRecent;
  bool sleeping;
  bool lightsOff;
  bool dying;
  bool lightMistakeCounted;
  bool hungerMistakeCounted;
  bool happyMistakeCounted;
  uint8_t calls;  // CallReason

  uint32_t clock;     // horloge du jeu, secondes depuis 2000-01-01 (heure locale)
  uint32_t ageSec;    // âge depuis l'éclosion
  uint32_t stageSec;  // temps passé dans le stade courant
  uint32_t lifespan;  // durée du stade Senior avant mort naturelle

  // minuteries (secondes)
  uint32_t tHunger, tHappy, tEnergy, tPoop, tSnack;
  uint32_t tHungerZero, tHappyZero, tLightOn;
  uint32_t tSick, tDirty, tFake, tNextFake, tPetCooldown;

  uint32_t rng;
};

// Réglages de durée (secondes de jeu). Index : Baby, Child, Teen, Adult, Senior.
struct Tuning {
  uint32_t stageDuration[6];  // Egg..Adult (Senior : lifespan aléatoire)
  uint32_t hungerEvery[5];
  uint32_t happyEvery[5];
  uint32_t poopEvery[5];
  uint32_t energyAwakeEvery;
  uint32_t energySleepEvery;
  uint32_t neglectTimeout;   // besoin ignoré -> erreur de soin
  uint32_t starveDeath;      // faim à 0 pendant -> mort
  uint32_t sickDeath;        // malade non soigné pendant -> mort
  uint32_t dyingDuration;    // phase "dying" avant la mort
  uint32_t fakeCallDuration;
};

const Tuning& defaultTuning();

class Pet {
 public:
  Pet();
  explicit Pet(const PetData& d) : d_(d) {}

  void newEgg(uint32_t clock, uint32_t seed, uint16_t generation = 1);
  bool loadFrom(const PetData& d);  // false si sauvegarde invalide
  const PetData& data() const { return d_; }
  PetData& mutableData() { return d_; }

  // Avance le temps de jeu de `seconds`.
  void tick(uint32_t seconds);

  // Heure du jeu (0..23) et minute
  uint8_t hour() const { return (d_.clock / 3600) % 24; }
  uint8_t minute() const { return (d_.clock / 60) % 60; }
  void setClock(uint32_t clock) { d_.clock = clock; }

  // Actions du joueur
  Result feedMeal();
  Result feedSnack();
  Result clean();
  Result giveMedicine();
  Result toggleLight();
  Result scold();
  Result caress();
  Result canPlay();                   // vérifie avant de lancer le mini-jeu
  void applyGameResult(bool won);

  // Lecture
  Life life() const { return d_.life; }
  bool isDead() const { return d_.life == Life::Dead; }
  bool isEgg() const { return d_.life == Life::Egg; }
  bool isSick() const { return d_.dosesNeeded > 0; }
  bool isCalling() const { return d_.calls != 0; }
  uint16_t takeEvents() {
    uint16_t e = events_;
    events_ = 0;
    return e;
  }
  uint8_t ageDays() const { return d_.ageSec / 86400; }

  // Pour le test : fixer la graine
  uint32_t random(uint32_t n);

 private:
  void step();  // 1 seconde
  int stageIndex() const;  // 0..4 pour Baby..Senior, -1 sinon
  void evolve();
  void die();
  void updateSleep();
  void updateCalls();
  bool isNight() const;
  bool rollRefuse();
  void becomeSick();

  PetData d_;
  uint16_t events_ = 0;
};

}  // namespace tama
