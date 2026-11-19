#include "Animator.h"

using namespace tama;

static const int16_t MIN_X = 56;
static const int16_t MAX_X = 170;

uint32_t Animator::rnd(uint32_t n) {
  seed_ ^= seed_ << 13;
  seed_ ^= seed_ >> 17;
  seed_ ^= seed_ << 5;
  return n ? seed_ % n : seed_;
}

void Animator::reset(uint32_t nowMs) {
  view_ = View{};
  view_.x = 120;
  view_.emote = NO_SPRITE;
  view_.item = NO_SPRITE;
  fx_ = 120;
  targetX_ = 120;
  now_ = lastMs_ = poseStart_ = nowMs;
  actionUntil_ = 0;
  seed_ ^= nowMs * 2654435761u;
}

StageId Animator::stageFor(const Pet& pet) {
  switch (pet.life()) {
    case Life::Egg: return STAGE_EGG;
    case Life::Baby: return STAGE_BABY;
    case Life::Child: return STAGE_CHILD;
    case Life::Teen: return STAGE_TEEN;
    case Life::Adult:
      switch (pet.data().adultKind) {
        case AdultKind::Good: return STAGE_ADULT_GOOD;
        case AdultKind::Mid: return STAGE_ADULT_MID;
        default: return STAGE_ADULT_BAD;
      }
    case Life::Senior: return STAGE_SENIOR;
    default: return STAGE_GHOST;
  }
}

uint16_t Animator::frameMs(PoseId pose) {
  switch (pose) {
    case POSE_WALK: return 250;
    case POSE_EAT: return 300;
    case POSE_REFUSE: return 200;
    case POSE_VERY_HAPPY:
    case POSE_WIN:
    case POSE_CALL: return 250;
    case POSE_SLEEP: return 900;
    case POSE_SICK:
    case POSE_DYING: return 600;
    case POSE_CRACK: return 500;
    case POSE_HATCH: return 400;
    case POSE_ASCEND: return 700;
    default: return 450;
  }
}

void Animator::play(PoseId pose, uint32_t ms, int16_t emote, int16_t item) {
  actionPose_ = pose;
  actionEmote_ = emote;
  actionItem_ = item;
  actionStage_ = -1;
  actionStart_ = now_;
  actionUntil_ = now_ + ms;
}

void Animator::playStage(StageId stage, PoseId pose, uint32_t ms, int16_t emote) {
  play(pose, ms, emote);
  actionStage_ = stage;
}

void Animator::handleEvents(uint16_t ev, const Pet& pet) {
  if (ev & EV_HATCHED) playStage(STAGE_EGG, POSE_HATCH, 1600);
  if (ev & EV_EVOLVED) {
    play(POSE_EVOLVE, 2400, SPR_FX_SPARKLE);
  }
  if (ev & EV_DIED) playStage(lastLivingStage_, POSE_DEAD, 5000);
  if ((ev & EV_POOPED) && !busy()) play(POSE_POOP, 1500, SPR_EMOTES_SWEAT);
  if ((ev & EV_GOT_SICK) && !busy()) play(POSE_SICK, 2000, SPR_EMOTES_SKULL);
  if ((ev & EV_CURED) && !busy()) play(POSE_HAPPY, 1500, SPR_EMOTES_NOTE);
  if ((ev & EV_WOKE_UP) && !busy()) play(POSE_WAKE_UP, 1500);
  if ((ev & EV_FELL_ASLEEP) && !busy() && pet.life() != Life::Baby) play(POSE_SLEEPY, 1500);
  (void)pet;
}

void Animator::basePose(const Pet& pet, PoseId& pose, int16_t& emote) {
  const PetData& d = pet.data();
  emote = NO_SPRITE;
  pose = POSE_IDLE;
  switch (pet.life()) {
    case Life::Egg:
      pose = d.stageSec >= 50 ? POSE_CRACK : (d.stageSec >= 35 ? POSE_WOBBLE : POSE_IDLE);
      return;
    case Life::Dead:
      pose = POSE_IDLE;
      return;
    default:
      break;
  }
  if (d.dying) { pose = POSE_DYING; emote = SPR_EMOTES_SKULL; return; }
  if (d.sleeping) { pose = POSE_SLEEP; emote = SPR_EMOTES_ZZZ; return; }
  if (pet.isSick()) { pose = POSE_SICK; emote = SPR_EMOTES_SKULL; return; }
  if (d.calls & CALL_FAKE) { pose = POSE_CALL; emote = SPR_EMOTES_EXCLAIM; return; }
  if (d.hunger == 0) { pose = POSE_HUNGRY; emote = SPR_EMOTES_FOOD_BUBBLE; return; }
  if (d.happy == 0) { pose = POSE_CRY; emote = SPR_EMOTES_BROKEN_HEART; return; }
  if (d.poops >= 2) { pose = POSE_DIRTY; emote = SPR_EMOTES_STINK; return; }
  if (d.energy == 0) { pose = POSE_SLEEPY; return; }
  if (d.happy == 1) { pose = POSE_SAD; return; }
  if (d.hunger == 1 || d.happy == 2) { pose = POSE_BORED; return; }
  pose = POSE_IDLE;  // idle / walk décidé par wander()
  if (d.happy >= 4 && d.hunger >= 3) emote = SPR_EMOTES_NOTE;
}

void Animator::wander(uint32_t dtMs) {
  if (now_ < idleUntil_) return;
  float step = dtMs * 0.02f;  // 20 px/s
  if (fx_ < targetX_ - 1) {
    fx_ += step;
    view_.faceLeft = false;
  } else if (fx_ > targetX_ + 1) {
    fx_ -= step;
    view_.faceLeft = true;
  } else {
    idleUntil_ = now_ + 2000 + rnd(4000);
    targetX_ = MIN_X + rnd(MAX_X - MIN_X);
  }
}

void Animator::update(const Pet& pet, uint32_t nowMs) {
  uint32_t dt = nowMs - lastMs_;
  lastMs_ = now_ = nowMs;

  StageId stage = stageFor(pet);
  if (pet.life() != Life::Dead && pet.life() != Life::Egg) lastLivingStage_ = stage;

  PoseId pose;
  int16_t emote;
  int16_t item = NO_SPRITE;
  bool walking = false;

  if (busy()) {
    pose = actionPose_;
    emote = actionEmote_;
    item = actionItem_;
    if (actionStage_ >= 0) stage = (StageId)actionStage_;
  } else {
    basePose(pet, pose, emote);
    bool canMove = pose == POSE_IDLE && pet.life() != Life::Egg && pet.life() != Life::Dead;
    if (canMove) {
      wander(dt);
      walking = now_ >= idleUntil_;
      if (walking) {
        pose = POSE_WALK;
      } else if (now_ >= nextBlink_) {
        pose = POSE_BLINK;
        if (now_ >= nextBlink_ + 180) nextBlink_ = now_ + 2500 + rnd(3000);
      }
    } else if (pet.life() == Life::Egg || pet.life() == Life::Dead) {
      fx_ = 120;
    }
  }

  if (pose != lastPose_) {
    lastPose_ = pose;
    poseStart_ = now_;
  }
  const Anim& a = CREATURE_ANIMS[stage][pose];
  uint32_t elapsed = now_ - (busy() ? actionStart_ : poseStart_);
  uint32_t idx = elapsed / frameMs(pose);
  // les animations ponctuelles ne bouclent pas pour certaines poses
  bool oneShot = busy() && (pose == POSE_HATCH || pose == POSE_CRACK || pose == POSE_ASCEND);
  view_.frame = a.count ? (oneShot ? (idx < a.count ? idx : a.count - 1) : idx % a.count) : 0;

  view_.stage = stage;
  view_.pose = pose;
  view_.x = (int16_t)fx_;
  if (!walking && pose != POSE_WALK) {
    // en dehors de la marche, garder l'orientation (droite par défaut pour les poses directionnelles)
    if (pose == POSE_LOOK_LEFT || pose == POSE_LOOK_RIGHT) view_.faceLeft = false;
  }
  view_.emote = emote;
  view_.emoteFrame = emote >= 0 ? (now_ / 500) % SPRITES[emote].count : 0;
  view_.item = item;
  if (item >= 0) {
    uint32_t total = actionUntil_ - actionStart_;
    uint32_t n = SPRITES[item].count;
    uint32_t i = total ? (elapsed * n) / total : 0;
    view_.itemFrame = i < n ? i : n - 1;
  }
  view_.flash = busy() && pose == POSE_EVOLVE && ((now_ / 150) % 2 == 0);
}
