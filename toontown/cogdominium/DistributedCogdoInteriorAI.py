import random
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task


# How long after setGameFinish the intro movie is expected to last before
# we nudge the interior into Battle state.
_BATTLE_INTRO_DURATION = 12.0

# How long to wait in Reward before force-deleting the interior DO.
# The client plays the penthouse outro + player-driven chat during this window.
_REWARD_CLEANUP_DELAY = 90.0

# Seconds between mazeGameDone() and the automatic second elevator ride
# to the penthouse.  Gives toons a moment to stand by the exit elevator.
_RESTING_DURATION = 3.0

# How long after the final exit state to keep the interior DO alive so every
# client has time to fully process the transition.
_FAIL_CLEANUP_DELAY = 15.0

# Server-side fallback: if not all toons call elevatorDone within this many
# seconds, advance anyway (handles disconnects mid-ride).
_ELEVATOR_TIMEOUT = 30.0


class DistributedCogdoInteriorAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedCogdoInteriorAI")

    def __init__(self, air, elevator=None):
        DistributedObjectAI.__init__(self, air)
        self.elevator = elevator

        # --- required broadcast ram fields ---
        self._zoneId = 0
        self._extZoneId = 0
        self._distBldgDoId = 0
        self._numFloors = 0
        self._shopOwnerNpcId = 0
        self._state = ('Off', 0)

        # --- non-required ram fields ---
        self._sosNpcId = 0
        self._foType = 0
        self._toons = ([], 0)
        self._suits = ([], [], [])

        # --- internal tracking ---
        self._joinedToons = set()
        self._expectedToonCount = 0
        self._currentFloor = -1      # incremented once per floor, after all toons respond
        self._elevatorResponses = set()  # toons that called elevatorDone this ride
        self._mazeGame = None        # DistCogdoMazeGameAI instance while active
        self._bldg = None            # saved building reference for cleanup

        # --- penthouse battle ---
        self._penthouseSuits = []
        self._penthouseActiveSuits = []
        self._battle = None

    # -----------------------------------------------------------------------
    # State broadcast
    # -----------------------------------------------------------------------

    def d_setState(self, state):
        timestamp = globalClockDelta.getRealNetworkTime()
        self.setState(state, timestamp)
        self.sendUpdate('setState', [state, timestamp])

    # -----------------------------------------------------------------------
    # Required broadcast ram fields
    # -----------------------------------------------------------------------

    def setZoneId(self, zoneId):
        self._zoneId = zoneId

    def getZoneId(self):
        return self._zoneId

    def setExtZoneId(self, extZoneId):
        self._extZoneId = extZoneId

    def getExtZoneId(self):
        return self._extZoneId

    def setDistBldgDoId(self, distBldgDoId):
        self._distBldgDoId = distBldgDoId

    def getDistBldgDoId(self):
        return self._distBldgDoId

    def setNumFloors(self, numFloors):
        self._numFloors = numFloors

    def getNumFloors(self):
        return self._numFloors

    def setShopOwnerNpcId(self, npcId):
        self._shopOwnerNpcId = npcId

    def getShopOwnerNpcId(self):
        return self._shopOwnerNpcId

    def setState(self, state, timestamp):
        self._state = (state, timestamp)

    def getState(self):
        return self._state

    # -----------------------------------------------------------------------
    # Non-required ram fields
    # -----------------------------------------------------------------------

    def setSOSNpcId(self, npcId):
        self._sosNpcId = npcId

    def getSOSNpcId(self):
        return self._sosNpcId

    def setFOType(self, typeId):
        self._foType = typeId

    def getFOType(self):
        return self._foType

    def setToons(self, toonIds, hack):
        self._toons = (toonIds, hack)

    def getToons(self):
        return self._toons

    def setSuits(self, suitIds, reserveIds, values):
        self._suits = (suitIds, reserveIds, values)

    def getSuits(self):
        return self._suits

    # -----------------------------------------------------------------------
    # Toon join handling
    # -----------------------------------------------------------------------

    def setAvatarJoined(self):
        avId = self.air.getAvatarIdFromSender()
        self._joinedToons.add(avId)
        taskMgr.remove(self.uniqueName('elevatorTransition'))
        if self._expectedToonCount > 0 and len(self._joinedToons) >= self._expectedToonCount:
            self._transitionToElevator(None)
        else:
            # Wait a short time for any remaining toons to join.
            taskMgr.doMethodLater(
                3.0, self._transitionToElevator,
                self.uniqueName('elevatorTransition'))

    def _transitionToElevator(self, task):
        taskMgr.remove(self.uniqueName('elevatorTransition'))
        self.d_setState('Elevator')
        return Task.done

    # -----------------------------------------------------------------------
    # Floor progression — guarded against multiple clients
    # -----------------------------------------------------------------------

    def elevatorDone(self):
        """Called by each client after its elevator ride animation finishes.
        We wait for ALL joined toons before advancing the floor so that two
        simultaneous calls from two clients don't increment _currentFloor twice.
        """
        avId = self.air.getAvatarIdFromSender()
        if avId not in self._joinedToons:
            self.notify.warning('elevatorDone from unknown toon %d; ignoring' % avId)
            return
        # Deduplicate: ignore if this toon already responded for this ride.
        if avId in self._elevatorResponses:
            return
        self._elevatorResponses.add(avId)
        self.notify.debug('elevatorDone: %d/%d responses' % (
            len(self._elevatorResponses), len(self._joinedToons)))
        # Start/reset a server-side timeout so we advance even if a client
        # disconnects mid-ride and never sends its elevatorDone.
        taskMgr.remove(self.uniqueName('elevatorTimeout'))
        taskMgr.doMethodLater(
            _ELEVATOR_TIMEOUT, self._onElevatorTimeout,
            self.uniqueName('elevatorTimeout'))
        # Only advance once every expected toon has responded.
        if len(self._elevatorResponses) < len(self._joinedToons):
            return
        self._advanceFloor()

    def _onElevatorTimeout(self, task):
        """Server-side fallback: not all toons responded in time."""
        self.notify.warning(
            '_onElevatorTimeout: advancing floor with %d/%d responses' % (
                len(self._elevatorResponses), len(self._joinedToons)))
        self._advanceFloor()
        return Task.done

    def _advanceFloor(self):
        """Actually increment the floor counter and transition the interior."""
        taskMgr.remove(self.uniqueName('elevatorTimeout'))
        self._elevatorResponses.clear()
        self._currentFloor += 1
        self.notify.debug('_advanceFloor: currentFloor=%d numFloors=%d' % (
            self._currentFloor, self._numFloors))
        taskMgr.remove(self.uniqueName('elevatorTransition'))

        if self._currentFloor < self._numFloors:
            # Still on a maze game floor (floor 0, 1, ... numFloors-1).
            self.d_setState('Game')
            self._createMazeGame()
        else:
            # Boss floor (floor == numFloors, i.e. the penthouse).
            # Generate the suits now so they exist when the battle starts.
            # We do NOT broadcast setSuits to DistributedCogdoInterior clients
            # because that would trigger a spurious ReservesJoining animation;
            # DistributedBattleBldg handles suit positioning via FaceOff.
            self._generatePenthouseSuits()
            self.d_setState('BattleIntro')
            taskMgr.doMethodLater(
                _BATTLE_INTRO_DURATION,
                self._transitionToBattle,
                self.uniqueName('battleIntroDelay'))

    # -----------------------------------------------------------------------
    # Maze game lifecycle
    # -----------------------------------------------------------------------

    def _createMazeGame(self):
        """Instantiate DistCogdoMazeGameAI and kick off the game flow."""
        from toontown.cogdominium.DistCogdoMazeGameAI import DistCogdoMazeGameAI
        toonIds = list(self._joinedToons) if self._joinedToons else list(self._toons[0])
        self._mazeGame = DistCogdoMazeGameAI(
            self.air, self.doId, self._extZoneId, toonIds, self)
        self._mazeGame.generateWithRequired(self._zoneId)
        self._mazeGame.startGame()
        self.notify.debug('_createMazeGame: generated DO %d' % self._mazeGame.doId)

    def mazeGameDone(self):
        """Called by DistCogdoMazeGameAI when the game timer expires (or door opens)."""
        self.notify.debug('mazeGameDone')
        if self._mazeGame:
            self._mazeGame.requestDelete()
            self._mazeGame = None
        # Show the exit elevator so toons can walk up to it.
        self.d_setState('Resting')
        # After a brief pause, automatically send the elevator to the penthouse.
        taskMgr.doMethodLater(
            _RESTING_DURATION,
            self._sendElevatorToPenthouse,
            self.uniqueName('elevatorToPenthouse'))

    def _sendElevatorToPenthouse(self, task):
        """Trigger the second elevator ride to the boss floor."""
        self.d_setState('Elevator')
        return Task.done

    # -----------------------------------------------------------------------
    # Penthouse suit generation
    # -----------------------------------------------------------------------

    def _generatePenthouseSuits(self):
        """Spawn DistributedSuitAI objects for the penthouse battle floor."""
        from toontown.building.SuitPlannerInteriorAI import SuitPlannerInteriorAI
        try:
            bldg = self.elevator.bldg
            difficulty = bldg.difficulty
            track = bldg.track
        except Exception:
            difficulty = 1
            track = 's'

        # numFloors=1 makes genFloorSuits(0) use the boss-floor level pool.
        planner = SuitPlannerInteriorAI(1, difficulty, track, self._zoneId)
        handles = planner.genFloorSuits(0)
        self._penthouseSuits = handles['activeSuits']
        self._penthouseActiveSuits = list(self._penthouseSuits)
        self.notify.debug('_generatePenthouseSuits: %d suits' % len(self._penthouseSuits))
        # Pick the SOS NPC reward now so it's stable for the whole battle and
        # available immediately when we transition to Reward state.
        self._sosNpcId = self._selectSOSNpc()
        self.notify.debug('_generatePenthouseSuits: sosNpcId=%d' % self._sosNpcId)

    # -----------------------------------------------------------------------
    # Penthouse battle lifecycle
    # -----------------------------------------------------------------------

    def _transitionToBattle(self, task):
        """Fire after BattleIntro; create the real penthouse battle."""
        self._createPenthouseBattle()
        self.d_setState('Battle')
        return Task.done

    def _createPenthouseBattle(self):
        """Instantiate DistributedCogdoBattleBldgAI and connect it to toons/suits.
        Using the Cogdo subclass ensures clients receive a DistributedCogdoBattleBldg
        DO, so getBossBattleTaunt() returns the correct cogdo-specific line."""
        from toontown.cogdominium.DistributedCogdoBattleBldgAI import DistributedCogdoBattleBldgAI
        toonIds = list(self._joinedToons) if self._joinedToons else list(self._toons[0])
        self._battle = DistributedCogdoBattleBldgAI(
            self.air,
            self._zoneId,
            self._handleBattleRoundDone,
            self._handleBattleDone,
            bossBattle=1)
        # Mark all joined toons as helpful so they receive merit/experience credit.
        self._battle.helpfulToons = list(toonIds)
        self._battle.setInitialMembers(toonIds, self._penthouseSuits)
        self._battle.generateWithRequired(self._zoneId)
        self.notify.debug('_createPenthouseBattle: battle DO %d' % self._battle.doId)

    def _handleBattleRoundDone(self, toonIds, totalHp, deadSuits):
        """Called by DistributedBattleBldgAI after each combat round."""
        for suit in deadSuits:
            if suit in self._penthouseActiveSuits:
                self._penthouseActiveSuits.remove(suit)
        if not self._penthouseActiveSuits:
            # All suits defeated — trigger the building-reward/experience sequence.
            self._battle.resume(0, topFloor=1)
        else:
            self._battle.resume()

    def _handleBattleDone(self, zoneId, activeToons):
        """Called by DistributedBattleBldgAI when the battle is fully resolved."""
        self.notify.debug('_handleBattleDone: activeToons=%s' % activeToons)
        self._cleanupPenthouseBattle()
        if not activeToons:
            # All toons went sad — fail out of the cogdo.
            self._transitionToFailed(None)
        else:
            # Toons won — award each surviving toon their SOS card, then prep
            # the street building and enter the Reward cutscene.
            self._awardSOSCards(activeToons)
            self._prepBuildingForExit()
            self.d_setState('Reward')
            taskMgr.doMethodLater(
                _REWARD_CLEANUP_DELAY,
                self._selfDelete,
                self.uniqueName('selfDelete'))

    def _selectSOSNpc(self):
        """Return an NPC ID drawn from FOnpcFriends weighted by neighbourhood difficulty.

        Star distribution follows TTO documentation:
          0-star more likely in TTC / Donald's Dock   (difficulty 0.00–0.33)
          1-star more likely in Daisy Gardens / MM    (difficulty 0.34–0.67)
          2-star more likely in The Brrrgh / DDL      (difficulty 0.68–1.00)
        Any star can appear in any neighbourhood; only the probabilities shift.
        """
        from toontown.cogdominium.CogdoGameConsts import getDifficulty
        from toontown.toon.NPCToons import npcFriendsMinMaxStars

        difficulty = getDifficulty(self._extZoneId)
        # Per-tier weight vectors: [0-star, 1-star, 2-star]
        if difficulty < 0.34:
            tierWeights = [70, 20, 10]
        elif difficulty < 0.68:
            tierWeights = [20, 60, 20]
        else:
            tierWeights = [10, 20, 70]

        # Build a flat pool where each NPC shares its tier's total weight equally.
        pool = []
        weights = []
        for star, tierWeight in enumerate(tierWeights):
            candidates = npcFriendsMinMaxStars(star, star)
            if not candidates:
                continue
            perNpc = tierWeight / len(candidates)
            for npcId in candidates:
                pool.append(npcId)
                weights.append(perNpc)

        if not pool:
            self.notify.warning('_selectSOSNpc: FOnpcFriends pool is empty!')
            return 0

        return random.choices(pool, weights=weights, k=1)[0]

    def _awardSOSCards(self, activeToons):
        """Give the pre-selected SOS card to every toon that survived the penthouse."""
        if not self._sosNpcId:
            self.notify.warning('_awardSOSCards: _sosNpcId not set; skipping award')
            return
        self.notify.debug('_awardSOSCards: npcId=%d toons=%s' % (
            self._sosNpcId, activeToons))
        for avId in activeToons:
            toon = self.air.doId2do.get(avId)
            if toon is None:
                self.notify.warning('_awardSOSCards: toon %d not found' % avId)
                continue
            toon.attemptAddNPCFriend(self._sosNpcId)

    def _cleanupPenthouseBattle(self):
        """Delete the suit DOs and battle DO."""
        for suit in list(self._penthouseSuits):
            try:
                if not suit.isDeleted():
                    suit.requestDelete()
            except Exception as e:
                self.notify.warning('_cleanupPenthouseBattle suit: %s' % e)
        self._penthouseSuits = []
        self._penthouseActiveSuits = []
        if self._battle is not None:
            try:
                if not self._battle.isDeleted():
                    self._battle.requestDelete()
            except Exception as e:
                self.notify.warning('_cleanupPenthouseBattle battle: %s' % e)
            self._battle = None

    # -----------------------------------------------------------------------
    # Failure path
    # -----------------------------------------------------------------------

    def _transitionToFailed(self, task):
        # Clean up any active maze game (normally done in mazeGameDone(), but
        # on the fail path mazeGameDone() is never called).
        if self._mazeGame:
            self._mazeGame.requestDelete()
            self._mazeGame = None
        # On failure the building stays as a field office — do NOT call
        # _prepBuildingForExit() which would trigger waitForVictorsFromCogdo
        # and squish the building.  Instead just remove the interior reference
        # and reopen the exterior elevator so the next group can attempt it.
        try:
            bldg = self.elevator.bldg
            if hasattr(bldg, 'interior') and bldg.interior is self:
                del bldg.interior
            if hasattr(bldg, 'elevator'):
                bldg.elevator.d_setFloor(-1)
                bldg.elevator.open()
        except Exception as e:
            self.notify.warning('_transitionToFailed cleanup: %s' % e)
        self.d_setState('Failed')
        taskMgr.doMethodLater(
            _FAIL_CLEANUP_DELAY,
            self._selfDelete,
            self.uniqueName('selfDelete'))
        return Task.done

    # -----------------------------------------------------------------------
    # Shared building / cleanup helpers  (success path only)
    # -----------------------------------------------------------------------

    def _prepBuildingForExit(self):
        """Put the street-side building into waitForVictorsFromCogdo so that
        when toons' interest changes back to the street the full exit animation
        (squash + toon walks out) plays correctly.  Only called on success."""
        self._bldg = None
        try:
            bldg = self.elevator.bldg
            toonIds = list(self._toons[0])
            while len(toonIds) < 4:
                toonIds.append(0)
            toonIds = toonIds[:4]
            bldg.fsm.request('waitForVictorsFromCogdo', [toonIds, []])
            # exitCogdo() (triggered by the FSM above) deletes bldg.elevator,
            # so save the reference for later cleanup.
            self._bldg = bldg
        except Exception as e:
            self.notify.warning('_prepBuildingForExit: %s' % e)

    def _selfDelete(self, task):
        try:
            bldg = self._bldg
            if bldg and hasattr(bldg, 'interior') and bldg.interior is self:
                del bldg.interior
        except Exception as e:
            self.notify.warning('_selfDelete: %s' % e)
        self.requestDelete()
        return Task.done

    def delete(self):
        taskMgr.remove(self.uniqueName('elevatorTransition'))
        taskMgr.remove(self.uniqueName('elevatorTimeout'))
        taskMgr.remove(self.uniqueName('elevatorToPenthouse'))
        taskMgr.remove(self.uniqueName('battleIntroDelay'))
        taskMgr.remove(self.uniqueName('selfDelete'))
        self._cleanupPenthouseBattle()
        if self._mazeGame:
            self._mazeGame.requestDelete()
            self._mazeGame = None
        DistributedObjectAI.delete(self)

    # -----------------------------------------------------------------------
    # Unused airecv stubs (required by DC)
    # -----------------------------------------------------------------------

    def reserveJoinDone(self):
        pass

    def toonLeftBarrelRoom(self):
        pass

    def toonBarrelRoomIntroDone(self):
        pass

    def setBarrelRoomReward(self, avIds, laffs):
        pass

    def toonBarrelRoomRewardDone(self):
        pass
