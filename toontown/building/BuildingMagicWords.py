"""BuildingMagicWords.py — dev/testing magic words for building manipulation."""
from otp.ai.MagicWordGlobal import *
from toontown.building.DistributedBuildingAI import DistributedBuildingAI

@magicWord(category=CATEGORY_OVERRIDE, types=[int, int])
def fieldoffice(difficulty=1, floors=1):
    """Force a nearby toon or suit building to become a cogdo field office.
    Usage: ~fieldoffice [difficulty] [floors]
      difficulty 0-3, default 1
      floors 1-3, default 1  (number of maze game floors before the penthouse)"""
    av = spellbook.getInvoker()
    zoneId = av.getLocation()[1]
    branchZone = zoneId - (zoneId % 100)

    bm = simbase.air.buildingManagers.get(branchZone)
    if bm is None:
        # Also try the exact zone in case rounding was wrong.
        bm = simbase.air.buildingManagers.get(zoneId)
    if bm is None:
        return 'No building manager found for zone %d.' % zoneId

    buildings = bm.getBuildings()
    if not buildings:
        return 'No buildings found in zone %d.' % branchZone

    difficulty = max(0, min(int(difficulty), 3))
    # buildingHeight = floors - 1 (cogdoTakeOver adds 1 internally).
    # Clamp to a sane range so we never produce a 0- or 10-floor office.
    buildingHeight = max(0, min(int(floors) - 1, 5))

    # Prefer a toon building (cleanest conversion); fall back to a suit building.
    # Only consider DistributedBuildingAI instances — gagshops, HQ buildings, etc.
    # are also in getBuildings() but don't have an fsm and can't be converted.
    toon_bldg = None
    suit_bldg = None
    for bldg in buildings:
        if not isinstance(bldg, DistributedBuildingAI):
            continue
        state = bldg.fsm.getCurrentState().getName()
        if state == 'toon' and toon_bldg is None:
            toon_bldg = bldg
        elif state == 'suit' and suit_bldg is None:
            suit_bldg = bldg

    target = toon_bldg or suit_bldg
    if target is None:
        return 'No convertible buildings found in zone %d (all may already be cogdos or in transition).' % branchZone

    state = target.fsm.getCurrentState().getName()

    def _convert(bldg):
        bldg.cogdoTakeOver(difficulty, buildingHeight)
        # cogdoTakeOver will silently randomize numFloors if buildingHeight falls
        # outside the valid range for this difficulty level.  Override it here
        # so the requested floor count is always honoured.
        bldg.numFloors = buildingHeight + 1

    if state == 'toon':
        # Clean path: toon → clearOutToonInteriorForCogdo → becomingCogdo → cogdo
        _convert(target)
        return 'Converting toon building (block %d) to cogdo field office (difficulty %d, %d floor(s)).' % (target.block, difficulty, buildingHeight + 1)

    elif state == 'suit':
        # Force the building back through toon state first, then into cogdo.
        # suit → becomingToon  (exit cleans up elevator/planner)
        if target.suitPlannerExt:
            target.suitPlannerExt.recycleBuilding()
        target.fsm.request('becomingToon')
        # Cancel the normal victory-sequence delay; jump straight to toon.
        taskMgr.remove(target.taskName(str(target.block) + '_becomingToon-timer'))
        # becomingToon → toon  (enter creates interior, door, knockKnock)
        target.fsm.request('toon')
        # toon → clearOutToonInteriorForCogdo → becomingCogdo → cogdo
        _convert(target)
        return 'Converting suit building (block %d) to cogdo field office (difficulty %d, %d floor(s)).' % (target.block, difficulty, buildingHeight + 1)

    return 'Building (block %d) is in state "%s" and cannot be converted right now.' % (target.block, state)
