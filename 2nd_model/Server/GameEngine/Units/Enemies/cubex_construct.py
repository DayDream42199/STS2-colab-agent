from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.StatusEffects.strength import Strength
from ...Effects.StatusEffects.artifact import Artifact, artifact_for


class CubexConstruct(ScriptedEnemy):
    """Act 1. Arrives behind 13 Block with 1 Artifact (one more per extra
    player). Charges Up (+2 Strength) once, then Repeater Blast (7, +2
    Strength), Repeater Blast again, Expel Blast (5 x 2), and round again.
    It only gets stronger."""

    NAME = "Cubex Construct"
    DEFAULT_MAX_HP = 65
    DEFAULT_HP_VARIANCE = 0

    OPENING_BLOCK = 13
    ARTIFACT = 1
    CHARGE = 2
    REPEATER = 7
    REPEATER_STRENGTH = 2
    EXPEL = 5
    EXPEL_HITS = 2

    def on_combat_start(self, context):
        return [InstantBlock(source=self, target=self, amount=self.OPENING_BLOCK),
                Artifact(source=self, target=self,
                         amount=artifact_for(len(context.all_allies), self.ARTIFACT))]

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._opener = buff("Charge Up", Strength, self.CHARGE)
        blast = attack("Repeater Blast", self.REPEATER, gain=(Strength, self.REPEATER_STRENGTH))
        self._cycle = (blast, blast,
                       attack("Expel Blast", self.EXPEL, hits=self.EXPEL_HITS))

    def pick_move(self, turn):
        if turn == 0:
            return self._opener
        return self._cycle[(turn - 1) % len(self._cycle)]
