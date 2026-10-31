from ._scripted import ScriptedEnemy, attack, guard
from ...Effects.StatusEffects.artifact import Artifact, artifact_for
from ...Effects.StatusEffects.frail import Frail


class PunchConstruct(ScriptedEnemy):
    """Arrives with 1 Artifact (one more per extra player). Ready (10 Block),
    Fast Punch 5 x 2 and 1 Frail, Strong Punch 14, round and round."""

    NAME = "Punch Construct"
    DEFAULT_MAX_HP = 55
    DEFAULT_HP_VARIANCE = 0
    ARTIFACT = 1
    READY_BLOCK = 10
    FAST_PUNCH = 5
    FAST_PUNCH_HITS = 2
    STRONG_PUNCH = 14

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (guard("Ready", self.READY_BLOCK),
                       attack("Fast Punch", self.FAST_PUNCH, hits=self.FAST_PUNCH_HITS, inflict=(Frail, 1)),
                       attack("Strong Punch", self.STRONG_PUNCH))

    def on_combat_start(self, context):
        return [Artifact(source=self, target=self,
                         amount=artifact_for(len(context.all_allies), self.ARTIFACT))]

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
