from direct.directnotify import DirectNotifyGlobal
from toontown.pets import PetUtil, PetDNA, PetNameGenerator
from toontown.toonbase import ToontownGlobals
from toontown.ai.DatabaseObject import DatabaseObject
import random
import time


class PetManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('PetManagerAI')

    def __init__(self, air):
        self.air = air

    def getAvailablePets(self, numPets, difficulty):
        """Return a list of random integer seeds for displayable pets."""
        seeds = []
        for i in range(numPets):
            seeds.append(random.randint(0, 2 ** 31 - 1))
        return seeds

    def createNewPetFromSeed(self, avId, seed, nameIndex=0, gender=0,
                             safeZoneId=ToontownGlobals.ToontownCentral):
        """
        Create a new DistributedPetAI in the database and assign it to toon avId.

        The pet is written directly to the DB with its initial field values.
        Trait fields are intentionally omitted so that DistributedPetAI.announceGenerate
        re-derives them from traitSeed when the pet is first activated in the estate.
        """
        av = self.air.doId2do.get(avId)
        if not av:
            self.notify.warning('createNewPetFromSeed: avatar %s not found' % avId)
            return

        dclass = self.air.dclassesByName.get('DistributedPetAI')
        if not dclass:
            self.notify.warning('createNewPetFromSeed: DistributedPetAI dclass not found')
            return

        # Derive pet appearance, name seed and trait seed from the adoption seed.
        name, dna, traitSeed = PetUtil.getPetInfoFromSeed(seed, safeZoneId)

        # Override gender from the caller (petNum % numGenders in the clerk).
        dna = list(dna)
        dna[8] = gender
        head, ears, nose, tail, body, color, colorScale, eyes, gender_val = dna

        # Resolve the displayed name from the name-picker index.
        if nameIndex is not None and nameIndex >= 0:
            try:
                ng = PetNameGenerator.PetNameGenerator()
                indexedName = ng.getName(nameIndex)
                if indexedName:
                    name = indexedName
            except Exception:
                pass  # keep the seed-derived name on any failure

        # Trick aptitudes start at 0 for all 7 learnable tricks (BALK is excluded).
        emptyAptitudes = [0.0] * 7

        fields = {
            'setOwnerId':          [avId],
            'setPetName':          [name],
            'setTraitSeed':        [traitSeed],
            'setSafeZone':         [safeZoneId],
            'setHead':             [head],
            'setEars':             [ears],
            'setNose':             [nose],
            'setTail':             [tail],
            'setBodyTexture':      [body],
            'setColor':            [color],
            'setColorScale':       [colorScale],
            'setEyeColor':         [eyes],
            'setGender':           [gender_val],
            'setTrickAptitudes':   [emptyAptitudes],
            'setLastSeenTimestamp':[int(time.time())],
        }

        def handleCreated(petId):
            if not petId:
                self.notify.warning('createNewPetFromSeed: DB creation failed for '
                                    'toon %s' % avId)
                return

            self.notify.info('createNewPetFromSeed: created pet %s for toon %s'
                             % (petId, avId))

            # Link the pet to the toon.  If the toon is still online we can do
            # it in-memory + broadcast; otherwise fall back to a direct DB write.
            av2 = self.air.doId2do.get(avId)
            if av2:
                av2.b_setPetId(petId)
            else:
                toonDclass = self.air.dclassesByName.get('DistributedToonAI')
                if toonDclass:
                    self.air.dbInterface.updateObject(
                        self.air.dbId,
                        avId,
                        toonDclass,
                        {'setPetId': [petId]})

        self.air.dbInterface.createObject(
            self.air.dbId,
            dclass,
            fields,
            handleCreated)

    def deleteToonsPet(self, avId):
        """
        Permanently delete the toon's current pet from the database and
        clear the toon's petId field.
        """
        av = self.air.doId2do.get(avId)
        if not av:
            self.notify.warning('deleteToonsPet: avatar %s not found' % avId)
            return

        petId = av.getPetId()
        if not petId:
            self.notify.warning('deleteToonsPet: toon %s has no pet to delete' % avId)
            return

        self.notify.info('deleteToonsPet: deleting pet %s for toon %s' % (petId, avId))

        # Remove the pet from the state server if it is currently active.
        pet = self.air.doId2do.get(petId)
        if pet:
            pet.requestDelete()

        # Hard-delete the database record.
        dbo = DatabaseObject(self.air, petId)
        dbo.deleteObject()

        # Clear the owner's petId.
        av.b_setPetId(0)
