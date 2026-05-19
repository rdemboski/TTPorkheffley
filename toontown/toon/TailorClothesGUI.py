from toontown.makeatoon import ClothesGUI
from . import ToonDNA

class TailorClothesGUI(ClothesGUI.ClothesGUI):
    notify = directNotify.newCategory('MakeClothesGUI')

    def __init__(self, doneEvent, swapEvent, tailorId):
        ClothesGUI.ClothesGUI.__init__(self, ClothesGUI.CLOTHES_TAILOR, doneEvent, swapEvent)
        self.tailorId = tailorId

    def setupScrollInterface(self):
        self.dna = self.toon.getStyle()
        gender = self.dna.getGender()
        if gender != self.gender:
            self.topStyles = ToonDNA.getTopStyles(gender, tailorId=self.tailorId)
            self.tops = ToonDNA.getTops(gender, tailorId=self.tailorId)
            self.bottomStyles = ToonDNA.getBottomStyles(gender, tailorId=self.tailorId)
            self.bottoms = ToonDNA.getBottoms(gender, tailorId=self.tailorId)
            self.gender = gender
            self.topChoice = 0
            self.topColorChoice = 0
            self.topStyleChoice = 0
            self.bottomStyleChoice = 0
            self.bottomColorChoice = 0
            self.bottomChoice = 0
        self.setupButtons()
        return
