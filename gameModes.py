# -*- coding: utf-8 -*-
# Screaming Strike game mode handlers
# Copyright (C) 2019 Yukio Nozawa <personal@nyanchangames.com>
# License: GPL V2.0 (See copying.txt for details)
import math
import random
import bonusCounter
import enemy
import item
import itemConstants
import window

NORMAL = 0
ARCADE = 1
CLASSIC = 2
BURDEN = 3
CHAOS = 4
YOLO = 5
ALL_MODES_STR = ["Normal", "Arcade", "Classic", "Burden", "Chaos", "Yolo"]
# Local-only, for-fun modes: completely excluded from the online scoreboard (no posting, no viewing).
LOCAL_ONLY_MODES = [ALL_MODES_STR[CHAOS], ALL_MODES_STR[YOLO]]


def isScoreboardEnabled(mode):
    """Whether the given mode participates in the online scoreboard (posting and viewing).

    :param mode: Mode string.
    :rtype: bool
    """
    return mode not in LOCAL_ONLY_MODES


class ModeHandlerBase(object):
    def __init__(self):
        self.allowConsecutiveHitsBonus = True
        # Originally this was true, but I decided to disable it because the one of
        # my friends (a professional game designer) said "In the game designing
        # theory, subtracting scores is a totally bad idea!". And the penalty was
        # very irritating, actually. lol!
        self.allowConsecutiveMissesBonus = False
        self.allowLevelupBonus = True
        self.name = "Base"
        self.paused = False

    def initialize(self, field):
        self.field = field

    def frameUpdate(self):
        pass

    def calculateNextLevelup(self):
        """
        Calculates the number of enemies that should be defeated in this mode. This function implements the default formula.
        """
        if self.field.level == 1:
            return 2
        r = int(1 + (self.field.level * self.field.level * 0.25))
        if r > 60:
            r = 60
        return r

    def calculateEnemyDefeatScore(self, speed, y):
        """Calculates score by enemy defeat. Since the object references are not organized, I just give up on refactoring it and gather information in a dirty way, if needed. Receives speed and y coors from the defeated enemy."""
        score = (1000 - speed) * (y + 1) * (0.5 + (0.5 * self.field.level)) * 0.1
        if self.field.player.penetrate:
            score = score * 2.0
        return score

    def getDefeatMessage(self, speed, y):
        """Generates log message for enemy defeat."""
        if self.field.player.penetrate:
            return _("Hit! (speed %(speed)d, distance %(distance)d, penetration bonus added)") % {"speed": 900 - speed, "distance": y}
        else:
            return _("Hit! (speed %(speed)d, distance %(distance)d)") % {"speed": 900 - speed, "distance": y}
        # end penetration bonus?

    def getShrinkMultiplier(self):
        """
                Defines the multiplier amount of the shrink item effect in this mode, Default is 0.5 (half length).

                :rtype multiplier: float
        """
        return 0.5

    def getSlowDownMultiplier(self):
        """
                Defines the multiplier amount of the slow down item effect in this mode, Default is 2.0 (2x motion time).

                :rtype multiplier: float
        """
        return 2.0

    def getMaxBlurredStacks(self):
        """Maximum number of simultaneously active Blurred effects, or None for no limit."""
        return None

    def getMinPunchDelay(self):
        """Minimum punch delay in ms (floor that boosts may not push below), or None for no limit."""
        return None

    def getMaxPunchDelay(self):
        """Maximum punch delay in ms (cap that slow downs may not push above), or None for no limit."""
        return None

    def getMaxLives(self):
        """Maximum number of lives (HP cap), or None for no limit."""
        return None

    def getMaxDestructionShields(self):
        """Maximum number of stored destruction shields (autoDestructionRemaining), or None for no limit."""
        return None

    def getExtraLifeOverflowBonus(self):
        """Bonus score granted when an Extra life is obtained while already at the life cap. Default 0."""
        return 0

    def onEnemyDefeated(self, x=None, y=None):
        """Called when the player defeated an enemy. x / y are the grid coordinates of the defeated enemy (may be None when unknown)."""
        pass

    def onItemObtained(self, it=None):
        """Called when the player got an item. it is the obtained item.Item instance (may be None when unknown)."""
        pass

    def onItemMissed(self, it=None):
        """Called when an item fell to the ground without being obtained. it is the missed item.Item instance."""
        pass

    def onItemPunchedAway(self, it=None):
        """Called when the player deliberately destroyed an item by punching it with the UP arrow held. it is the destroyed item.Item instance."""
        pass

    def shouldObtainOnDestruction(self, it):
        """Decides what the Destruction effect does with an item. Default: good items are obtained, nasty items are destroyed."""
        return it.type == itemConstants.TYPE_GOOD

    def onEnemyDefeatedByDestruction(self, x=None, y=None):
        """Called for each enemy cleared by the Destruction effect. Kept separate from onEnemyDefeated so Burden's bonus logic is not triggered here. Default no-op."""
        pass

    def getName(self):
        """
        Retrieves the name of this mode. Normal, arcade or classic. There may be more future modes.

        :rtype: str
        """
        return self.name

    def setPaused(self, p):
        """Pauses / resumes this mode handler."""
        pass

    def getModeSpecificResults(self):
        """Can set the modes's specific result data in the game end. Return the array of strings to show at the result screen, otherwise, return an empty array."""
        return []

    def getModeSpecificResultsForScoreboard(self):
        """Can set the modes's specific result data when sending score. Return the string to be shown to the scoreboard, otherwise, return an empty string."""
        return ""


class NormalModeHandler(ModeHandlerBase):
    def __init__(self):
        super().__init__()
        self.name = ALL_MODES_STR[0]

    def initialize(self, field):
        super().initialize(field)


class ArcadeModeHandler(ModeHandlerBase):
    def __init__(self):
        super().__init__()
        self.name = ALL_MODES_STR[1]

    def initialize(self, field):
        super().initialize(field)
        self.itemComingTimer = window.Timer()
        self.resetItemComingTimer()
        self.itemShowerTimer = window.Timer()
        self.resetItemShower()

    def frameUpdate(self):
        if self.itemShowerTimer.elapsed >= self.itemShowerTime:
            self.triggerItemShower()
        if self.itemComingTimer.elapsed >= self.itemComingTime:
            self.spawnItem()

    def setPaused(self, p):
        if p == self.paused:
            return
        self.paused = p
        self.itemComingTimer.setPaused(p)
        self.itemShowerTimer.setPaused(p)
    # end setPaused

    def triggerItemShower(self):
        self.spawnItem()
        self.itemShowerCount -= 1
        if self.itemShowerCount == 0:
            self.resetItemShower()
        else:
            self.itemShowerTime = 150
            self.itemShowerTimer.restart()

    def resetItemShower(self):
        self.itemShowerTime = random.randint(70000, 150000)
        self.itemShowerCount = random.randint(3, 6)

    def spawnItem(self):
        spd = random.randint(100, 800)
        t = itemConstants.TYPE_NASTY if random.randint(1, 100) <= spd / 10 else itemConstants.TYPE_GOOD
        ident = self.selectNastyItem() if t == item.TYPE_NASTY else random.randint(0, item.GOOD_MAX)
        i = item.Item()
        i.initialize(self.field, random.randint(0, self.field.x - 1), spd, t, ident)
        self.field.items.append(i)
        self.resetItemComingTimer()

    def selectNastyItem(self):
        """Prevents shrink from appearing when the player already has 2 shrink effects."""
        shrinks = len([e for e in self.field.player.itemEffects if e.name ==
                       itemConstants.NAMES[itemConstants.TYPE_NASTY][itemConstants.NASTY_SHRINK]])
        while(True):
            ret = random.randint(0, itemConstants.NASTY_MAX)
            if ret == itemConstants.NASTY_SHRINK and shrinks == 2:
                continue
            break
        return ret

    def resetItemComingTimer(self):
        self.itemComingTimer.restart()
        self.itemComingTime = random.randint(0, 60000)


class ClassicModeHandler(ModeHandlerBase):
    def __init__(self):
        super().__init__()
        # disable bonuses
        self.allowConsecutiveHitsBonus = False
        self.allowConsecutiveMissesBonus = False
        self.allowLevelupBonus = False
        self.name = ALL_MODES_STR[2]

    def calculateNextLevelup(self):
        """
        This function provides classic mode specific formula.
        """
        return int((2 + self.field.level) * 0.7)


class BurdenModeHandler(ModeHandlerBase):
    def __init__(self):
        super().__init__()
        # disable bonuses
        self.allowConsecutiveHitsBonus = False
        self.allowConsecutiveMissesBonus = False
        self.allowLevelupBonus = False
        self.name = ALL_MODES_STR[3]
        self.bonusCounters = []
        self.highestBoost = 1.0

    def initialize(self, field):
        super().initialize(field)
        self.itemComingTimer = window.Timer()
        self.resetItemComingTimer()
        self.itemShowerTimer = window.Timer()
        self.resetItemShower()

    def calculateEnemyDefeatScore(self, speed, y):
        """Uses completely different formula for burden mode."""
        boost = math.pow(1.45 + (self.field.level * 0.05), len(self.field.player.itemEffects))
        # Update highest boost here
        if boost > self.highestBoost:
            self.highestBoost = boost
        # end update highest boost
        return boost * (1000 - speed) * math.pow(self.field.level, 2) / 5

    def getDefeatMessage(self, speed, y):
        boost = "%.1f" % math.pow(1.45 + (self.field.level * 0.05), len(self.field.player.itemEffects))
        return _("Hit! (speed %(speed)d, burden %(burden)d, %(boost)sx boost)") % {
            "speed": 900 - speed, "burden": len(self.field.player.itemEffects), "boost": boost}

    def getShrinkMultiplier(self):
        return 0.75

    def getSlowDownMultiplier(self):
        return 1.5

    def frameUpdate(self):
        for elem in self.bonusCounters[:]:
            if not elem.active:
                self.bonusCounters.remove(elem)
                continue
            # end cleanup
            elem.frameUpdate()
        # end update bonus counters
        if self.itemShowerTimer.elapsed >= self.itemShowerTime:
            self.triggerItemShower()
        if self.itemComingTimer.elapsed >= self.itemComingTime:
            self.spawnItem()
            self.resetItemComingTimer()

    def setPaused(self, p):
        if p == self.paused:
            return
        self.paused = p
        self.itemComingTimer.setPaused(p)
        self.itemShowerTimer.setPaused(p)
    # end setPaused

    def triggerItemShower(self):
        self.spawnItem()
        self.itemShowerCount -= 1
        if self.itemShowerCount == 0:
            self.resetItemShower()
        else:
            self.itemShowerTime = 150
            self.itemShowerTimer.restart()

    def resetItemShower(self):
        self.itemShowerTime = random.randint(70000, 150000)
        self.itemShowerCount = random.randint(3, 6)

    def spawnItem(self):
        spd = random.randint(100, 800)
        t = itemConstants.TYPE_NASTY
        ident = self.selectNastyItem()
        i = item.Item()
        i.initialize(self.field, random.randint(0, self.field.x - 1), spd, t, ident)
        self.field.items.append(i)

    def selectNastyItem(self):
        """Prevents shrink from appearing when the player already has 3 shrink effects."""
        shrinks = len([e for e in self.field.player.itemEffects if e.name ==
                       itemConstants.NAMES[itemConstants.TYPE_NASTY][itemConstants.NASTY_SHRINK]])
        while(True):
            ret = random.randint(0, itemConstants.NASTY_MAX)
            if ret == itemConstants.NASTY_SHRINK and shrinks == 3:
                continue
            break
        return ret

    def resetItemComingTimer(self):
        self.itemComingTimer.restart()
        self.itemComingTime = random.randint(0, 60000)

    def onEnemyDefeated(self, x=None, y=None):
        effects = len(self.field.player.itemEffects)
        if effects > 0:
            bc = bonusCounter.BonusCounter()
            bc.initialize()
            bc.start(effects)
            self.bonusCounters.append(bc)
        # end append bonus counter

    def onItemObtained(self, it=None):
        self.spawnItem()

    def getModeSpecificResults(self):
        boost = "%.1f" % self.highestBoost
        return [
            _("Highest boost: %(boost)sx") % {"boost": boost}
        ]

    def getModeSpecificResultsForScoreboard(self):
        boost = "%.1f" % self.highestBoost
        return "%(boost)sx highest boost" % {"boost": boost}


class ChaosModeHandler(ArcadeModeHandler):
    """
    Chaos mode. Inherits the regular item spawns and item shower from arcade mode, but:
      - every defeated enemy drops an item (in addition to the regular spawns),
      - item type (good / nasty) is fully random and no longer correlated with falling speed,
      - the accuracy-based levelup bonus is disabled; instead the player is rewarded for
        obtaining ANY item and penalized for letting an item fall to the ground,
      - the level up curve and the per-enemy defeat score are the same slow ones as in normal / arcade.
    The destruction item behaves chaotically too (see gameField.performDestruction).
    """
    # Tunable scoring constants. Both scale with the square of the current level (base * level^2),
    # so item pickups / misses keep pace with the combat score instead of becoming negligible.
    ITEM_REWARD_BASE = 75
    MISS_PENALTY_BASE = 50
    # Hard cap on simultaneous items on the field. Each falling item holds a looped BASS channel,
    # so an unbounded Destruction shower (one drop per cleared enemy) at high levels would exhaust
    # the channel pool ("can't get a free channel"). Skip new items once this many are already live.
    MAX_ITEMS_ON_FIELD = 40
    # Bounding measures (this mode is unpublishable / for-fun only): cap HP and stored destruction
    # shields so the run can actually end at a sane level instead of growing forever (which also
    # prevented the BASS channel exhaustion that comes with hundreds of simultaneous enemies/items).
    MAX_LIVES = 5
    MAX_DESTRUCTION_SHIELDS = 3

    def __init__(self):
        super().__init__()
        # No accuracy-based bonuses in chaos mode; scoring is driven by item pickups / misses instead.
        # Disable both the level-up (accuracy) bonus and the consecutive-hits bonus (inherited as True from arcade).
        self.allowConsecutiveHitsBonus = False
        self.allowLevelupBonus = False
        self.name = ALL_MODES_STR[4]

    def _createItem(self, x=None):
        """Creates a single item with a fully random type (independent of speed), appends it to the field and returns it. Returns None if the field is already at the item cap."""
        if len(self.field.items) >= self.MAX_ITEMS_ON_FIELD:
            return None
        spd = random.randint(100, 800)
        t = itemConstants.TYPE_NASTY if random.randint(0, 1) == 0 else itemConstants.TYPE_GOOD
        ident = self.selectNastyItem() if t == itemConstants.TYPE_NASTY else random.randint(0, item.GOOD_MAX)
        if x is None:
            x = random.randint(0, self.field.x - 1)
        i = item.Item()
        i.initialize(self.field, x, spd, t, ident)
        self.field.items.append(i)
        return i

    def spawnItem(self, x=None):
        """Regular / shower spawn. Resets the coming timer like arcade mode does."""
        self._createItem(x)
        self.resetItemComingTimer()

    def dropItem(self, x):
        """Drops an item at the given column without disturbing the regular spawn cadence."""
        i = self._createItem(x)
        if i is None:  # field at item cap; skip the drop (and its log)
            return
        self.field.log(_("An enemy dropped a \"%(item)s\" item!") % {"item": itemConstants.NAMES[i.type][i.identifier]})

    def onEnemyDefeated(self, x=None, y=None):
        """Every defeated enemy drops an item where it was standing."""
        self.dropItem(x if x is not None else random.randint(0, self.field.x - 1))

    def onItemObtained(self, it=None):
        """Reward the player for obtaining any item, good or nasty alike."""
        self.field.player.addScore(self.ITEM_REWARD_BASE * self.field.level ** 2)

    def onItemMissed(self, it=None):
        """Penalize the player for letting an item fall to the ground."""
        self.field.player.addScore(-1 * self.MISS_PENALTY_BASE * self.field.level ** 2)

    def onItemPunchedAway(self, it=None):
        """Deliberately destroying an item (UP + punch) costs double the miss penalty."""
        self.field.player.addScore(-2 * self.MISS_PENALTY_BASE * self.field.level ** 2)

    def getMaxBlurredStacks(self):
        """Chaos: at most 2 simultaneously active Blurred effects."""
        return 2

    def getMinPunchDelay(self):
        """Chaos: boosts may not push the punch delay below 1 ms (prevents engine hang / crash)."""
        return 1

    def getMaxPunchDelay(self):
        """Chaos: slow downs may not push the punch delay above 800 ms."""
        return 800

    def getMaxLives(self):
        """Chaos: cap HP so the run can end at a sane level."""
        return self.MAX_LIVES

    def getMaxDestructionShields(self):
        """Chaos: cap stored destruction shields; overflow explodes on the hero instead of extending the run."""
        return self.MAX_DESTRUCTION_SHIELDS

    def getExtraLifeOverflowBonus(self):
        """Chaos: an Extra life obtained at the HP cap turns into bonus points (count no longer matters, score is just a number)."""
        return self.ITEM_REWARD_BASE * self.field.level ** 2

    def shouldObtainOnDestruction(self, it):
        """Chaos: flip a coin per item, obtain or destroy, regardless of good / nasty."""
        return random.randint(0, 1) == 0

    def onEnemyDefeatedByDestruction(self, x=None, y=None):
        """Chaos: enemies cleared by Destruction drop items too, creating a fresh item shower (bigger at higher levels)."""
        self.dropItem(x if x is not None else random.randint(0, self.field.x - 1))


class YoloModeHandler(ChaosModeHandler):
    """
    Yolo mode: a zero-player autoplay variant of Chaos. A bot drives the player by simulating
    movement (one column step per tick) and punches, WITHOUT cheating time: it respects the real
    punch delay (Boost / Slow down) and the real effective reach (Shrink / Megaton).

    Per-tick targeting:
      - Enemies are resolved first inside the player's column by the normal punchHit logic.
      - The Destruction item is pursued over other items, unless an enemy is already within reach.
      - Otherwise the bot chases the nearest object on the Y axis.
      - When aligned, good items (incl. Destruction) are obtained, nasty items are destroyed
        (UP + punch, accepting the penalty). The bot has perfect good/nasty knowledge.

    Inherits all Chaos behavior (drops, level^2 scoring, effect limits, HP / shield caps). For
    local for-fun use only.
    """

    # Tighter bounding measures than Chaos: the autoplay bot barely loses HP (it reached level 319
    # before exhausting the BASS channel pool), so cap HP / destruction shields lower to make the
    # zero-player run actually end at a sane level. Chaos and the other modes keep their own caps.
    MAX_LIVES = 3
    MAX_DESTRUCTION_SHIELDS = 1

    def __init__(self):
        super().__init__()
        self.name = ALL_MODES_STR[5]

    def frameUpdate(self):
        super().frameUpdate()  # regular Chaos / Arcade item spawning
        self._autoPlay()

    def _candidates(self):
        """Returns the list of live targets as (obj, x, y, kind) tuples; kind in enemy/destruction/good/nasty."""
        out = []
        for e in self.field.enemies:
            if e is not None and e.state == enemy.STATE_ALIVE:
                out.append((e, e.x, e.y, "enemy"))
        for it in self.field.items:
            if it.state != itemConstants.STATE_ALIVE:
                continue
            if it.type == itemConstants.TYPE_GOOD and it.identifier == itemConstants.GOOD_DESTRUCTION:
                kind = "destruction"
            elif it.type == itemConstants.TYPE_GOOD:
                kind = "good"
            else:
                kind = "nasty"
            out.append((it, it.x, it.y, kind))
        return out

    def _selectTarget(self, effRange):
        """Chooses which object (column) the bot should chase this tick."""
        cands = self._candidates()
        if not cands:
            return None
        px = self.field.player.x
        enemies = [c for c in cands if c[3] == "enemy"]
        destrs = [c for c in cands if c[3] == "destruction"]
        imminentEnemy = any(c[2] <= effRange for c in enemies)
        # The Destruction item is pursued over other items, unless an enemy is already within reach.
        if destrs and not imminentEnemy:
            return min(destrs, key=lambda c: (c[2], abs(c[1] - px)))
        # Otherwise chase the nearest object on Y (enemies win ties), then the closest column.
        return min(cands, key=lambda c: (c[2], 0 if c[3] == "enemy" else 1, abs(c[1] - px)))

    def _nearestInColumn(self, x, effRange):
        """Returns the nearest hittable target (obj, x, y, kind) in column x within reach, enemies winning ties, or None."""
        best = None
        for c in self._candidates():
            if c[1] != x or c[2] > effRange:
                continue
            if best is None or c[2] < best[2] or (c[2] == best[2] and c[3] == "enemy"):
                best = c
        return best

    def _autoPlay(self):
        """The zero-player bot. Drives the player like simulated key presses, respecting reach and timing."""
        player = self.field.player
        if player.punching:
            return  # let the current punch land first (respect punch timing)
        effRange = max(1, int(player.punchRange))
        target = self._selectTarget(effRange)
        if target is None:
            return
        tx = target[1]
        # Simulate moving one column toward the target (respects movement timing).
        if tx < player.x:
            if player.x > 0:
                player.moveTo(player.x - 1)
            return
        if tx > player.x:
            if player.x < self.field.x - 1:
                player.moveTo(player.x + 1)
            return
        # Aligned: only punch if something is actually in reach in this column (no time cheating).
        nearest = self._nearestInColumn(player.x, effRange)
        if nearest is None:
            return
        # Destroy nasty items (UP + punch), obtain everything else (enemies / good / destruction).
        player.autoDestroyNext = (nearest[3] == "nasty")
        player.punchLaunch()


def getModeHandler(mode):
    """Receives a mode in string and returns the associated modeHandler object without initializing it.

    :param mode: Mode.
    :type mode: str
    """
    if mode == ALL_MODES_STR[0]:
        return NormalModeHandler()
    if mode == ALL_MODES_STR[1]:
        return ArcadeModeHandler()
    if mode == ALL_MODES_STR[2]:
        return ClassicModeHandler()
    if mode == ALL_MODES_STR[3]:
        return BurdenModeHandler()
    if mode == ALL_MODES_STR[4]:
        return ChaosModeHandler()
    if mode == ALL_MODES_STR[5]:
        return YoloModeHandler()
    return None
