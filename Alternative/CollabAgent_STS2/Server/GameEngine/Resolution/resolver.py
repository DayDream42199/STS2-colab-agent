import copy

from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.InstantEffects.instant_energy import InstantEnergy
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.StatusEffects._status_effect import StatusEffect


class Resolver:
    """Applies one already-built Effect to real Unit state and returns a
    JSON-safe dict describing what happened, for broadcasting to clients."""

    @staticmethod
    def resolve(effect):
        if isinstance(effect, InstantDamage):
            return Resolver._resolve_instant_damage(effect)
        if isinstance(effect, InstantBlock):
            return Resolver._resolve_instant_block(effect)
        if isinstance(effect, InstantDraw):
            return Resolver._resolve_instant_draw(effect)
        if isinstance(effect, InstantEnergy):
            return Resolver._resolve_instant_energy(effect)
        if isinstance(effect, InstantHpLoss):
            return Resolver._resolve_instant_hp_loss(effect)
        # Any StatusEffect subclass (Vulnerable, and whatever comes after it)
        # is handled the same generic way — new statuses need no new branch
        # here unless they do something beyond "attach to the target".
        if isinstance(effect, StatusEffect):
            return Resolver._resolve_status(effect)
        raise NotImplementedError(
            f"No resolution handler for effect type {type(effect).__name__}"
        )

    @staticmethod
    def _resolve_instant_damage(effect):
        target = effect.target
        amount = effect.amount

        # Outgoing modifiers from the source's own statuses (Strength, Weak).
        for status in Resolver._ordered(effect.source):
            amount = status.modify_outgoing_damage(amount)

        # Incoming modifiers from the target's statuses (Vulnerable).
        for status in Resolver._ordered(target):
            amount = status.modify_incoming_damage(amount)

        # Slay the Spire floors after multipliers rather than rounding:
        # 5 damage into Vulnerable is 7, not 8.
        amount = max(0, int(amount))
        dealt = target.take_damage(amount)

        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": dealt,
            "target_hp": target.current_hp,
            "target_block": target.block,
        }

    @staticmethod
    def _ordered(unit):
        """Statuses sorted so additive modifiers apply before multiplicative
        ones, rather than in whatever order they happened to be applied."""
        return sorted(unit.statuses.values(), key=lambda s: s.DAMAGE_ORDER)

    @staticmethod
    def _resolve_instant_draw(effect):
        drawn = effect.target.draw(effect.amount, effect.rng)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.target.unit_id,
            "amount": len(drawn),
            "hand_size": len(effect.target.hand),
        }

    @staticmethod
    def _resolve_instant_energy(effect):
        effect.target.gain_energy(effect.amount)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.target.unit_id,
            "amount": effect.amount,
            "energy": effect.target.energy,
        }

    @staticmethod
    def _resolve_instant_hp_loss(effect):
        target = effect.target
        lost = target.lose_hp(effect.amount)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": lost,
            "target_hp": target.current_hp,
        }

    @staticmethod
    def _resolve_instant_block(effect):
        target = effect.target
        target.add_block(effect.amount)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": effect.amount,
            "target_block": target.block,
        }

    @staticmethod
    def _resolve_status(effect):
        target = effect.target
        # A dead unit cannot be debuffed. Bash whose damage kills its target
        # should not leave Vulnerable sitting on the corpse, where nothing
        # ticks it down again. None means "no-op"; the caller drops it.
        if not target.is_alive():
            return None
        # Unit.apply_status stores the instance it is handed, so a single
        # effect applied to several targets would alias between them --
        # ticking one would tick the rest. Give each target its own copy.
        target.apply_status(copy.copy(effect))
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": target.statuses[effect.effect_id].amount,
        }
