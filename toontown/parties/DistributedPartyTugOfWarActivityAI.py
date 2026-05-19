from direct.directnotify import DirectNotifyGlobal
from toontown.parties.DistributedPartyTeamActivityAI import DistributedPartyTeamActivityAI
from toontown.parties import PartyGlobals

class DistributedPartyTugOfWarActivityAI(DistributedPartyTeamActivityAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPartyTugOfWarActivityAI")

    minPlayersPerTeam = PartyGlobals.TugOfWarMinimumPlayersPerTeam
    maxPlayersPerTeam = PartyGlobals.TugOfWarMaximumPlayersPerTeam
    duration = PartyGlobals.TugOfWarDuration
    canSwitchTeams = False

    def generate(self):
        DistributedPartyTeamActivityAI.generate(self)
        self.teamForces = [0.0, 0.0]   # accumulated force per team
        self.ropeOffset = 0.0          # current tug position

    def delete(self):
        taskMgr.remove(self.uniqueName('tugUpdate'))
        del self.teamForces
        del self.ropeOffset
        DistributedPartyTeamActivityAI.delete(self)

    def startActive(self):
        self.teamForces = [0.0, 0.0]
        self.ropeOffset = 0.0
        DistributedPartyTeamActivityAI.startActive(self)
        taskMgr.doMethodLater(
            PartyGlobals.TugOfWarKeyPressReportRate,
            self._tugUpdateTask,
            self.uniqueName('tugUpdate')
        )

    def finishActive(self):
        taskMgr.remove(self.uniqueName('tugUpdate'))
        DistributedPartyTeamActivityAI.finishActive(self)

    def startConclusion(self, losingTeam=PartyGlobals.TeamActivityNeitherTeam):
        losingTeamVal = losingTeam.value if hasattr(losingTeam, 'value') else int(losingTeam)

        # Award jellybeans to all participating toons
        self._awardJellybeans(losingTeamVal)

        # Broadcast conclusion state and start the conclusion timer
        from direct.distributed.ClockDelta import globalClockDelta
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('setState', ['Conclusion', timestamp, losingTeamVal])
        taskMgr.doMethodLater(
            PartyGlobals.TugOfWarConclusionDuration,
            self._conclusionExpired,
            self.uniqueName('conclusionTimer')
        )

    def _awardJellybeans(self, losingTeamVal):
        from toontown.toonbase import TTLocalizer
        for team in range(2):
            for avId in self.toonIds[team]:
                av = self.air.doId2do.get(avId)
                if not av:
                    continue
                if losingTeamVal == PartyGlobals.TeamActivityNeitherTeam:
                    # Timer expired with no fall-in — treat as a tie
                    reward = PartyGlobals.TugOfWarTieReward
                elif team == losingTeamVal:
                    # This toon's team fell in — they lose
                    reward = PartyGlobals.TugOfWarFallInLossReward
                else:
                    # This toon's team pulled the other in — they win
                    reward = PartyGlobals.TugOfWarFallInWinReward
                av.addMoney(reward)
                self.sendUpdateToAvatarId(avId, 'showJellybeanReward', [
                    reward,
                    av.getMoney(),
                    TTLocalizer.PartyTeamActivityRewardMessage % reward
                ])

    def reportKeyRateForce(self, keyRate, force):
        avId = self.air.getAvatarIdFromSender()
        if self.activityFSM.getCurrentOrNextState() != 'Active':
            return
        # Broadcast key rate to other clients so they see the animation
        self.sendUpdate('updateToonKeyRate', [avId, keyRate])
        # Accumulate force: left team pulls negative, right team pulls positive
        team = self._getTeamOfToon(avId)
        if team is None:
            return
        if team == PartyGlobals.TeamActivityTeams.LeftTeam:
            self.teamForces[0] = force
        else:
            self.teamForces[1] = force

    def _tugUpdateTask(self, task):
        if self.activityFSM.getCurrentOrNextState() != 'Active':
            return task.done
        leftForce = sum(self.teamForces[0:1])
        rightForce = sum(self.teamForces[1:2])
        netForce = rightForce - leftForce
        self.ropeOffset += netForce * PartyGlobals.TugOfWarKeyPressReportRate * 0.1
        # Clamp offset — if beyond fall threshold, conclusion is triggered by client via reportFallIn
        self.ropeOffset = max(-10.0, min(10.0, self.ropeOffset))
        self.sendUpdate('updateToonPositions', [self.ropeOffset])
        return task.again

    def reportFallIn(self, losingTeam):
        avId = self.air.getAvatarIdFromSender()
        if self.activityFSM.getCurrentOrNextState() != 'Active':
            return
        losingTeam = int(losingTeam)
        self.activityFSM.request('Conclusion', losingTeam)

    def setToonsPlaying(self, todo0, todo1):
        pass

    def updateToonKeyRate(self, todo0, todo1):
        pass

    def updateToonPositions(self, todo0):
        pass
