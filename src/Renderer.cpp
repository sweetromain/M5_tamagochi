#include "Renderer.h"

namespace ui {

static const SpriteId MENU_ICONS[MENU_ITEMS][2] = {
    {SPR_ICONS_FOOD, SPR_ICONS_FOOD_SEL},
    {SPR_ICONS_PLAY, SPR_ICONS_PLAY_SEL},
    {SPR_ICONS_CLEAN, SPR_ICONS_CLEAN_SEL},
    {SPR_ICONS_MEDICINE, SPR_ICONS_MEDICINE_SEL},
    {SPR_ICONS_LIGHT, SPR_ICONS_LIGHT_SEL},
    {SPR_ICONS_DISCIPLINE, SPR_ICONS_DISCIPLINE_SEL},
    {SPR_ICONS_STATS, SPR_ICONS_STATS_SEL},
    {SPR_ICONS_SETTINGS, SPR_ICONS_SETTINGS_SEL},
};

void drawSprite(M5Canvas& c, const Anim& a, uint8_t frame, int x, int y, int scale, bool flip, bool silhouette) {
  if (!a.count) return;
  if (frame >= a.count) frame = a.count - 1;
  const uint16_t* px = a.frames[frame];
  const bool mirror = flip != a.flip;
  for (int j = 0; j < a.h; ++j) {
    const int dy = y + j * scale;
    if (dy + scale <= 0 || dy >= H) continue;
    // regroupe les pixels identiques consécutifs en un seul rectangle
    int i = 0;
    while (i < a.w) {
      uint16_t col = px[j * a.w + (mirror ? a.w - 1 - i : i)];
      int run = 1;
      while (i + run < a.w && px[j * a.w + (mirror ? a.w - 1 - (i + run) : i + run)] == col) ++run;
      if (col != SPRITE_TRANSPARENT) {
        c.fillRect(x + i * scale, dy, run * scale, scale, silhouette ? (uint16_t)0xFFFF : col);
      }
      i += run;
    }
  }
}

void drawBackground(M5Canvas& c, BgId id, uint16_t fallback) {
  if (BACKGROUNDS[id]) {
    c.pushImage(0, 0, W, H, (const lgfx::rgb565_t*)BACKGROUNDS[id]);
  } else {
    c.fillScreen(fallback);
  }
}

void drawHearts(M5Canvas& c, int x, int y, uint8_t value, uint8_t max) {
  for (uint8_t i = 0; i < max; ++i) {
    drawSprite(c, i < value ? SPR_UI_HEART_FULL : SPR_UI_HEART_EMPTY, 0, x + i * 20, y, 2);
  }
}

void drawTitleBar(M5Canvas& c, const char* title) {
  c.fillRect(0, 0, W, 20, COL_PANEL);
  c.setTextColor(COL_ACCENT);
  c.setTextDatum(middle_center);
  c.setFont(&fonts::Font2);
  c.drawString(title, W / 2, 10);
}

void drawHint(M5Canvas& c, const char* text) {
  c.setTextColor(0x8410);
  c.setTextDatum(bottom_center);
  c.setFont(&fonts::Font0);
  c.drawString(text, W / 2, H - 2);
}

void drawMain(M5Canvas& c, const tama::Pet& pet, const View& v, int selected, bool blinkOn) {
  const tama::PetData& d = pet.data();
  const bool night = d.lightsOff;

  // ---- fond
  if (night) {
    drawBackground(c, BG_NIGHT, COL_BG_NIGHT);
  } else if (pet.isSick()) {
    drawBackground(c, BG_SICK, COL_BG_SICK);
  } else {
    drawBackground(c, BG_DAY, COL_BG_DAY);
  }
  if (!BACKGROUNDS[BG_DAY] || night) {
    c.fillRect(0, GROUND_Y, W, H - GROUND_Y, night ? (uint16_t)0x0841 : COL_GROUND);
  }

  // ---- barre de menu
  c.fillRect(0, 0, W, 19, night ? (uint16_t)0x0000 : COL_PANEL);
  for (int i = 0; i < MENU_ITEMS; ++i) {
    drawSprite(c, MENU_ICONS[i][i == selected ? 1 : 0], 0, 4 + i * 24, 1);
  }
  if (pet.isCalling()) {
    drawSprite(c, SPR_ICONS_ATTENTION, blinkOn ? 0 : 1, W - 20, 1);
  }

  // ---- créature
  const int size = 32 * CREATURE_SCALE;
  const int cx = v.x - size / 2;
  const int cy = GROUND_Y - size;

  if (pet.isDead()) {
    drawSprite(c, SPR_ITEMS_TOMBSTONE, 0, 150, GROUND_Y - 64, 2);
  }
  if (d.sleeping && !night) {
    // lit sous la créature qui dort
    drawSprite(c, SPR_ITEMS_BED, 0, cx, GROUND_Y - 24, CREATURE_SCALE);
  }
  if (!night || d.sleeping || pet.isDead()) {
    const Anim& a = CREATURE_ANIMS[v.stage][v.pose];
    drawSprite(c, a, v.frame, cx, cy, CREATURE_SCALE, v.faceLeft, v.flash);
  }

  // ---- objet (repas, médicament...) devant la bouche
  if (v.item >= 0) {
    const Anim& it = SPRITES[v.item];
    drawSprite(c, it, v.itemFrame, v.faceLeft ? cx - it.w * 2 + 8 : cx + size - 8, GROUND_Y - it.h * 2, 2);
  }

  // ---- bulle d'émotion au-dessus de la tête
  if (v.emote >= 0) {
    const Anim& e = SPRITES[v.emote];
    if (e.w >= 32) {
      drawSprite(c, e, v.emoteFrame, cx, cy, CREATURE_SCALE);  // effets plein corps
    } else {
      int ex = v.faceLeft ? cx - 8 : cx + size - 24;
      drawSprite(c, e, v.emoteFrame, ex, 20, 2);
    }
  }

  // ---- cacas (colonne à droite)
  for (int i = 0; i < d.poops; ++i) {
    int px = (i % 2) ? W - 34 : W - 66;
    if (v.x > W - 90) px -= 150;  // évite de recouvrir la créature
    int py = GROUND_Y - 32 - (i / 2) * 34;
    drawSprite(c, SPR_ITEMS_POOP, (blinkOn ? 1 : 0), px, py, 2);
  }

  // ---- nuit : texte discret
  if (night && !d.sleeping && !pet.isDead()) {
    c.setTextColor(0x8410);
    c.setTextDatum(middle_center);
    c.setFont(&fonts::Font2);
    c.drawString("Zzz... lumiere eteinte", W / 2, 75);
  }
}

}  // namespace ui
