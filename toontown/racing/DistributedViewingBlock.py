from direct.distributed.ClockDelta import *
from direct.interval.IntervalGlobal import *
from toontown.building.ElevatorConstants import *
from toontown.building.ElevatorUtils import *
from toontown.building import DistributedElevatorExt
from toontown.building import DistributedElevator
from toontown.toonbase import ToontownGlobals
from direct.fsm import ClassicFSM
from direct.fsm import State
from direct.gui import DirectGui
from toontown.hood import ZoneUtil
from toontown.toonbase import TTLocalizer
from toontown.toontowngui import TTDialog
from direct.distributed import DistributedObject
from direct.distributed import DistributedSmoothNode
from direct.actor import Actor
from direct.fsm.FSM import FSM
from direct.showbase import PythonUtil
from toontown.toonbase.ToontownTimer import ToontownTimer
from toontown.racing.Kart import Kart
from toontown.racing.KartShopGlobals import KartGlobals
from toontown.racing.DistributedStartingBlock import DistributedStartingBlock
from toontown.toontowngui.TTDialog import TTGlobalDialog
from toontown.toontowngui.TeaserPanel import TeaserPanel
from panda3d.core import NodePath, Point3, CollisionNode, CollisionSphere
if (__debug__):
    import pdb

class DistributedViewingBlock(DistributedStartingBlock):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedViewingBlock')
    sphereRadius = 6

    def __init__(self, cr):
        DistributedStartingBlock.__init__(self, cr)
        self.timer = None
        return

    def delete(self):
        if self.timer != None:
            self.timer.destroy()
            del self.timer
        DistributedStartingBlock.delete(self)
        return

    def generateInit(self):
        self.notify.debugStateCall(self)
        DistributedObject.DistributedObject.generateInit(self)
        self.nodePath = NodePath(self.uniqueName('StartingBlock'))
        self.collSphere = CollisionSphere(-1, 6.75, -1, self.sphereRadius)
        self.collSphere.setTangible(0)
        self.collNode = CollisionNode(self.uniqueName('StartingBlockSphere'))
        self.collNode.setCollideMask(ToontownGlobals.WallBitmask)
        self.collNode.addSolid(self.collSphere)
        self.collNodePath = self.nodePath.attachNewNode(self.collNode)

    def announceGenerate(self):
        self.notify.debugStateCall(self)
        DistributedObject.DistributedObject.announceGenerate(self)
        self.nodePath.reparentTo(render)
        self.accept(self.uniqueName('enterStartingBlockSphere'), self.__handleEnterSphere)
        if (__debug__):
            if self.testLOD:
                self.__generateKartAppearTrack()

    def setPadLocationId(self, padLocationId):
        self.notify.debugStateCall(self)
        self.movieNode = self.nodePath.attachNewNode(self.uniqueName('MovieNode'))
        self.exitMovieNode = self.nodePath.attachNewNode(self.uniqueName('ExitMovieNode'))
        if padLocationId % 2:
            self.movieNode.setPosHpr(0, 6.5, 0, 0, 0, 0)
        else:
            self.movieNode.setPosHpr(0, -6.5, 0, 0, 0, 0)
        self.exitMovieNode.setPosHpr(3, 6.5, 0, 270, 0, 0)
        self.collNodePath.reparentTo(self.movieNode)

    def __handleEnterSphere(self, collEntry):
        if base.localAvatar.doId == self.lastAvId and globalClock.getFrameCount() <= self.lastFrame + 1:
            self.notify.debug('Ignoring duplicate entry for avatar.')
            return
        if base.localAvatar.hp > 0:

            def handleEnterRequest(self = self):
                self.ignore('stoppedAsleep')
                if hasattr(self.dialog, 'doneStatus') and self.dialog.doneStatus == 'ok':
                    self.d_requestEnter(base.cr.isPaid())
                else:
                    self.cr.playGame.getPlace().setState('walk')
                self.dialog.ignoreAll()
                self.dialog.cleanup()
                del self.dialog

            self.cr.playGame.getPlace().fsm.request('stopped')
            self.accept('stoppedAsleep', handleEnterRequest)
            doneEvent = 'enterRequest|dialog'
            msg = TTLocalizer.StartingBlock_EnterShowPad
            self.dialog = TTGlobalDialog(msg, doneEvent, 4)
            self.dialog.accept(doneEvent, handleEnterRequest)

    def generateCameraMoveTrack(self):
        self.cPos = camera.getPos(self.av)
        self.cHpr = camera.getHpr(self.av)
        cameraPos = Point3(23, -10, 7)
        cameraHpr = Point3(65, -10, 0)
        camera.wrtReparentTo(self.nodePath)
        cameraTrack = LerpPosHprInterval(camera, 1.5, cameraPos, cameraHpr)
        return cameraTrack

    def makeGui(self):
        self.notify.debugStateCall(self)
        if self.timer != None:
            return
        self.timer = ToontownTimer()
        self.timer.setScale(0.3)
        self.timer.setPos(1.16, 0, -.73)
        self.timer.hide()
        DistributedStartingBlock.makeGui(self)
        return

    def showGui(self):
        self.notify.debugStateCall(self)
        self.timer.show()
        DistributedStartingBlock.showGui(self)

    def hideGui(self):
        self.notify.debugStateCall(self)
        if not hasattr(self, 'timer') or self.timer == None:
            return
        self.timer.reset()
        self.timer.hide()
        DistributedStartingBlock.hideGui(self)
        return

    def countdown(self):
        countdownTime = KartGlobals.COUNTDOWN_TIME - globalClockDelta.localElapsedTime(self.kartPad.getTimestamp(self.avId))
        self.timer.countdown(countdownTime)

    def enterEnterMovie(self):
        self.notify.debug('%d enterEnterMovie: Entering the Enter Movie State.' % self.doId)
        if config.ConfigVariableBool('want-qa-regression', 0).getValue():
            raceName = TTLocalizer.KartRace_RaceNames[self.kartPad.trackType]
            self.notify.info('QA-REGRESSION: KARTING: %s' % raceName)
        pos = self.nodePath.getPos(render)
        hpr = self.nodePath.getHpr(render)
        pos.addZ(1.7)
        hpr.addX(270)
        self.kartNode.setPosHpr(pos, hpr)
        toonTrack = self.generateToonMoveTrack()
        kartTrack = self.generateKartAppearTrack()
        jumpTrack = self.generateToonJumpTrack()
        name = self.av.uniqueName('EnterRaceTrack')
        if self.av != None and self.localToonKarting:
            cameraTrack = self.generateCameraMoveTrack()
            self.finishMovie()
            self.movieTrack = Sequence(Parallel(cameraTrack, Sequence()), kartTrack, jumpTrack, Func(self.makeGui), Func(self.showGui), Func(self.countdown), Func(self.request, 'Waiting'), Func(self.d_movieFinished), name=name, autoFinish=1)
        else:
            self.finishMovie()
            self.movieTrack = Sequence(toonTrack, kartTrack, jumpTrack, name=name, autoFinish=1)
        self.movieTrack.start()
        self.exitRequested = True
        return