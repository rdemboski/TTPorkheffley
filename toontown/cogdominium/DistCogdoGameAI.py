from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.distributed.ClockDelta import globalClockDelta
from toontown.cogdominium import CogdoGameConsts


class DistCogdoGameAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoGameAI")

    def __init__(self, air, interiorId, exteriorZone, toonIds):
        DistributedObjectAI.__init__(self, air)
        self._interiorId = interiorId
        self._exteriorZone = exteriorZone
        self._toonIds = list(toonIds)
        self._difficultyOverride = CogdoGameConsts.NoDifficultyOverride
        self._exteriorZoneOverride = CogdoGameConsts.NoExteriorZoneOverride
        self._readyToons = set()

    # --- Required broadcast ram getters ---

    def setInteriorId(self, interiorId):
        self._interiorId = interiorId

    def getInteriorId(self):
        return self._interiorId

    def setExteriorZone(self, exteriorZone):
        self._exteriorZone = exteriorZone

    def getExteriorZone(self):
        return self._exteriorZone

    def setDifficultyOverrides(self, difficultyOverride, exteriorZoneOverride):
        self._difficultyOverride = difficultyOverride
        self._exteriorZoneOverride = exteriorZoneOverride

    def getDifficultyOverrides(self):
        return (self._difficultyOverride, self._exteriorZoneOverride)

    # --- Broadcasts to clients ---

    def d_setVisible(self):
        self.sendUpdate('setVisible', [])

    def d_setIntroStart(self):
        self.sendUpdate('setIntroStart', [])

    def d_setGameStart(self):
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('setGameStart', [timestamp])

    def d_setGameFinish(self):
        timestamp = globalClockDelta.getRealNetworkTime()
        self.sendUpdate('setGameFinish', [timestamp])

    # --- Avatar ready tracking (airecv clsend) ---

    def setAvatarReady(self):
        avId = self.air.getAvatarIdFromSender()
        self.notify.debug('setAvatarReady from %d (%d/%d ready)' % (
            avId, len(self._readyToons) + 1, max(len(self._toonIds), 1)))
        self._readyToons.add(avId)
        if not self._toonIds or len(self._readyToons) >= len(self._toonIds):
            self.d_setGameStart()
            self._onGameStarted()

    def _onGameStarted(self):
        """Override in subclasses to start game-specific timers."""
        pass

    # --- Unused broadcast stubs (satisfy DC system) ---

    def setVisible(self):
        pass

    def setIntroStart(self):
        pass

    def setToonSad(self, toonId):
        pass

    def setToonDisconnect(self, toonId):
        pass

    def setGameStart(self, timestamp):
        pass

    def setGameFinish(self, timestamp):
        pass
