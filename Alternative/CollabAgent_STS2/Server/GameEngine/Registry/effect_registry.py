from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.InstantEffects.instant_energy import InstantEnergy
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.StatusEffects.vulnerable import Vulnerable
from ..Effects.StatusEffects.weak import Weak
from ..Effects.StatusEffects.strength import Strength
from ..Effects.StatusEffects.strength_this_turn import StrengthThisTurn

_EFFECT_CLASSES = {}


def register_effect(effect_id, effect_class):
    _EFFECT_CLASSES[effect_id] = effect_class
    return effect_class


def create_effect(effect_id, **kwargs):
    """Generic factory: works as long as the effect's __init__ accepts
    (source, target, amount) — true for every effect so far. An effect with a
    different shape (e.g. no target) will need its own construction path
    rather than this one."""
    effect_class = _EFFECT_CLASSES.get(effect_id)
    if effect_class is None:
        raise KeyError(f"Unknown effect id: {effect_id}")
    return effect_class(**kwargs)


def known_effect_ids():
    return sorted(_EFFECT_CLASSES)


register_effect("instant_damage", InstantDamage)
register_effect("instant_block", InstantBlock)
register_effect("vulnerable", Vulnerable)
register_effect("weak", Weak)
register_effect("strength", Strength)
register_effect("strength_this_turn", StrengthThisTurn)
register_effect("instant_hp_loss", InstantHpLoss)
register_effect("instant_energy", InstantEnergy)
# InstantDraw is deliberately absent: create_effect's (source, target, amount)
# signature cannot supply the rng it needs.
