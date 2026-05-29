# -*- coding: utf-8 -*-
# Screaming Strike player handler class
# Copyright (C) 2019 Yukio Nozawa <personal@nyanchangames.com>
# License: GPL V2.0 (See copying.txt for details)
import bgtsound
import random
import bonusCounter
import enemy
import globalVars
import itemConstants
import itemEffects
import window

DEFAULT_PUNCH_RANGE = 4
DEFAULT_PUNCH_SPEED = 200


class Player():
    """This class represents a player."""

    def initialize(self, field):
        """Initializes this player.

        :param field: The field instance on which this player should be bound.
        :type field: gameField.GameField
        """
        self.paused = False
        self.field = field
        self.lives = 3
        self.x = field.getCenterPosition()
        self.punchTimer = window.Timer()
        self.punching = False
        self.punchSpeed = DEFAULT_PUNCH_SPEED
        self.punchRange = DEFAULT_PUNCH_RANGE
        self.score = 0
        self.score_validator = []
        self.punches = 0
        self.hits = 0
        self.hitPercentage = 0
        self.consecutiveHitBonus = bonusCounter.BonusCounter()
        self.consecutiveHitBonus.initialize()
        self.consecutiveMissUnbonus = bonusCounter.BonusCounter()
        self.consecutiveMissUnbonus.initialize()
        self.consecutiveHits = 0
        self.consecutiveMisses = 0
        self.itemEffects = []
        self.penetrate = False
        self.autoDestructionRemaining = 0
        # Set by the Yolo autoplay bot to make the next punch destroy an item (UP + punch) instead of obtaining it.
        self.autoDestroyNext = False
        self.lastHighscore = globalVars.appMain.statsStorage.get("hs_" + self.field.modeHandler.getName())
        self.gotHighscore = False

    def frameUpdate(self):
        """Call this method once per frame to keep everything updated."""
        self.consecutiveHitBonus.frameUpdate()
        self.consecutiveMissUnbonus.frameUpdate()
        if self.punching is False and globalVars.appMain.keyPressed(window.K_SPACE):
            self.punchLaunch()
        if self.punching is True and self.punchTimer.elapsed >= self.punchSpeed:
            self.punchHit()
        if self.x != 0 and globalVars.appMain.keyPressed(window.K_LEFT):
            self.moveTo(self.x - 1)
        if self.x != self.field.getX() - 1 and globalVars.appMain.keyPressed(window.K_RIGHT):
            self.moveTo(self.x + 1)
        for elem in self.itemEffects[:]:
            if not elem.frameUpdate(self.field.modeHandler):
                self.itemEffects.remove(elem)

    def punchLaunch(self):
        """Launches a punch. If this player is already punching, this method does nothing. """
        if self.punching:
            return
        self.punches += 1
        self.punching = True
        s = bgtsound.sound()
        s.load(globalVars.appMain.sounds["fists.ogg"])
        s.pan = self.field.getPan(self.x)
        s.pitch = int(DEFAULT_PUNCH_SPEED / self.punchSpeed * 100) + random.randint(-10, 10)
        s.play()
        self.punchTimer.restart()

    def punchHit(self):
        """Process punch hits. Called from frameUpdate as it is needed."""
        self.punching = False
        hit = 0
        # Effective reach is floored at 1: overlapping Megaton (x5 / /5) and Shrink (x0.5 floor)
        # effects can drift punchRange to a fractional or sub-1 value, which would otherwise leave
        # the fist only able to reach position 0 (practically useless). Keep at least reach 1.
        effectiveRange = max(1, int(self.punchRange))
        for pos in range(effectiveRange + 1):
            for elem in self.field.enemies:
                if elem is not None and elem.state == enemy.STATE_ALIVE and self.x == elem.x and elem.y == pos:
                    elem.hit()
                    self.field.modeHandler.onEnemyDefeated(elem.x, elem.y)
                    hit += 1
                    self.hits += 1
                    self.consecutiveHits += 1
                    self.processConsecutiveMisses()
                    self.calcHitPercentage()  # penetration would higher the percentage, but I don't care
                    self.field.logDefeat()
                    if not self.penetrate:
                        break
                # end if
            # end for enemies
            if not self.penetrate and hit > 0:
                break
            for elem in self.field.items:
                if elem.state == itemConstants.STATE_ALIVE and self.x == elem.x and elem.y == pos:
                    if globalVars.appMain.keyPressing(window.K_UP) or self.autoDestroyNext:
                        elem.punch()
                    else:
                        elem.obtain()
                        self.field.modeHandler.onItemObtained(elem)
                        self.processItemHit(elem)
                    # end item hit
                    hit = True
                    self.hits += 1
                    self.consecutiveHits += 1
                    self.processConsecutiveMisses()
                    self.calcHitPercentage()
                    if not self.penetrate:
                        break
                # end if
            # end for items
        # end for range
        self.autoDestroyNext = False  # one-shot: consumed by this punch
        if not hit:
            self.punchMiss()
    # end punchHit

    def punchMiss(self):
        """Processes punch miss. Called from punchHit."""
        self.consecutiveMisses += 1
        if self.hits > 0:
            self.calcHitPercentage()
        self.processConsecutiveHits()

    def processConsecutiveHits(self):
        """Processes consecutive hits bonus. Called from punchHit."""
        if not self.field.modeHandler.allowConsecutiveHitsBonus:
            return
        if self.consecutiveHits > 5:
            self.field.log(_("%(hits)d consecutive hits bonus!") % {"hits": self.consecutiveHits})
            self.addScore(self.consecutiveHits * self.consecutiveHits * self.field.level * self.field.level)
            self.consecutiveHitBonus.start(self.consecutiveHits)
        # end if
        self.consecutiveHits = 0

    def processConsecutiveMisses(self):
        """Processes consecutive misses penalty. Called from punchHit."""
        if not self.field.modeHandler.allowConsecutiveMissesBonus:
            return
        if self.consecutiveMisses > 5:
            self.field.log(_("%(misses)d consecutive misses penalty!") % {"misses": self.consecutiveMisses})
            self.addScore(self.consecutiveMisses * self.consecutiveMisses * self.field.level * self.field.level * -1)
            self.consecutiveMissUnbonus.start(self.consecutiveMisses * -1)
        # end if
        self.consecutiveMisses = 0

    def processItemHit(self, it):
        """
        Processes hitting an item. Called from punchHit. This method just checks the item is good or nasty, then calls the specific methods.

        :param it: Item instance which got hit.
        :type it: item.Item
        """
        if it.type == itemConstants.TYPE_NASTY:
            self.processNastyItemHit(it)
        else:
            self.processGoodItemHit(it)

    def processNastyItemHit(self, it):
        """
        Processes a nasty item hit. Called from processItemHit.

        :param it: Item instance which got hit.
        :type it: item.Item
        """
        if it.identifier == itemConstants.NASTY_SHRINK:
            # When player's punching range cannot be decreased further, find an existing shrink effect and extend the effect expiration.
            self.processShrinkItemEffect()
            return
        if it.identifier == itemConstants.NASTY_BLURRED:
            self.processBlurredItemEffect()
            return
        if it.identifier == itemConstants.NASTY_SLOWDOWN:
            self.processSlowDownItemEffect()
            return

    def processShrinkItemEffect(self):
        """
                Processes an edge case where player's punching range is 1 and cannot be decreased further.
                In this case, find an existing shrink effect, which will be expired next.
                Extend the found shrink effect's expiration.
                Otherwise, normally process the shrink effect.
        """
        if self.punchRange == 1:
            shrinks = [e for e in self.itemEffects if e.name == itemConstants.NAMES[itemConstants.TYPE_NASTY]
                       [itemConstants.NASTY_SHRINK]]  # length should never be 0
            shrinks.sort(key=lambda e: e.calculateTimeRemaining())
            shrinks[0].extend(itemConstants.BASE_EFFECT_TIME)
            return
        # normal
        e = itemEffects.ShrinkEffect()
        e.initialize(self)
        e.activate(self.field.modeHandler)
        self.itemEffects.append(e)

    def processBlurredItemEffect(self):
        """
                Adds a blurred effect, respecting the mode's stack cap.
                If the mode limits active blurred stacks and we are already at the cap,
                extend the soonest-expiring blurred effect instead of stacking another.
        """
        maxStacks = self.field.modeHandler.getMaxBlurredStacks()
        blurreds = [e for e in self.itemEffects if e.name == itemConstants.NAMES[itemConstants.TYPE_NASTY][itemConstants.NASTY_BLURRED]]
        if maxStacks is not None and len(blurreds) >= maxStacks:
            blurreds.sort(key=lambda e: e.calculateTimeRemaining())
            blurreds[0].extend(itemConstants.BASE_EFFECT_TIME)
            return
        e = itemEffects.BlurredEffect()
        e.initialize(self)
        e.activate(self.field.modeHandler)
        self.itemEffects.append(e)

    def processSlowDownItemEffect(self):
        """
                Adds a slow down effect, respecting the mode's punch-delay cap.
                If applying it would push the punch delay above the mode's maximum,
                extend an existing slow down instead of stacking another.
        """
        maxDelay = self.field.modeHandler.getMaxPunchDelay()
        mult = self.field.modeHandler.getSlowDownMultiplier()
        if maxDelay is not None and self.punchSpeed * mult > maxDelay:
            existing = self.findEffect("Slow down")
            if existing is not None:
                existing.extend(itemConstants.BASE_EFFECT_TIME)
            return
        e = itemEffects.SlowDownEffect()
        e.initialize(self)
        e.activate(self.field.modeHandler)
        self.itemEffects.append(e)

    def processBoostItemEffect(self):
        """
                Adds a boost effect, respecting the mode's punch-delay floor.
                If halving the punch delay would drop it below the mode's minimum,
                extend an existing boost instead of stacking another.
        """
        minDelay = self.field.modeHandler.getMinPunchDelay()
        if minDelay is not None and self.punchSpeed / 2 < minDelay:
            existing = self.findEffect("Boost")
            if existing is not None:
                existing.extend(itemConstants.BASE_EFFECT_TIME)
            return
        e = itemEffects.BoostEffect()
        e.initialize(self)
        e.activate(self.field.modeHandler)
        self.itemEffects.append(e)

    def processGoodItemHit(self, it):
        """
        Processes a good item hit. Called from processItemHit.

        :param it: Item instance which got hit.
        :type it: item.Item
        """
        if it.identifier == itemConstants.GOOD_MEGATONPUNCH:
            existing = self.findEffect("Megaton punch")
            if existing is None:
                e = itemEffects.MegatonPunchEffect()
                e.initialize(self)
                e.activate(self.field.modeHandler)
                self.itemEffects.append(e)
            else:
                existing.extend(itemConstants.BASE_EFFECT_TIME)
            return
        if it.identifier == itemConstants.GOOD_BOOST:
            self.processBoostItemEffect()
            return
        if it.identifier == itemConstants.GOOD_PENETRATION:
            existing = self.findEffect("Penetration")
            if existing is None:
                e = itemEffects.PenetrationEffect()
                e.initialize(self)
                e.activate(self.field.modeHandler)
                self.itemEffects.append(e)
            else:
                existing.extend(itemConstants.BASE_EFFECT_TIME)
            return
        if it.identifier == itemConstants.GOOD_DESTRUCTION:
            ok = self.field.startDestruction()
            if not ok:  # Already destructing
                maxShields = self.field.modeHandler.getMaxDestructionShields()
                if maxShields is not None and self.autoDestructionRemaining >= maxShields:
                    self.explodeOnSelf()
                    return
                self.autoDestructionRemaining += 1
                self.field.log(_("This effect will be used when it's necessary! (Remaining %(r)d)") % {"r": self.autoDestructionRemaining})
                return
        if it.identifier == itemConstants.GOOD_EXTRALIFE:
            maxLives = self.field.modeHandler.getMaxLives()
            if maxLives is not None and self.lives >= maxLives:
                bonus = self.field.modeHandler.getExtraLifeOverflowBonus()
                if bonus:
                    self.addScore(bonus)
                self.field.log(_("Extra life at maximum HP! Converted to bonus points."))
                s = bgtsound.sound()
                s.load(globalVars.appMain.sounds["extraLife.ogg"])
                s.pitch = 60 + (self.lives * 10)
                s.play()
                return
            self.lives += 1
            self.field.log(_("Extra life! (now %(lives)d lives)") % {"lives": self.lives})
            s = bgtsound.sound()
            s.load(globalVars.appMain.sounds["extraLife.ogg"])
            s.pitch = 60 + (self.lives * 10)
            s.play()
            return

    def findEffect(self, name):
        """
        Checks whether this player has the specified effect currently active.

        :param name: Name of the effect to search(Blurred, Megaton Punch, etc).
        :type name: str

        :rtype: bool
        """
        for elem in self.itemEffects:
            if elem.name == name:
                return elem
        return None

    def setPunchRange(self, r):
        """
        Changes this player's effective punch length.

        :param r: New range.
        :type r: int
        """
        previous = self.punchRange
        self.field.log(_("The effective range of your Punch is now %(range)d (from %(from)d)") % {"range": r, "from": previous})
        self.punchRange = r

    def setPunchSpeed(self, s):
        """
        Changes this player's punching speed.

        :param s: New speed in milliseconds.
        :type s: int
        """
        # Safety net for the mode's punch-delay bounds: even with the application-side guards,
        # interleaved effect expirations can drift the delay out of range. Clamp it here so the
        # delay never crashes the engine (too small) or freezes gameplay (too large).
        minDelay = self.field.modeHandler.getMinPunchDelay()
        if minDelay is not None and s < minDelay:
            s = minDelay
        maxDelay = self.field.modeHandler.getMaxPunchDelay()
        if maxDelay is not None and s > maxDelay:
            s = maxDelay
        previous = self.punchSpeed
        self.field.log(_("The speed of your punch is now %(speed)d milliseconds (from %(from)d)") % {"speed": s, "from": previous})
        self.punchSpeed = s

    def setPenetration(self, p):
        """
        Sets whether this player's punches penetrate.

        :param p: Penetrate?
        :type p: bool
        """
        if p is True:
            self.field.log(_("Your punches now penetrate enemies and items!"))
        else:
            self.field.log(_("Your punches no longer penetrate enemies and items!"))
        self.penetrate = p

    def calcHitPercentage(self):
        """Calculates the hitting percentage of this player and updates the hitPercentage property."""
        self.hitPercentage = self.hits / self.punches * 100

    def moveTo(self, p):
        """
        Moves this player to the specified position.

        :param p: New position.
        :type p: int
        """
        self.x = p
        s = bgtsound.sound()
        s.load(globalVars.appMain.sounds["change.ogg"])
        s.pan = self.field.getPan(self.x)
        s.play()

    def hit(self):
        """Called when this player gets hit by one of the enemies. Returns true when the attack succeeds, or False if player attacks back with auto destruction."""
        if self.autoDestructionRemaining > 0:
            self.autoDestructionRemaining -= 1
            self.field.log(_("You're about to be attacked, but you have a counter!"))
            self.field.startDestruction()

            return False
        # end auto destruction
        self.lives -= 1
        self.field.log(_("You've been slapped! (%(lives)d HP remaining)") % {"lives": self.lives})
        s = bgtsound.sound()
        if self.lives > 0:
            s.load(globalVars.appMain.sounds["attacked.ogg"])
            s.play()
        else:
            self.field.log(_("Game over!"))
            s.load(globalVars.appMain.sounds["gameover.ogg"])
            s.volume = -10
            s.play()
            return False

    def explodeOnSelf(self):
        """Called when the player tries to store a destruction shield beyond the mode's cap: it detonates on the hero, costing a life (bounds the run instead of extending it forever)."""
        self.lives -= 1
        self.field.log(_("Too many stored destructions! It explodes on you! (%(lives)d HP remaining)") % {"lives": self.lives})
        bgtsound.playOneShot(globalVars.appMain.sounds["destruct.ogg"])
        if self.lives <= 0:
            self.field.log(_("Game over!"))
            s = bgtsound.sound()
            s.load(globalVars.appMain.sounds["gameover.ogg"])
            s.volume = -10
            s.play()

    def addScore(self, score):
        """
        Add a specified amount of score to this player. Also checks for high score.

        :param score: Score to add.
        :type score: int
        """
        self.score += score
        self.score_validator.append(score)
        if self.gotHighscore is False and self.score >= self.lastHighscore:
            self.processHighscore()
        which = _("added")
        if score <= 0:
            which = _("subtracted")
        self.field.log(_("Point: %(added).1f %(changestr)s (%(total).1f)") % {"added": score, "changestr": which, "total": self.score})
    # end addScore

    def processHighscore(self):
        """Plays the highscore sound and logs that this player has achieved high score."""
        bgtsound.playOneShot(globalVars.appMain.sounds["highscore.ogg"])
        self.gotHighscore = True
    # end processHighscore

    def getNewHighscore(self):
        """Returns the new high score if this player got one, otherwise None."""
        return None if self.gotHighscore is False else int(self.score)
    # end getNewHighscore

    def getPreviousHighscore(self):
        """Retrieves the previous high score. If this player has achieved a new high score, the previous one is returned. Otherwise, the currently standing highscore is returned.

        :rtype: int
        """
        return self.lastHighscore
    # end getPreviousHighscore

    def setPaused(self, p):
        """Pauses this player."""
        if p == self.paused:
            return
        self.paused = p
        for elem in self.itemEffects:
            elem.setPaused(p)
        # end item effects
        self.punchTimer.setPaused(p)
    # end pause


# end class Player
