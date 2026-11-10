// Dessin sur le canvas hors écran (double buffer).
#pragma once
#include <M5Unified.h>

#include "Animator.h"
#include "Pet.h"

namespace ui {

static const int W = 240;
static const int H = 135;
static const int GROUND_Y = 131;   // ligne du sol
static const int CREATURE_SCALE = 3;
static const int MENU_ITEMS = 8;

// couleurs RGB565
static const uint16_t COL_BG_DAY = 0xEF5D;
static const uint16_t COL_BG_NIGHT = 0x10A2;
static const uint16_t COL_BG_SICK = 0xC7F5;
static const uint16_t COL_GROUND = 0xAD55;
static const uint16_t COL_TEXT = 0x18E3;
static const uint16_t COL_PANEL = 0x2124;
static const uint16_t COL_ACCENT = 0xFEA0;

// Dessine un sprite RGB565 agrandi, avec transparence et miroir.
void drawSprite(M5Canvas& c, const Anim& a, uint8_t frame, int x, int y, int scale, bool flip = false,
                bool silhouette = false);
inline void drawSprite(M5Canvas& c, SpriteId id, uint8_t frame, int x, int y, int scale = 1) {
  drawSprite(c, SPRITES[id], frame, x, y, scale);
}

void drawBackground(M5Canvas& c, BgId id, uint16_t fallback);
void drawMain(M5Canvas& c, const tama::Pet& pet, const View& v, int selected, bool blinkOn);
void drawHearts(M5Canvas& c, int x, int y, uint8_t value, uint8_t max = 4);
void drawTitleBar(M5Canvas& c, const char* title);
void drawHint(M5Canvas& c, const char* text);

}  // namespace ui
