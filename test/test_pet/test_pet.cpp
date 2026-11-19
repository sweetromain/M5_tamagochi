// Tests de la logique (pio test -e native)
#include <unity.h>

#include "Pet.h"

using namespace tama;

static const uint32_t MIN = 60, HOUR = 3600, DAY = 86400;
// 2026-01-01 12:00 (heure locale, secondes depuis 2000)
static const uint32_t NOON = 26 * 365 * DAY + 7 * DAY + 12 * HOUR;

static Pet hatched() {
  Pet p;
  p.newEgg(NOON, 42);
  p.tick(61);
  return p;
}

void setUp() {}
void tearDown() {}

void test_egg_hatches_after_one_minute() {
  Pet p;
  p.newEgg(NOON, 1);
  p.tick(59);
  TEST_ASSERT_TRUE(p.isEgg());
  p.tick(2);
  TEST_ASSERT_EQUAL((int)Life::Baby, (int)p.life());
  TEST_ASSERT_TRUE(p.takeEvents() & EV_HATCHED);
}

void test_egg_rejects_actions() {
  Pet p;
  p.newEgg(NOON, 1);
  TEST_ASSERT_EQUAL((int)Result::Unavailable, (int)p.feedMeal());
}

void test_hunger_decreases_and_meal_restores() {
  Pet p = hatched();
  p.mutableData().hunger = 4;
  p.mutableData().discipline = 100;  // pas de caprice
  p.tick(10 * MIN);
  TEST_ASSERT_EQUAL(3, p.data().hunger);
  TEST_ASSERT_EQUAL((int)Result::Ok, (int)p.feedMeal());
  TEST_ASSERT_EQUAL(4, p.data().hunger);
  TEST_ASSERT_EQUAL((int)Result::Full, (int)p.feedMeal());
}

void test_neglect_counts_one_care_mistake() {
  Pet p = hatched();
  p.mutableData().hunger = 0;
  p.mutableData().happy = 4;
  p.mutableData().discipline = 100;
  p.tick(14 * MIN);
  TEST_ASSERT_EQUAL(0, p.data().careMistakes);
  p.tick(5 * MIN);
  TEST_ASSERT_EQUAL(1, p.data().careMistakes);
  p.tick(10 * MIN);
  TEST_ASSERT_EQUAL(1, p.data().careMistakes);  // une seule erreur par épisode
  TEST_ASSERT_TRUE(p.data().calls & CALL_HUNGER);
}

void test_four_poops_make_sick_and_medicine_cures() {
  Pet p = hatched();
  p.mutableData().poops = 4;
  p.tick(1);
  TEST_ASSERT_TRUE(p.isSick());
  TEST_ASSERT_EQUAL((int)Result::Ok, (int)p.clean());
  while (p.isSick()) TEST_ASSERT_EQUAL((int)Result::Ok, (int)p.giveMedicine());
  TEST_ASSERT_EQUAL((int)Result::NotNeeded, (int)p.giveMedicine());
}

void test_untreated_sickness_kills() {
  Pet p = hatched();
  p.mutableData().dosesNeeded = 2;
  p.tick(6 * HOUR + 31 * MIN);
  TEST_ASSERT_TRUE(p.isDead());
}

void test_starvation_kills() {
  Pet p = hatched();
  p.mutableData().hunger = 0;
  p.tick(12 * HOUR + 1);
  TEST_ASSERT_TRUE(p.isDead());
}

void test_scold_fake_call_raises_discipline() {
  Pet p = hatched();
  p.mutableData().calls = CALL_FAKE;
  p.mutableData().discipline = 0;
  TEST_ASSERT_EQUAL((int)Result::Ok, (int)p.scold());
  TEST_ASSERT_EQUAL(25, p.data().discipline);
  // gronder sans raison rend triste
  p.mutableData().happy = 3;
  TEST_ASSERT_EQUAL((int)Result::NotNeeded, (int)p.scold());
  TEST_ASSERT_EQUAL(2, p.data().happy);
}

void test_child_sleeps_at_night_and_light_mistake() {
  Pet p = hatched();
  PetData& d = p.mutableData();
  d.life = Life::Child;
  d.stageSec = 0;
  d.hunger = d.happy = 4;
  d.clock = NOON + 8 * HOUR;  // 20:00
  p.tick(1);
  TEST_ASSERT_TRUE(p.data().sleeping);
  TEST_ASSERT_TRUE(p.data().calls & CALL_LIGHT);
  p.tick(16 * MIN);
  TEST_ASSERT_EQUAL(1, p.data().careMistakes);
  p.toggleLight();
  TEST_ASSERT_TRUE(p.data().lightsOff);
  TEST_ASSERT_EQUAL((int)Result::Asleep, (int)p.feedMeal());
}

void test_child_wakes_in_the_morning() {
  Pet p = hatched();
  PetData& d = p.mutableData();
  d.life = Life::Child;
  d.sleeping = true;
  d.lightsOff = true;
  d.energy = 4;
  d.clock = NOON - 4 * HOUR;  // 08:00
  p.tick(1);
  TEST_ASSERT_FALSE(p.data().sleeping);
  TEST_ASSERT_FALSE(p.data().lightsOff);
}

void test_teen_evolves_to_adult_kind_by_care() {
  Pet good = hatched();
  good.mutableData().life = Life::Teen;
  good.mutableData().discipline = 100;
  good.mutableData().stageSec = 2 * DAY - 1;
  good.mutableData().clock = NOON;
  good.tick(2);
  TEST_ASSERT_EQUAL((int)Life::Adult, (int)good.life());
  TEST_ASSERT_EQUAL((int)AdultKind::Good, (int)good.data().adultKind);

  Pet bad = hatched();
  bad.mutableData().life = Life::Teen;
  bad.mutableData().careMistakes = 8;
  bad.mutableData().stageSec = 2 * DAY - 1;
  bad.mutableData().clock = NOON;
  bad.tick(2);
  TEST_ASSERT_EQUAL((int)AdultKind::Bad, (int)bad.data().adultKind);
}

void test_senior_dies_of_old_age() {
  Pet p = hatched();
  PetData& d = p.mutableData();
  d.life = Life::Senior;
  d.lifespan = HOUR;
  d.stageSec = 0;
  d.hunger = d.happy = 4;
  p.tick(HOUR + 31 * MIN);
  TEST_ASSERT_TRUE(p.isDead());
}

void test_game_result() {
  Pet p = hatched();
  p.mutableData().happy = 1;
  p.mutableData().weight = 8;
  p.applyGameResult(true);
  TEST_ASSERT_EQUAL(2, p.data().happy);
  TEST_ASSERT_EQUAL(7, p.data().weight);
}

void test_save_roundtrip_and_invalid() {
  Pet p = hatched();
  PetData copy = p.data();
  Pet q;
  TEST_ASSERT_TRUE(q.loadFrom(copy));
  TEST_ASSERT_EQUAL((int)p.life(), (int)q.life());
  copy.magic = 0;
  TEST_ASSERT_FALSE(q.loadFrom(copy));
}

void test_full_life_simulation_does_not_crash() {
  // une semaine sans soins : doit mourir proprement
  Pet p;
  p.newEgg(NOON, 7);
  p.tick(7 * DAY);
  TEST_ASSERT_TRUE(p.isDead());
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_egg_hatches_after_one_minute);
  RUN_TEST(test_egg_rejects_actions);
  RUN_TEST(test_hunger_decreases_and_meal_restores);
  RUN_TEST(test_neglect_counts_one_care_mistake);
  RUN_TEST(test_four_poops_make_sick_and_medicine_cures);
  RUN_TEST(test_untreated_sickness_kills);
  RUN_TEST(test_starvation_kills);
  RUN_TEST(test_scold_fake_call_raises_discipline);
  RUN_TEST(test_child_sleeps_at_night_and_light_mistake);
  RUN_TEST(test_child_wakes_in_the_morning);
  RUN_TEST(test_teen_evolves_to_adult_kind_by_care);
  RUN_TEST(test_senior_dies_of_old_age);
  RUN_TEST(test_game_result);
  RUN_TEST(test_save_roundtrip_and_invalid);
  RUN_TEST(test_full_life_simulation_does_not_crash);
  return UNITY_END();
}
