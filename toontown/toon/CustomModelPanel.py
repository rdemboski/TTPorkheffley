from direct.gui.DirectGui import DirectFrame, DirectButton, DirectLabel
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import Vec4
from toontown.toonbase import ToontownGlobals

# Registry of available custom models.
# Add a new entry here whenever you add a new model ID to generateCustomModel.
CUSTOM_MODELS = [
    (0, 'Normal Toon'),
    (1, 'Sora'),
]

_PANEL_COLOR      = (0.08, 0.12, 0.45, 0.92)
_BTN_IDLE_COLOR   = (0.15, 0.20, 0.60, 1.0)
_BTN_HOVER_COLOR  = (0.25, 0.35, 0.75, 1.0)
_BTN_ACTIVE_COLOR = (0.20, 0.55, 0.25, 1.0)  # green = currently equipped
_TEXT_COLOR       = Vec4(1, 1, 1, 1)
_BTN_WIDTH        = 0.28
_BTN_HEIGHT       = 0.10
_PANEL_PAD        = 0.05

# Position of the toggle button relative to base.a2dBottomLeft.
# Sits just above the laff meter (which lives at roughly Z=0.13).
_TOGGLE_X = 0.13
_TOGGLE_Z = 0.24

class CustomModelPanel(DirectFrame):

    def __init__(self):
        numModels = len(CUSTOM_MODELS)
        panelHeight = numModels * _BTN_HEIGHT + _PANEL_PAD * 2 + 0.11

        DirectFrame.__init__(
            self,
            relief=DGG.GROOVE,
            frameColor=_PANEL_COLOR,
            frameSize=(-_BTN_WIDTH - _PANEL_PAD,
                        _BTN_WIDTH + _PANEL_PAD,
                        0,
                        panelHeight),
            sortOrder=50,
        )
        self.initialiseoptions(CustomModelPanel)

        self._currentModelId = 0
        self._buttons = {}

        DirectLabel(
            parent=self,
            text='Custom Models',
            text_scale=0.055,
            text_fg=_TEXT_COLOR,
            text_font=ToontownGlobals.getInterfaceFont(),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, panelHeight - 0.07),
        )

        for i, (modelId, modelName) in enumerate(CUSTOM_MODELS):
            # Stack buttons from the top downward
            yPos = panelHeight - 0.12 - i * _BTN_HEIGHT
            btn = DirectButton(
                parent=self,
                text=modelName,
                text_scale=0.05,
                text_fg=_TEXT_COLOR,
                text_font=ToontownGlobals.getInterfaceFont(),
                frameSize=(-_BTN_WIDTH, _BTN_WIDTH, -0.035, 0.045),
                frameColor=_BTN_IDLE_COLOR,
                relief=DGG.RAISED,
                pos=(0, 0, yPos),
                command=self._onModelSelected,
                extraArgs=[modelId],
            )
            btn.bind(DGG.ENTER, self._onBtnEnter, [modelId])
            btn.bind(DGG.EXIT,  self._onBtnExit,  [modelId])
            self._buttons[modelId] = btn

        self._refreshButtonColors()

        # Persistent toggle button — anchored just above the laff meter
        self._toggleBtn = DirectButton(
            parent=base.a2dBottomLeft,
            text='Models',
            text_scale=0.05,
            text_fg=_TEXT_COLOR,
            text_font=ToontownGlobals.getInterfaceFont(),
            frameSize=(-0.09, 0.09, -0.03, 0.04),
            frameColor=_BTN_IDLE_COLOR,
            relief=DGG.RAISED,
            pos=(_TOGGLE_X, 0, _TOGGLE_Z),
            sortOrder=50,
            command=self.togglePanel,
        )

        self.reparentTo(hidden)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def togglePanel(self):
        if self.getParent() != hidden:
            self.hidePanel()
        else:
            self.showPanel()

    def showPanel(self):
        # Anchor the panel to base.a2dBottomLeft, opening upward from the toggle button
        self.reparentTo(base.a2dBottomLeft)
        self.setPos(_TOGGLE_X, 0, _TOGGLE_Z + 0.05)

    def hidePanel(self):
        self.reparentTo(hidden)

    def destroy(self):
        self._toggleBtn.destroy()
        self.reparentTo(hidden)
        DirectFrame.destroy(self)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _onModelSelected(self, modelId):
        base.localAvatar.requestCustomModel(modelId)
        self._currentModelId = modelId
        self._refreshButtonColors()

    def _onBtnEnter(self, modelId, _event):
        if modelId != self._currentModelId:
            self._buttons[modelId]['frameColor'] = _BTN_HOVER_COLOR

    def _onBtnExit(self, modelId, _event):
        if modelId != self._currentModelId:
            self._buttons[modelId]['frameColor'] = _BTN_IDLE_COLOR

    def _refreshButtonColors(self):
        for modelId, btn in self._buttons.items():
            btn['frameColor'] = (
                _BTN_ACTIVE_COLOR if modelId == self._currentModelId
                else _BTN_IDLE_COLOR
            )