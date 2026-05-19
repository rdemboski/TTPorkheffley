import time
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task
from toontown.cogdominium.DistCogdoGameAI import DistCogdoGameAI
from toontown.cogdominium.CogdoGameConsts import getDifficulty, LaffPenalty
from toontown.cogdominium.CogdoMazeGameGlobals import (
    GameActions, SecondsUntilGameEnds, SecondsUntilTimeout, SecondsForTimeAlert,
    FinishDurationSeconds, NumSuits, SuitsModifier, SuitData, MaxLaffBonus, MinLaffBonus)


class DistCogdoMazeGameAI(DistCogdoGameAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoMazeGameAI")

    def __init__(self, air, interiorId, exteriorZone, toonIds, interior):
        DistCogdoGameAI.__init__(self, air, interiorId, exteriorZone, toonIds)
        self._interior = interior
        # Scale minion counts by neighbourhood difficulty.
        # SuitsModifier has one entry per tier; boss count is always NumSuits[0].
        difficulty = getDifficulty(exteriorZone)
        tier = min(int(difficulty * len(SuitsModifier)), len(SuitsModifier) - 1)
        modifier = SuitsModifier[tier]
        self._numSuits = [NumSuits[0],
                          NumSuits[1] + modifier,
                          NumSuits[2] + modifier]
        self.notify.debug('__init__: difficulty=%.2f tier=%d numSuits=%s' % (
            difficulty, tier, self._numSuits))
        # Laff penalty applied to toons who don't reach the exit in time.
        # Scales 0 (easiest neighbourhood) → LaffPenalty (hardest).
        self._laffPenalty = round(difficulty * LaffPenalty)
        self._gameFinished = False
        self._doorOpened = False
        self._doorOpenedAt = None        # wall-clock time when the exit door opened
        self._toonsEnteredDoor = set()  # avIds that have walked through the exit
        self._runFailed = False          # set True when a toon goes sad mid-game
        self._allToonsExited = False     # set True only when every toon escaped

    # --- Required broadcast getter ---

    def setNumSuits(self, numSuits):
        self._numSuits = list(numSuits)

    def getNumSuits(self):
        return self._numSuits

    # --- Game startup sequence ---

    def startGame(self):
        """Called by the interior AI once the game DO is generated.
        Sends Visible then queues the Intro start."""
        self._gameFinished = False
        self.d_setVisible()
        taskMgr.doMethodLater(
            0.5, self._doIntroStart, self.uniqueName('introStart'))

    def _doIntroStart(self, task):
        self.d_setIntroStart()
        return Task.done

    # --- DistCogdoGameAI hook: send Countdown and start the full-length timer ---

    def _onGameStarted(self):
        # Show the countdown clock on every client.
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('doAction', [GameActions.Countdown, 0, timestamp])
        # Send a TimeAlert (music switch) when SecondsForTimeAlert remain.
        timeAlertDelay = SecondsUntilTimeout - SecondsForTimeAlert
        if timeAlertDelay > 0:
            taskMgr.doMethodLater(
                timeAlertDelay,
                self._sendTimeAlert,
                self.uniqueName('timeAlert'))
        # Main game timer — runs the full timeout duration.
        taskMgr.doMethodLater(
            SecondsUntilTimeout,
            self._onGameTimerExpired,
            self.uniqueName('gameTimer'))

    def _sendTimeAlert(self, task):
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('doAction', [GameActions.TimeAlert, 0, timestamp])
        return Task.done

    def _onGameTimerExpired(self, task):
        self._endGame()
        return Task.done

    def _endGame(self):
        """Finish the game and schedule the interior callback."""
        if self._gameFinished:
            return
        self._gameFinished = True
        # Penalise any toons who did not reach the exit elevator in time.
        # Must happen before clearing _toonsEnteredDoor so we know who escaped.
        if self._laffPenalty > 0:
            for avId in self._toonIds:
                if avId not in self._toonsEnteredDoor:
                    self._applyLaffPenalty(avId)
        self._toonsEnteredDoor.clear()
        taskMgr.remove(self.uniqueName('gameTimer'))
        taskMgr.remove(self.uniqueName('timeAlert'))
        self.d_setGameFinish()
        taskMgr.doMethodLater(
            FinishDurationSeconds,
            self._notifyInteriorDone,
            self.uniqueName('mazeFinish'))

    def _failRun(self):
        """A toon went sad — end the game and mark the run as failed so
        the interior transitions to Failed (building resets) instead of
        continuing to the next floor."""
        if self._runFailed or self._gameFinished:
            return
        self._runFailed = True
        self._endGame()

    def _notifyInteriorDone(self, task):
        if self._interior:
            if self._runFailed or not self._allToonsExited:
                # Toon went sad mid-game OR the exit timer expired before all
                # toons escaped (the "you didn't make it" sad animation path).
                # Either way, fail the field office and reset the building.
                self._interior._transitionToFailed(None)
            else:
                # Every toon walked through the exit door — advance to the
                # next floor as normal.
                self._interior.mazeGameDone()
        return Task.done

    # --- Relay: action ---

    def requestAction(self, action, data):
        avId = self.air.getAvatarIdFromSender()
        timestamp = globalClockDelta.getRealNetworkTime()
        # EnterDoor: the client sends data=0; replace it with the real toonId
        # so every client's toonEntersDoor(toonId) can look up the correct player.
        if action == GameActions.EnterDoor:
            data = avId
        self.sendUpdate('doAction', [action, data, timestamp])
        if action == GameActions.OpenDoor:
            self._endGame()
        elif action == GameActions.RevealDoor:
            # First toon to find the exit opens the door for everyone.
            self._openDoor()
        elif action == GameActions.EnterDoor:
            # Track which toons have walked through the open door.
            # Award laff based on how quickly they reached the exit elevator.
            # End the game early only when ALL toons are safely through —
            # otherwise let the 60-second exit timer run so remaining toons
            # have a chance to reach the exit (avoids the premature Sad
            # animation on toons that just haven't reached the door yet).
            self._toonsEnteredDoor.add(avId)
            self._awardMazeLaff(avId)
            if len(self._toonsEnteredDoor) >= len(self._toonIds):
                # Everyone escaped — mark as a clean win before ending.
                self._allToonsExited = True
                self._endGame()

    def _applyLaffPenalty(self, avId):
        """Deduct laff from a toon who didn't reach the exit elevator in time.
        Penalty scales 0 (TTC) → LaffPenalty (Dreamland) based on neighbourhood
        difficulty, and never sends HP below 1 (no forced-sad from the penalty)."""
        toon = self.air.doId2do.get(avId)
        if toon is None:
            return
        newHp = max(1, toon.hp - self._laffPenalty)
        toon.b_setHp(newHp)
        self.notify.debug('_applyLaffPenalty: toon %d -%d laff (%d/%d)' % (
            avId, self._laffPenalty, newHp, toon.maxHp))

    def _awardMazeLaff(self, avId):
        """Award laff to a toon based on how quickly they entered the exit elevator.
        Scales linearly between MinLaffBonus (no time left) and MaxLaffBonus
        (full SecondsUntilGameEnds remaining), then clamps to the toon's max HP."""
        toon = self.air.doId2do.get(avId)
        if toon is None:
            return
        if self._doorOpenedAt is not None:
            elapsed = time.time() - self._doorOpenedAt
            timeRemaining = max(0.0, SecondsUntilGameEnds - elapsed)
            ratio = timeRemaining / SecondsUntilGameEnds
            bonus = max(MinLaffBonus, round(ratio * MaxLaffBonus))
        else:
            # Door was never formally opened (shouldn't happen under normal flow)
            bonus = MinLaffBonus
        newHp = min(toon.maxHp, toon.hp + bonus)
        toon.b_setHp(newHp)
        self.notify.debug('_awardMazeLaff: toon %d +%d laff (%d/%d)' % (
            avId, bonus, newHp, toon.maxHp))

    def _openDoor(self):
        """Broadcast OpenDoor to all clients and switch to the exit timer."""
        if self._doorOpened or self._gameFinished:
            return
        self._doorOpened = True
        self._doorOpenedAt = time.time()
        # Cancel the long main timer and time-alert task.
        taskMgr.remove(self.uniqueName('gameTimer'))
        taskMgr.remove(self.uniqueName('timeAlert'))
        # Tell all clients the door is now open.
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('doAction', [GameActions.OpenDoor, 0, timestamp])
        # Give toons SecondsUntilGameEnds to actually enter the door.
        taskMgr.doMethodLater(
            SecondsUntilGameEnds,
            self._onGameTimerExpired,
            self.uniqueName('gameTimer'))

    def doAction(self, action, data, networkTime):
        pass

    # --- Relay: gag throw ---

    def requestUseGag(self, x, y, h, networkTime):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdate('toonUsedGag', [avId, x, y, h, networkTime])

    def toonUsedGag(self, toonId, x, y, h, networkTime):
        pass

    # --- Relay: suit hit by gag ---

    def requestSuitHitByGag(self, suitType, suitNum):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdate('suitHitByGag', [avId, suitType, suitNum])

    def suitHitByGag(self, toonId, suitType, suitNum):
        pass

    # --- Relay: toon hit by suit ---

    def requestHitBySuit(self, suitType, suitNum, networkTime):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdate('toonHitBySuit', [avId, suitType, suitNum, networkTime])
        # Apply damage server-side so the HP reduction is authoritative.
        toon = self.air.doId2do.get(avId)
        if toon is not None:
            damage = int(SuitData[suitType]['toonDamage'])
            newHp = max(0, toon.hp - damage)
            toon.b_setHp(newHp)
            if newHp <= 0:
                # Toon has gone sad.  Notify all clients so each runs
                # handleToonWentSad (which exits the local toon to the street),
                # then fail the entire field-office run.
                self.sendUpdate('setToonSad', [avId])
                self._failRun()

    def toonHitBySuit(self, toonId, suitType, suitNum, networkTime):
        pass

    # --- Relay: toon hit by drop ---

    def requestHitByDrop(self):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdate('toonHitByDrop', [avId])

    def toonHitByDrop(self, toonId):
        pass

    # --- Relay: memo pickup ---

    def requestPickUp(self, pickupNum):
        avId = self.air.getAvatarIdFromSender()
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('pickUp', [avId, pickupNum, timestamp])

    def pickUp(self, toonId, pickupNum, networkTime):
        pass

    # --- Relay: water cooler gag refill ---

    def requestGag(self, waterCoolerIndex):
        avId = self.air.getAvatarIdFromSender()
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('hasGag', [avId, timestamp])

    def hasGag(self, toonId, networkTime):
        pass

    # --- Cleanup ---

    def delete(self):
        taskMgr.remove(self.uniqueName('introStart'))
        taskMgr.remove(self.uniqueName('gameTimer'))
        taskMgr.remove(self.uniqueName('timeAlert'))
        taskMgr.remove(self.uniqueName('mazeFinish'))
        self._interior = None
        DistCogdoGameAI.delete(self)
