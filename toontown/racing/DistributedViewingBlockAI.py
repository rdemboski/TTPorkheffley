from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.racing.KartShopGlobals import KartGlobals
from toontown.racing.DistributedStartingBlockAI import DistributedStartingBlockAI

class DistributedViewingBlockAI(DistributedStartingBlockAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedViewingBlockAI")
    
    def __init__(self, air):
        DistributedStartingBlockAI.__init__(self, air)
        self.air = air
        
    def requestEnter(self, isPaid):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do[avId]
        if not av.hasKart():
            self.sendUpdateToAvatarId(avId, 'rejectEnter', [KartGlobals.ERROR_CODE.eNoKart])
            return
        if self.avId != 0:
            if self.avId == avId:
                self.air.writeServerEvent('suspicious', avId=avId, issue='Toon tried to board the same starting block twice!')
            self.sendUpdateToAvatarId(avId, 'rejectEnter', [KartGlobals.ERROR_CODE.eOccupied])
            return
        self.b_setOccupied(avId)
        self.b_setMovie(KartGlobals.ENTER_MOVIE)
        taskMgr.doMethodLater(30, DistributedViewingBlockAI.b_setMovie, 'removePlayer%i' % self.doId, [self, KartGlobals.EXIT_MOVIE])
        
    def requestExit(self):
        DistributedStartingBlockAI.requestExit(self)
        taskMgr.remove('removePlayer%i' % self.doId)