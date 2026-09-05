from ._enemy import Enemy
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.StatusEffects.vulnerable import Vulnerable

class Dummy1(Enemy):
    DEFAULT_MAX_HP = 20
    DEFAULT_HP_VARIANCE = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._turn_count = 0

    def choose_intent(self, context=None):
        pattern = self._turn_count % 3
        self._turn_count += 1

        if pattern == 0:
            self.intent = {"type": "attack", "amount": 1}
        elif pattern == 1:
            self.intent = {"type": "block", "amount": 2}
        else:
            self.intent = {"type": "debuff_all", "status": "vulnerable", "amount": 1}

    def get_effects(self, context):
        intent = self.intent

        if intent["type"] == "attack":
            return [InstantDamage(source=self, target=context.target, amount=intent["amount"])]
        if intent["type"] == "block":
            return [InstantBlock(source=self, target=self, amount=intent["amount"])]
        if intent["type"] == "debuff_all":
            return [
                Vulnerable(source=self, target=ally, amount=intent["amount"])
                for ally in context.all_allies
            ]