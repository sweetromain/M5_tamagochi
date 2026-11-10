// Choisit quelle pose / émotion afficher à partir de l'état de la créature.
// Aucune dépendance matérielle.
#pragma once
#include <stdint.h>

#include "Pet.h"
#include "generated/sprites_gen.h"

static const int16_t NO_SPRITE = -1;

struct View {
  StageId stage;
  PoseId pose;
  uint8_t frame;
  int16_t x;        // centre horizontal de la créature (pixels écran)
  bool faceLeft;
  int16_t emote;    // SpriteId ou NO_SPRITE
  uint8_t emoteFrame;
  int16_t item;     // SpriteId (objet tenu / mangé) ou NO_SPRITE
  uint8_t itemFrame;
  bool flash;       // évolution : clignotement blanc
};

class Animator {
 public:
  void reset(uint32_t nowMs);
  // Joue une animation ponctuelle (manger, gronder, victoire...) pendant `ms`.
  void play(PoseId pose, uint32_t ms, int16_t emote = NO_SPRITE, int16_t item = NO_SPRITE);
  // Comme play() mais force aussi le stade affiché (éclosion, mort...)
  void playStage(StageId stage, PoseId pose, uint32_t ms, int16_t emote = NO_SPRITE);
  void handleEvents(uint16_t events, const tama::Pet& pet);
  void update(const tama::Pet& pet, uint32_t nowMs);
  bool busy() const { return actionUntil_ > now_; }
  const View& view() const { return view_; }

  static StageId stageFor(const tama::Pet& pet);
  static uint16_t frameMs(PoseId pose);

 private:
  void basePose(const tama::Pet& pet, PoseId& pose, int16_t& emote);
  void wander(uint32_t dtMs);
  uint32_t rnd(uint32_t n);

  View view_{};
  uint32_t now_ = 0;
  uint32_t lastMs_ = 0;
  uint32_t poseStart_ = 0;
  PoseId lastPose_ = POSE_IDLE;

  // action ponctuelle
  uint32_t actionStart_ = 0;
  uint32_t actionUntil_ = 0;
  PoseId actionPose_ = POSE_IDLE;
  int16_t actionEmote_ = NO_SPRITE;
  int16_t actionItem_ = NO_SPRITE;
  int16_t actionStage_ = -1;
  StageId lastLivingStage_ = STAGE_BABY;

  // déplacement
  int16_t targetX_ = 120;
  uint32_t idleUntil_ = 0;
  uint32_t nextBlink_ = 0;
  float fx_ = 120;
  uint32_t seed_ = 0xC0FFEE;
};
