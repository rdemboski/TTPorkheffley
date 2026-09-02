from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from toontown.parties.DistributedPartyActivityAI import DistributedPartyActivityAI
from toontown.parties.activityFSMs import TeamActivityAIFSM
from toontown.parties import PartyGlobals

class DistributedPartyTeamActivityAI(DistributedPartyActivityAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPartyTeamActivityAI")

    minPlayersPerTeam = PartyGlobals.TeamActivityDefaultMinPlayersPerTeam
    maxPlayersPerTeam = PartyGlobals.TeamActivityDefaultMaxPlayersPerTeam
    duration = 60
    canSwitchTeams = True

    def __init__(self, air, parent, activityTuple):
        DistributedPartyActivityAI.__init__(self, air, parent, activityTuple)
        # Initialize toonIds here so getToonsPlaying() works when called
        # by aiFormatGenerate() before generate() runs (setToonsPlaying is required)
        self.toonIds = [[], []]

    def getPlayersPerTeam(self):
        return (self.minPlayersPerTeam, self.maxPlayersPerTeam)

    def getDuration(self):
        return int(self.duration)

    def getCanSwitchTeams(self):
        return self.canSwitchTeams

    def getToonsPlaying(self):
        return (list(self.toonIds[0]), list(self.toonIds[1]))

    # --- lifecycle ---

    def generate(self):
        DistributedPartyActivityAI.generate(self)
        self.toonIds = [[], []]
        self.activityFSM = TeamActivityAIFSM(self)
        self.activityFSM.request('WaitForEnough')

    def delete(self):
        taskMgr.remove(self.uniqueName('waitToStartTimer'))
        taskMgr.remove(self.uniqueName('startActiveTask'))
        taskMgr.remove(self.uniqueName('activeTimer'))
        taskMgr.remove(self.uniqueName('conclusionTimer'))
        self.activityFSM.request('Final')
        del self.activityFSM
        del self.toonIds
        DistributedPartyActivityAI.delete(self)

    # --- required field getters (no state needed) ---

    def setState(self, todo0, todo1, todo2):
        pass

    def setToonsPlaying(self, todo0, todo1):
        pass

    def setAdvantage(self, todo0):
        pass

    def switchTeamRequestDenied(self, todo0):
        pass

    # --- broadcast helpers ---

    def _broadcastState(self, stateName, data=0):
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('setState', [stateName, timestamp, data])

    def _broadcastToonsPlaying(self):
        self.sendUpdate('setToonsPlaying', [list(self.toonIds[0]), list(self.toonIds[1])])

    # --- FSM state handlers ---

    def startWaitForEnough(self):
        self._broadcastState('WaitForEnough')

    def finishWaitForEnough(self):
        pass

    def startWaitToStart(self):
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('setState', ['WaitToStart', timestamp, 0])
        taskMgr.doMethodLater(
            PartyGlobals.TeamActivityStartDelay,
            self._waitToStartExpired,
            self.uniqueName('waitToStartTimer')
        )

    def finishWaitToStart(self):
        taskMgr.remove(self.uniqueName('waitToStartTimer'))

    def _waitToStartExpired(self, task):
        if self.activityFSM.getCurrentOrNextState() == 'WaitToStart':
            self.activityFSM.request('WaitClientsReady')
        return task.done

    def startWaitClientsReady(self):
        # Broadcast WaitClientsReady so clients show their rules panel, then
        # wait DefaultRulesTimeout before sending Active. Using a non-zero
        # delay also avoids AlreadyInTransition since we're still inside the
        # enterWaitClientsReady FSM callback when this runs.
        self._broadcastState('WaitClientsReady')
        taskMgr.doMethodLater(
            PartyGlobals.DefaultRulesTimeout,
            self._startActiveTask,
            self.uniqueName('startActiveTask')
        )

    def finishWaitClientsReady(self):
        taskMgr.remove(self.uniqueName('startActiveTask'))

    def _startActiveTask(self, task):
        self._startActive()
        return task.done

    def _startActive(self):
        self.activityFSM.request('Active')

    def startActive(self):
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('setState', ['Active', timestamp, 0])
        taskMgr.doMethodLater(
            self.duration,
            self._activeTimerExpired,
            self.uniqueName('activeTimer')
        )

    def finishActive(self):
        taskMgr.remove(self.uniqueName('activeTimer'))

    def _activeTimerExpired(self, task):
        if self.activityFSM.getCurrentOrNextState() == 'Active':
            self.activityFSM.request('Conclusion', PartyGlobals.TeamActivityNeitherTeam)
        return task.done

    def startConclusion(self, losingTeam=PartyGlobals.TeamActivityNeitherTeam):
        losingTeamVal = losingTeam.value if hasattr(losingTeam, 'value') else int(losingTeam)
        self._broadcastState('Conclusion', losingTeamVal)
        taskMgr.doMethodLater(
            PartyGlobals.TugOfWarConclusionDuration,
            self._conclusionExpired,
            self.uniqueName('conclusionTimer')
        )

    def finishConclusion(self):
        taskMgr.remove(self.uniqueName('conclusionTimer'))

    def _conclusionExpired(self, task):
        if self.activityFSM.getCurrentOrNextState() == 'Conclusion':
            self.toonIds = [[], []]
            self._broadcastToonsPlaying()
            self.activityFSM.request('WaitForEnough')
        return task.done

    # --- toon join/exit/switch ---

    def _getTeamOfToon(self, avId):
        for team in range(2):
            if avId in self.toonIds[team]:
                return team
        return None

    def toonJoinRequest(self, team):
        avId = self.air.getAvatarIdFromSender()
        state = self.activityFSM.getCurrentOrNextState()
        if state not in ('WaitForEnough', 'WaitToStart'):
            self.sendUpdateToAvatarId(avId, 'joinRequestDenied', [PartyGlobals.DenialReasons.Default])
            return
        if self._getTeamOfToon(avId) is not None:
            return  # already on a team
        team = int(team)
        if len(self.toonIds[team]) >= self.maxPlayersPerTeam:
            self.sendUpdateToAvatarId(avId, 'joinRequestDenied', [PartyGlobals.DenialReasons.Full])
            return
        self.toonIds[team].append(avId)
        self._broadcastToonsPlaying()
        self._checkEnoughPlayers()

    def toonExitRequest(self, team):
        avId = self.air.getAvatarIdFromSender()
        currentTeam = self._getTeamOfToon(avId)
        if currentTeam is None:
            return
        self.toonIds[currentTeam].remove(avId)
        self._broadcastToonsPlaying()
        state = self.activityFSM.getCurrentOrNextState()
        if state == 'WaitToStart':
            self._checkEnoughPlayers()

    def toonSwitchTeamRequest(self):
        avId = self.air.getAvatarIdFromSender()
        if not self.canSwitchTeams:
            self.sendUpdateToAvatarId(avId, 'switchTeamRequestDenied', [PartyGlobals.DenialReasons.Default])
            return
        currentTeam = self._getTeamOfToon(avId)
        if currentTeam is None:
            return
        otherTeam = 1 - currentTeam
        if len(self.toonIds[otherTeam]) >= self.maxPlayersPerTeam:
            self.sendUpdateToAvatarId(avId, 'switchTeamRequestDenied', [PartyGlobals.DenialReasons.Full])
            return
        self.toonIds[currentTeam].remove(avId)
        self.toonIds[otherTeam].append(avId)
        self._broadcastToonsPlaying()

    def _checkEnoughPlayers(self):
        leftCount = len(self.toonIds[0])
        rightCount = len(self.toonIds[1])
        hasEnough = leftCount >= self.minPlayersPerTeam and rightCount >= self.minPlayersPerTeam
        state = self.activityFSM.getCurrentOrNextState()
        if hasEnough and state == 'WaitForEnough':
            self.activityFSM.request('WaitToStart')
        elif not hasEnough and state == 'WaitToStart':
            self.activityFSM.request('WaitForEnough')

    # --- toon ready (from WaitForServer state on client) ---

    def toonReady(self):
        pass  # We skip WaitClientsReady, so nothing to do here
