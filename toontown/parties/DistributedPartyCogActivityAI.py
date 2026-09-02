from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from toontown.parties.DistributedPartyTeamActivityAI import DistributedPartyTeamActivityAI
from toontown.parties import PartyGlobals

# How often the server broadcasts updated cog distances (seconds)
_COG_UPDATE_RATE = 0.5

class DistributedPartyCogActivityAI(DistributedPartyTeamActivityAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPartyCogActivityAI")

    minPlayersPerTeam = PartyGlobals.CogActivityMinPlayersPerTeam
    maxPlayersPerTeam = PartyGlobals.CogActivityMaxPlayersPerTeam
    duration = PartyGlobals.CogActivityDuration
    canSwitchTeams = PartyGlobals.CogActivityBalanceTeams

    # --- lifecycle ---

    def generate(self):
        DistributedPartyTeamActivityAI.generate(self)
        self._resetGameState()

    def delete(self):
        taskMgr.remove(self.uniqueName('cogUpdateTask'))
        DistributedPartyTeamActivityAI.delete(self)

    # --- state handlers ---

    def startActive(self):
        self._resetGameState()
        DistributedPartyTeamActivityAI.startActive(self)
        taskMgr.doMethodLater(
            _COG_UPDATE_RATE,
            self._cogUpdateTask,
            self.uniqueName('cogUpdateTask')
        )

    def finishActive(self):
        taskMgr.remove(self.uniqueName('cogUpdateTask'))
        DistributedPartyTeamActivityAI.finishActive(self)

    def startConclusion(self, losingTeam=PartyGlobals.TeamActivityNeitherTeam):
        taskMgr.remove(self.uniqueName('cogUpdateTask'))

        leftScore = self.teamScores[0]
        rightScore = self.teamScores[1]

        # Determine which team lost based on hit-point totals
        if leftScore > rightScore:
            losingTeamVal = int(PartyGlobals.TeamActivityTeams.RightTeam)
        elif rightScore > leftScore:
            losingTeamVal = int(PartyGlobals.TeamActivityTeams.LeftTeam)
        else:
            losingTeamVal = PartyGlobals.TeamActivityNeitherTeam

        self._awardJellybeans(losingTeamVal)

        # Encode both teams' hit-point totals into the conclusion data so the
        # client can display per-team scores and determine the winner.
        # The client decodes as: leftScore = data // 10000, rightScore = data % 10000
        conclusionData = leftScore * 10000 + rightScore

        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('setState', ['Conclusion', timestamp, conclusionData])
        taskMgr.doMethodLater(
            PartyGlobals.CogActivityConclusionDuration,
            self._conclusionExpired,
            self.uniqueName('conclusionTimer')
        )

    # --- game logic ---

    def _resetGameState(self):
        # 3 cogs start at the centre (T = 0.0).
        # T = -1.0 is one barrier end, T = +1.0 is the other.
        self.cogDistances = [0.0, 0.0, 0.0]
        self.teamScores = [0, 0]   # hit-point totals per team
        self.toonHitScores = {}    # avId -> individual hit-point total
        self.highScoreName = ''
        self.highScore = 0

    def _cogUpdateTask(self, task):
        if self.activityFSM.getCurrentOrNextState() != 'Active':
            return task.done
        self.sendUpdate('setCogDistances', [list(self.cogDistances)])
        return task.again

    def pieHitsCog(self, toonId, timestamp, hitCogNum, x, y, z, direction, part):
        """Received from the client that scored the hit (clsend broadcast airecv)."""
        if self.activityFSM.getCurrentOrNextState() != 'Active':
            return

        avId = self.air.getAvatarIdFromSender()
        team = self._getTeamOfToon(avId)
        if team is None:
            return
        if not (0 <= hitCogNum <= 2):
            return

        # A pie thrown from the left (direction = -1.0) pushes the cog to the
        # right (+T direction), and vice-versa.  So the position delta is the
        # negative of the direction value.
        if part:
            pushFactor = PartyGlobals.CogPinataPushHeadFactor
            hitPoints = PartyGlobals.CogActivityHitPointsForHead
        else:
            pushFactor = PartyGlobals.CogPinataPushBodyFactor
            hitPoints = PartyGlobals.CogActivityHitPoints

        self.cogDistances[hitCogNum] = max(
            -1.0, min(1.0, self.cogDistances[hitCogNum] + direction * pushFactor)
        )

        # Accumulate per-team and per-toon scores
        self.teamScores[team] += hitPoints
        toonScore = self.toonHitScores.get(avId, 0) + hitPoints
        self.toonHitScores[avId] = toonScore

        # Broadcast new high score if this toon just set one
        if toonScore > self.highScore:
            self.highScore = toonScore
            av = self.air.doId2do.get(avId)
            if av:
                self.highScoreName = av.getName()
                self.sendUpdate('setHighScore', [self.highScoreName, self.highScore])

        # Push an immediate position update so clients see the cog move at once
        self.sendUpdate('setCogDistances', [list(self.cogDistances)])

    # --- jellybean reward ---

    def _awardJellybeans(self, losingTeamVal):
        from toontown.toonbase import TTLocalizer
        for team in range(2):
            for avId in self.toonIds[team]:
                av = self.air.doId2do.get(avId)
                if not av:
                    continue
                if losingTeamVal == PartyGlobals.TeamActivityNeitherTeam:
                    reward = PartyGlobals.CogActivityTieBeans
                elif team == losingTeamVal:
                    reward = PartyGlobals.CogActivityLossBeans
                else:
                    reward = PartyGlobals.CogActivityWinBeans
                av.addMoney(reward)
                self.sendUpdateToAvatarId(avId, 'showJellybeanReward', [
                    reward,
                    av.getMoney(),
                    TTLocalizer.PartyTeamActivityRewardMessage % reward
                ])

    # --- DC stubs (clsend broadcast; Astron relays automatically) ---

    def pieThrow(self, todo0, todo1, todo2, todo3, todo4, todo5, todo6):
        pass

    def pieHitsToon(self, todo0, todo1, todo2, todo3, todo4):
        pass

    def setCogDistances(self, todo0):
        pass

    def setHighScore(self, todo0, todo1):
        pass
