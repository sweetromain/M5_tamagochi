// Jeu de créature virtuelle pour M5StickC Plus2.
//
// Boutons :  A (face avant)  = valider / caresser
//            B (côté)        = icône suivante
//            PWR (côté)      = retour  (appui long 6 s = extinction matérielle)
//            Secouer         = réveiller l'écran / caresser
#include <M5Unified.h>
#include <Preferences.h>

#include "Animator.h"
#include "Pet.h"
#include "Renderer.h"
#include "Sound.h"
#include "TimeUtil.h"

using namespace tama;

// ------------------------------------------------------------------ réglages
static const uint32_t FRAME_MS = 66;            // ~15 fps
static const uint32_t SCREEN_TIMEOUT_MS = 30000;
static const uint32_t SAVE_EVERY_MS = 60000;
static const uint32_t MENU_DESELECT_MS = 10000;
static const uint32_t MAX_CATCHUP_SEC = 7 * 86400;
static const uint8_t SPEEDS[] = {1, 10, 60};
static const uint8_t BRIGHTNESS[] = {40, 90, 150, 220};

struct Settings {
  uint8_t version;
  bool sound;
  uint8_t speedIdx;
  uint8_t brightIdx;
};

enum class Screen : uint8_t { Main, Food, Stats, Game, Settings, Clock, Dead };

enum Input : uint8_t { IN_NONE = 0, IN_A = 1, IN_B = 2, IN_PWR = 4, IN_SHAKE = 8 };

// ------------------------------------------------------------------ état global
static M5Canvas canvas(&M5.Display);
static Preferences prefs;
static Pet pet;
static Animator anim;
static Sound sound;
static Settings settings = {1, true, 0, 2};

static Screen screen = Screen::Main;
static int menuSel = -1;
static int cursor = 0;
static uint32_t lastInputMs = 0, lastFrameMs = 0, lastSaveMs = 0, lastTickMs = 0, lastShakeMs = 0;
static uint32_t gameMsAcc = 0;
static uint32_t lastRtc = 0;
static uint32_t bootClock = 0;  // repli si le RTC est absent
static bool screenOn = true;
static bool rtcOk = false;
static uint32_t confirmUntil = 0;
static uint32_t newEggAt = 0;
static bool dirty = false;

// mini-jeu
struct MiniGame {
  uint8_t round, wins;
  bool revealing, finished;
  bool guessLeft, lookLeft;
  uint32_t until;
} game;

// ------------------------------------------------------------------ horloge
static uint32_t readRtc() {
  if (!rtcOk) return bootClock + millis() / 1000;
  auto dt = M5.Rtc.getDateTime();
  timeutil::DateTime t{(uint16_t)dt.date.year, (uint8_t)dt.date.month, (uint8_t)dt.date.date,
                       (uint8_t)dt.time.hours, (uint8_t)dt.time.minutes, (uint8_t)dt.time.seconds};
  return timeutil::toSeconds(t);
}

static void writeRtc(uint32_t secs) {
  if (!rtcOk) return;
  timeutil::DateTime t = timeutil::fromSeconds(secs);
  m5::rtc_datetime_t dt;
  dt.date.year = t.year;
  dt.date.month = t.month;
  dt.date.date = t.day;
  dt.date.weekDay = 0;
  dt.time.hours = t.hour;
  dt.time.minutes = t.minute;
  dt.time.seconds = t.second;
  M5.Rtc.setDateTime(dt);
}

// ------------------------------------------------------------------ sauvegarde
static void save() {
  lastRtc = readRtc();
  prefs.putBytes("pet", &pet.data(), sizeof(PetData));
  prefs.putUInt("rtc", lastRtc);
  prefs.putBytes("cfg", &settings, sizeof(settings));
  dirty = false;
}

static void applySettings() {
  sound.setEnabled(settings.sound);
  M5.Display.setBrightness(BRIGHTNESS[settings.brightIdx % 4]);
}

static void startNewEgg(uint16_t generation) {
  pet.newEgg(readRtc(), esp_random(), generation);
  anim.reset(millis());
  screen = Screen::Main;
  menuSel = -1;
  save();
}

static void load() {
  prefs.begin("tama", false);
  Settings s;
  if (prefs.getBytes("cfg", &s, sizeof(s)) == sizeof(s) && s.version == 1) settings = s;
  settings.speedIdx %= sizeof(SPEEDS);
  settings.brightIdx %= sizeof(BRIGHTNESS);
  applySettings();

  PetData d;
  bool ok = prefs.getBytes("pet", &d, sizeof(d)) == sizeof(d) && pet.loadFrom(d);
  lastRtc = prefs.getUInt("rtc", 0);
  if (!rtcOk) bootClock = lastRtc;
  if (!ok) {
    startNewEgg(1);
    return;
  }
  // Rattrapage du temps écoulé pendant que l'appareil était éteint
  uint32_t now = readRtc();
  if (now > lastRtc && lastRtc != 0) {
    uint32_t elapsed = (now - lastRtc) * SPEEDS[settings.speedIdx];
    if (elapsed > MAX_CATCHUP_SEC) elapsed = MAX_CATCHUP_SEC;
    canvas.fillScreen(ui::COL_PANEL);
    canvas.setTextColor(ui::COL_ACCENT);
    canvas.setTextDatum(middle_center);
    canvas.setFont(&fonts::Font2);
    canvas.drawString("Pendant ton absence...", ui::W / 2, ui::H / 2);
    canvas.pushSprite(0, 0);
    while (elapsed) {
      uint32_t chunk = elapsed > 3600 ? 3600 : elapsed;
      pet.tick(chunk);
      elapsed -= chunk;
      delay(0);
    }
    pet.takeEvents();
  }
  pet.setClock(now);  // l'horloge du jeu suit le RTC
  save();
}

// ------------------------------------------------------------------ entrées
static uint8_t readInput(uint32_t now) {
  uint8_t in = IN_NONE;
  if (M5.BtnA.wasPressed()) in |= IN_A;
  if (M5.BtnB.wasPressed()) in |= IN_B;
  if (M5.BtnPWR.wasClicked() || M5.BtnPWR.wasPressed()) in |= IN_PWR;
  float ax, ay, az;
  if (M5.Imu.isEnabled() && M5.Imu.getAccel(&ax, &ay, &az)) {
    float g2 = ax * ax + ay * ay + az * az;
    if (g2 > 4.0f && now - lastShakeMs > 1500) {  // > 2 g
      lastShakeMs = now;
      in |= IN_SHAKE;
    }
  }
  return in;
}

static void setScreenOn(bool on) {
  if (on == screenOn) return;
  screenOn = on;
  if (on) {
    M5.Display.wakeup();
    applySettings();
  } else {
    M5.Display.setBrightness(0);
    M5.Display.sleep();
  }
}

// ------------------------------------------------------------------ réactions
static void react(Result r, PoseId okPose, uint32_t ms, Tune okTune, int16_t emote = NO_SPRITE,
                  int16_t item = NO_SPRITE) {
  switch (r) {
    case Result::Ok:
      anim.play(okPose, ms, emote, item);
      sound.play(okTune);
      dirty = true;
      break;
    case Result::Refused:
      anim.play(POSE_REFUSE, 1500, SPR_EMOTES_ANGER);
      sound.play(Tune::Refuse);
      break;
    case Result::Full:
      anim.play(POSE_FULL, 1500, SPR_EMOTES_SWEAT);
      sound.play(Tune::Refuse);
      break;
    case Result::NotNeeded:
      anim.play(POSE_SURPRISED, 1000, SPR_EMOTES_QUESTION);
      sound.play(Tune::Beep);
      break;
    case Result::TooTired:
      anim.play(POSE_SLEEPY, 1500, SPR_EMOTES_SWEAT);
      sound.play(Tune::Refuse);
      break;
    default:
      sound.play(Tune::Beep);
      break;
  }
}

static void handlePetEvents(uint16_t ev) {
  if (!ev) return;
  anim.handleEvents(ev, pet);
  bool wake = false;
  if (ev & EV_HATCHED) { sound.play(Tune::Hatch); wake = true; }
  if (ev & EV_EVOLVED) { sound.play(Tune::Evolve); wake = true; }
  if (ev & EV_DIED) { sound.play(Tune::Death); wake = true; screen = Screen::Dead; }
  if (ev & EV_GOT_SICK) { sound.play(Tune::Sick); wake = true; }
  if (ev & EV_CALL_STARTED) { sound.play(Tune::Call); wake = true; }
  if (wake) {
    setScreenOn(true);
    lastInputMs = millis();
  }
  dirty = true;
}

// ------------------------------------------------------------------ écrans
static void activateMenu(int item) {
  switch (item) {
    case 0:  // manger
      if (pet.isEgg() || pet.isDead()) { sound.play(Tune::Beep); return; }
      screen = Screen::Food;
      cursor = 0;
      break;
    case 1: {  // jouer
      Result r = pet.canPlay();
      if (r == Result::Ok) {
        game = MiniGame{0, 0, false, false, false, false, 0};
        screen = Screen::Game;
        sound.play(Tune::Beep);
      } else {
        react(r, POSE_IDLE, 0, Tune::Beep);
      }
      break;
    }
    case 2:  // nettoyer
      react(pet.clean(), POSE_WASH, 2000, Tune::Happy, NO_SPRITE, SPR_ITEMS_SHOWER);
      break;
    case 3:  // soigner
      react(pet.giveMedicine(), POSE_MEDICINE, 1800, Tune::Beep, SPR_EMOTES_SWEAT, SPR_ITEMS_PILL);
      break;
    case 4:  // lumière
      pet.toggleLight();
      sound.play(Tune::Beep);
      dirty = true;
      break;
    case 5: {  // gronder
      Result r = pet.scold();
      if (r == Result::Ok) {
        anim.play(POSE_SCOLDED, 1800, SPR_EMOTES_SWEAT);
        sound.play(Tune::Refuse);
        dirty = true;
      } else if (r == Result::NotNeeded) {
        anim.play(POSE_CRY, 1800, SPR_EMOTES_TEAR);  // grondé sans raison
        sound.play(Tune::Lose);
        dirty = true;
      } else {
        sound.play(Tune::Beep);
      }
      break;
    }
    case 6:
      screen = Screen::Stats;
      cursor = 0;
      sound.play(Tune::Beep);
      break;
    case 7:
      screen = Screen::Settings;
      cursor = 0;
      sound.play(Tune::Beep);
      break;
  }
}

static void updateMain(uint8_t in, uint32_t now) {
  if (in & IN_B) {
    menuSel = (menuSel + 1) % ui::MENU_ITEMS;
    sound.play(Tune::Beep);
  }
  if (in & IN_PWR) menuSel = -1;
  if (in & IN_A) {
    if (menuSel >= 0) {
      activateMenu(menuSel);
    } else {
      react(pet.caress(), POSE_LOVE, 1500, Tune::Happy, SPR_EMOTES_HEART);
    }
  }
  if ((in & IN_SHAKE) && !anim.busy()) {
    react(pet.caress(), POSE_LOVE, 1500, Tune::Happy, SPR_EMOTES_HEART);
  }
  if (menuSel >= 0 && now - lastInputMs > MENU_DESELECT_MS) menuSel = -1;
}

static void drawMenuList(const char* title, const char* const* items, int n, int sel) {
  ui::drawTitleBar(canvas, title);
  canvas.setFont(&fonts::Font2);
  canvas.setTextDatum(middle_left);
  for (int i = 0; i < n; ++i) {
    int y = 34 + i * 18;
    canvas.setTextColor(i == sel ? ui::COL_ACCENT : (uint16_t)0xFFFF);
    if (i == sel) ui::drawSprite(canvas, SPR_UI_CURSOR, 0, 8, y - 4);
    canvas.drawString(items[i], 22, y);
  }
}

static void updateFood(uint8_t in) {
  if (in & IN_B) { cursor = (cursor + 1) % 2; sound.play(Tune::Beep); }
  if (in & IN_PWR) { screen = Screen::Main; return; }
  if (in & IN_A) {
    screen = Screen::Main;
    if (cursor == 0) {
      react(pet.feedMeal(), POSE_EAT, 2400, Tune::Eat, NO_SPRITE, SPR_ITEMS_MEAL);
    } else {
      react(pet.feedSnack(), POSE_EAT, 2400, Tune::Eat, SPR_EMOTES_HEART, SPR_ITEMS_SNACK);
    }
  }
}

static void drawFood() {
  canvas.fillScreen(ui::COL_PANEL);
  static const char* const items[] = {"Repas   (faim +1)", "Friandise (joie +1)"};
  drawMenuList("Manger", items, 2, cursor);
  ui::drawSprite(canvas, SPR_ITEMS_MEAL, 0, 180, 30, 2);
  ui::drawSprite(canvas, SPR_ITEMS_SNACK, 0, 180, 70, 2);
  ui::drawHint(canvas, "B: suivant  A: donner  PWR: retour");
}

static const int STATS_PAGES = 5;

static void updateStats(uint8_t in) {
  if (in & IN_B) { cursor = (cursor + 1) % STATS_PAGES; sound.play(Tune::Beep); }
  if (in & (IN_A | IN_PWR)) screen = Screen::Main;
}

static void drawStats() {
  const PetData& d = pet.data();
  char buf[48];
  canvas.fillScreen(ui::COL_PANEL);
  canvas.setFont(&fonts::Font2);
  canvas.setTextColor(0xFFFF);
  canvas.setTextDatum(middle_left);
  switch (cursor) {
    case 0:
      ui::drawTitleBar(canvas, "Profil");
      ui::drawSprite(canvas, SPR_UI_CAKE, 0, 16, 30, 2);
      snprintf(buf, sizeof(buf), "Age : %u jour(s)", pet.ageDays());
      canvas.drawString(buf, 56, 46);
      ui::drawSprite(canvas, SPR_UI_SCALE, 0, 16, 70, 2);
      snprintf(buf, sizeof(buf), "Poids : %u g", d.weight);
      canvas.drawString(buf, 56, 86);
      snprintf(buf, sizeof(buf), "Generation %u", d.generation);
      canvas.drawString(buf, 56, 112);
      break;
    case 1:
      ui::drawTitleBar(canvas, "Faim");
      ui::drawHearts(canvas, 80, 55, d.hunger);
      break;
    case 2:
      ui::drawTitleBar(canvas, "Joie");
      ui::drawHearts(canvas, 80, 55, d.happy);
      break;
    case 3:
      ui::drawTitleBar(canvas, "Energie");
      ui::drawHearts(canvas, 80, 55, d.energy);
      break;
    case 4: {
      ui::drawTitleBar(canvas, "Discipline");
      canvas.drawRect(30, 50, 180, 20, 0xFFFF);
      canvas.fillRect(32, 52, 176 * d.discipline / 100, 16, ui::COL_ACCENT);
      snprintf(buf, sizeof(buf), "%u %%", d.discipline);
      canvas.setTextDatum(middle_center);
      canvas.drawString(buf, ui::W / 2, 90);
      snprintf(buf, sizeof(buf), "%02u:%02u   batterie %d%%", pet.hour(), pet.minute(),
               (int)M5.Power.getBatteryLevel());
      canvas.drawString(buf, ui::W / 2, 112);
      break;
    }
  }
  snprintf(buf, sizeof(buf), "%d/%d  B: page suivante  A: retour", cursor + 1, STATS_PAGES);
  ui::drawHint(canvas, buf);
}

// ---- mini-jeu : deviner de quel côté la créature va regarder
static void updateGame(uint8_t in, uint32_t now) {
  if (game.finished) {
    if (now >= game.until) {
      bool won = game.wins >= 3;
      pet.applyGameResult(won);
      anim.play(won ? POSE_WIN : POSE_LOSE, 2000, won ? SPR_EMOTES_STAR : SPR_EMOTES_TEAR);
      sound.play(won ? Tune::Win : Tune::Lose);
      screen = Screen::Main;
      dirty = true;
    }
    return;
  }
  if (game.revealing) {
    if (now >= game.until) {
      game.revealing = false;
      game.round++;
      if (game.round >= 5) {
        game.finished = true;
        game.until = now + 1500;
      }
    }
    return;
  }
  if (in & IN_PWR) { screen = Screen::Main; return; }
  if (in & (IN_A | IN_B)) {
    game.guessLeft = (in & IN_A) != 0;
    game.lookLeft = esp_random() & 1;
    bool ok = game.guessLeft == game.lookLeft;
    if (ok) game.wins++;
    anim.play(game.lookLeft ? POSE_LOOK_LEFT : POSE_LOOK_RIGHT, 900, ok ? SPR_EMOTES_HEART : SPR_EMOTES_ANGER);
    sound.play(ok ? Tune::Happy : Tune::Refuse);
    game.revealing = true;
    game.until = now + 1000;
  }
}

static void drawGame(const View& v) {
  ui::drawBackground(canvas, BG_GAME, 0x4D3F);
  if (!BACKGROUNDS[BG_GAME]) canvas.fillRect(0, ui::GROUND_Y, ui::W, ui::H - ui::GROUND_Y, ui::COL_GROUND);
  char buf[32];
  canvas.setFont(&fonts::Font2);
  canvas.setTextDatum(top_left);
  snprintf(buf, sizeof(buf), "Manche %d/5", game.round < 5 ? game.round + 1 : 5);
  ui::drawShadowText(canvas, buf, 4, 2, 0xFFFF);
  canvas.setTextDatum(top_right);
  snprintf(buf, sizeof(buf), "Gagne %d", game.wins);
  ui::drawShadowText(canvas, buf, ui::W - 4, 2, 0xFFFF);
  // créature au centre
  const int size = 32 * ui::CREATURE_SCALE;
  PoseId pose = anim.busy() ? v.pose : POSE_IDLE;
  const Anim& a = CREATURE_ANIMS[v.stage][pose];
  ui::drawSprite(canvas, a, anim.busy() ? v.frame : (millis() / 450) % a.count, ui::W / 2 - size / 2,
                 ui::GROUND_Y - size, ui::CREATURE_SCALE);
  if (!game.revealing && !game.finished) {
    ui::drawSprite(canvas, SPR_EMOTES_QUESTION, 0, ui::W / 2 + 24, 22, 2);
    ui::drawSprite(canvas, SPR_UI_ARROW_LEFT, 0, 12, 70, 2);
    ui::drawSprite(canvas, SPR_UI_ARROW_RIGHT, 0, ui::W - 28, 70, 2);
    canvas.setTextDatum(middle_center);
    ui::drawShadowText(canvas, "A", 20, 100, 0xFFFF);
    ui::drawShadowText(canvas, "B", ui::W - 20, 100, 0xFFFF);
  } else if (v.emote >= 0) {
    ui::drawSprite(canvas, SPRITES[v.emote], v.emoteFrame, ui::W / 2 + 24, 22, 2);
  }
  if (game.finished) {
    canvas.setTextDatum(middle_center);
    ui::drawShadowText(canvas, game.wins >= 3 ? "Gagne !" : "Perdu...", ui::W / 2, 30, ui::COL_ACCENT);
  }
}

static const int SETTINGS_ITEMS = 6;

static void updateSettings(uint8_t in, uint32_t now) {
  if (in & IN_B) { cursor = (cursor + 1) % SETTINGS_ITEMS; confirmUntil = 0; sound.play(Tune::Beep); }
  if (in & IN_PWR) { screen = Screen::Main; save(); return; }
  if (!(in & IN_A)) return;
  switch (cursor) {
    case 0: settings.sound = !settings.sound; applySettings(); break;
    case 1: settings.speedIdx = (settings.speedIdx + 1) % sizeof(SPEEDS); break;
    case 2: settings.brightIdx = (settings.brightIdx + 1) % sizeof(BRIGHTNESS); applySettings(); break;
    case 3: screen = Screen::Clock; break;
    case 4:
      if (confirmUntil > now) {
        confirmUntil = 0;
        startNewEgg(pet.data().generation + 1);
      } else {
        confirmUntil = now + 3000;
      }
      break;
    case 5: screen = Screen::Main; break;
  }
  sound.play(Tune::Beep);
  save();
}

static void drawSettings(uint32_t now) {
  char l0[24], l1[24], l2[24];
  snprintf(l0, sizeof(l0), "Son : %s", settings.sound ? "oui" : "non");
  snprintf(l1, sizeof(l1), "Vitesse : x%u", SPEEDS[settings.speedIdx]);
  snprintf(l2, sizeof(l2), "Luminosite : %u/4", settings.brightIdx + 1);
  const char* items[] = {l0, l1, l2, "Regler l'heure",
                         confirmUntil > now ? "Nouvel oeuf : A pour confirmer" : "Nouvel oeuf", "Retour"};
  canvas.fillScreen(ui::COL_PANEL);
  drawMenuList("Reglages", items, SETTINGS_ITEMS, cursor);
  ui::drawSprite(canvas, settings.sound ? SPR_UI_SOUND_ON : SPR_UI_SOUND_OFF, 0, ui::W - 22, 6);
}

static void updateClock(uint8_t in) {
  uint32_t c = pet.data().clock;
  if (in & IN_B) pet.setClock(c - (c % 86400) + ((c / 3600 + 1) % 24) * 3600 + c % 3600);
  if (in & IN_A) {
    uint32_t m = (c / 60) % 60;
    pet.setClock(c - m * 60 + ((m / 5 * 5 + 5) % 60) * 60 - (c % 60));
  }
  if (in & IN_PWR) {
    writeRtc(pet.data().clock);
    lastRtc = pet.data().clock;
    screen = Screen::Settings;
    save();
  }
}

static void drawClock() {
  char buf[16];
  canvas.fillScreen(ui::COL_PANEL);
  ui::drawTitleBar(canvas, "Regler l'heure");
  snprintf(buf, sizeof(buf), "%02u:%02u", pet.hour(), pet.minute());
  canvas.setFont(&fonts::Font7);
  canvas.setTextColor(ui::COL_ACCENT);
  canvas.setTextDatum(middle_center);
  canvas.drawString(buf, ui::W / 2, 70);
  ui::drawHint(canvas, "B: heure+1  A: minutes+5  PWR: valider");
}

static void updateDead(uint8_t in, uint32_t now) {
  if (newEggAt && now >= newEggAt) {
    newEggAt = 0;
    startNewEgg(pet.data().generation + 1);
    return;
  }
  if ((in & IN_A) && !anim.busy() && !newEggAt) {
    anim.playStage(STAGE_GHOST, POSE_ASCEND, 2100);
    newEggAt = now + 2100;
  }
}

// ------------------------------------------------------------------ Arduino
void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  M5.Display.setRotation(1);  // paysage 240x135
  M5.Speaker.setVolume(96);
  canvas.setColorDepth(16);
  canvas.createSprite(ui::W, ui::H);

  rtcOk = M5.Rtc.isEnabled();
  if (rtcOk) {
    auto dt = M5.Rtc.getDateTime();
    if (dt.date.year < 2024) writeRtc(timeutil::toSeconds({2026, 1, 1, 12, 0, 0}));
  }
  // écran titre
  ui::drawBackground(canvas, BG_TITLE, ui::COL_PANEL);
  canvas.setFont(&fonts::Font4);
  canvas.setTextDatum(middle_center);
  ui::drawShadowText(canvas, "Tamagochi", ui::W / 2, BACKGROUNDS[BG_TITLE] ? 28 : 50, ui::COL_ACCENT);
  if (!BACKGROUNDS[BG_TITLE]) {
    ui::drawSprite(canvas, CREATURE_ANIMS[STAGE_EGG][POSE_IDLE], 0, ui::W / 2 - 32, 70, 2);
  }
  canvas.pushSprite(0, 0);
  delay(1500);

  load();
  anim.reset(millis());
  if (pet.isDead()) screen = Screen::Dead;
  lastInputMs = lastTickMs = lastSaveMs = millis();
}

void loop() {
  M5.update();
  const uint32_t now = millis();
  uint8_t in = readInput(now);

  if (in) {
    lastInputMs = now;
    if (!screenOn) {
      setScreenOn(true);
      in = IN_NONE;  // le premier appui ne fait que rallumer l'écran
    }
  }

  // ---- temps de jeu
  gameMsAcc += (now - lastTickMs) * SPEEDS[settings.speedIdx];
  lastTickMs = now;
  if (gameMsAcc >= 1000) {
    pet.tick(gameMsAcc / 1000);
    gameMsAcc %= 1000;
  }
  handlePetEvents(pet.takeEvents());

  // ---- écran courant
  switch (screen) {
    case Screen::Main:
      if (pet.isDead()) screen = Screen::Dead;
      else updateMain(in, now);
      break;
    case Screen::Food: updateFood(in); break;
    case Screen::Stats: updateStats(in); break;
    case Screen::Game: updateGame(in, now); break;
    case Screen::Settings: updateSettings(in, now); break;
    case Screen::Clock: updateClock(in); break;
    case Screen::Dead: updateDead(in, now); break;
  }
  anim.update(pet, now);
  sound.update(now);

  // ---- rendu
  if (screenOn && now - lastFrameMs >= FRAME_MS) {
    lastFrameMs = now;
    bool blink = (now / 500) % 2;
    switch (screen) {
      case Screen::Main:
      case Screen::Dead:
        ui::drawMain(canvas, pet, anim.view(), menuSel, blink);
        if (screen == Screen::Dead && !anim.busy()) ui::drawHint(canvas, "A : nouvel oeuf");
        break;
      case Screen::Food: drawFood(); break;
      case Screen::Stats: drawStats(); break;
      case Screen::Game: drawGame(anim.view()); break;
      case Screen::Settings: drawSettings(now); break;
      case Screen::Clock: drawClock(); break;
    }
    canvas.pushSprite(0, 0);
  }

  // ---- veille écran & sauvegarde
  if (screenOn && screen != Screen::Game && now - lastInputMs > SCREEN_TIMEOUT_MS) {
    setScreenOn(false);
    menuSel = -1;
    if (screen != Screen::Dead) screen = Screen::Main;
  }
  if (dirty && now - lastSaveMs > 20000) {
    save();
    lastSaveMs = now;
  } else if (now - lastSaveMs > SAVE_EVERY_MS) {
    save();
    lastSaveMs = now;
  }
  delay(screenOn ? 5 : 50);
}
