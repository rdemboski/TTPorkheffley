from direct.directnotify import DirectNotifyGlobal

class SuitPlannerCogdoInteriorAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('SuitPlannerCogdoInteriorAI')

    def __init__(self, cogdoLayout, difficulty, track, zoneId):
        self.cogdoLayout = cogdoLayout
        self.difficulty = difficulty
        self.track = track
        self.zoneId = zoneId
