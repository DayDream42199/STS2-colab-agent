from ._enemy import Enemy
from ._scripted import scaled_block
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.StatusEffects.vulnerable import Vulnerable

class Dummy1(Enemy):
    DEFAULT_MAX_HP = 20
    DEFAULT_HP_VARIANCE = 2

    ATTACK = 1
    BLOCK = 2
    VULNERABLE = 1

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._turn_count = 0

    def choose_intent(self, context=None):
        pattern = self._turn_count % 3
        self._turn_count += 1

        if pattern == 0:
            self.intent = {"type": "attack", "amount": self.ATTACK}
        elif pattern == 1:
            # What it will actually gain: Combat doubles an enemy's Block for
            # two players, so the intent has to say 4 there, not 2.
            self.intent = {"type": "block",
                           "amount": scaled_block(self.BLOCK, getattr(self, "block_scale", 1.0))}
        else:
            self.intent = {"type": "debuff_all", "status": "vulnerable", "amount": self.VULNERABLE}

    def get_effects(self, context):
        intent = self.intent

        # A test dummy does what its intent says, so a test can pin it to
        # "attack for 5". The one exception is Block: the intent shows it
        # already scaled for the party, and the resolver scales Block again
        # on the way in, so the printed number is what goes in.
        if intent["type"] == "attack":
            return [
                InstantDamage(source=self, target=ally, amount=intent["amount"])
                for ally in context.all_allies
                if ally.is_alive()
            ]
        if intent["type"] == "block":
            return [InstantBlock(source=self, target=self, amount=self.BLOCK)]
        if intent["type"] == "debuff_all":
            return [
                Vulnerable(source=self, target=ally, amount=intent["amount"])
                for ally in context.all_allies
            ]
