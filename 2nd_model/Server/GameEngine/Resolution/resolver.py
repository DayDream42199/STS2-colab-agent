import copy

from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_add_card import InstantAddCard
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.InstantEffects.instant_draw_until import InstantDrawUntil
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard
from ..Effects.InstantEffects.instant_energy import InstantEnergy
from ..Effects.InstantEffects.instant_heal import InstantHeal
from ..Effects.InstantEffects.instant_max_hp_loss import InstantMaxHpLoss
from ..Effects.InstantEffects.instant_max_hp_gain import InstantMaxHpGain
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.InstantEffects.instant_upgrade_card import InstantUpgradeCard
from ..Effects.InstantEffects.instant_boost_card import InstantBoostCard
from ..Effects.InstantEffects.instant_grant_replay import InstantGrantReplay
from ..Effects.InstantEffects.instant_raise_cost import InstantRaiseCost
from ..Effects.StatusEffects._status_effect import StatusEffect
from ..Cards._card_ref import new_ref, take


class Resolver:
    @staticmethod
    def resolve(effect):
        if isinstance(effect, InstantDamage):
            return Resolver._resolve_instant_damage(effect)
        if isinstance(effect, InstantBlock):
            return Resolver._resolve_instant_block(effect)
        if isinstance(effect, InstantAddCard):
            return Resolver._resolve_instant_add_card(effect)
        if isinstance(effect, InstantMoveCard):
            return Resolver._resolve_instant_move_card(effect)
        if isinstance(effect, InstantExhaust):
            return Resolver._resolve_instant_exhaust(effect)
        if isinstance(effect, InstantDraw):
            return Resolver._resolve_instant_draw(effect)
        if isinstance(effect, InstantDrawUntil):
            return Resolver._resolve_instant_draw_until(effect)
        if isinstance(effect, InstantHeal):
            return Resolver._resolve_instant_heal(effect)
        if isinstance(effect, InstantMaxHpLoss):
            return Resolver._resolve_instant_max_hp_loss(effect)
        if isinstance(effect, InstantMaxHpGain):
            return Resolver._resolve_instant_max_hp_gain(effect)
        if isinstance(effect, InstantEnergy):
            return Resolver._resolve_instant_energy(effect)
        if isinstance(effect, InstantHpLoss):
            return Resolver._resolve_instant_hp_loss(effect)
        if isinstance(effect, InstantUpgradeCard):
            return Resolver._resolve_instant_upgrade_card(effect)
        if isinstance(effect, InstantBoostCard):
            return Resolver._resolve_instant_boost_card(effect)
        if isinstance(effect, InstantGrantReplay):
            return Resolver._resolve_instant_grant_replay(effect)
        if isinstance(effect, InstantRaiseCost):
            return Resolver._resolve_instant_raise_cost(effect)
        if isinstance(effect, StatusEffect):
            return Resolver._resolve_status(effect)
        raise NotImplementedError(
            f"No resolution handler for effect type {type(effect).__name__}"
        )

    @staticmethod
    def _resolve_instant_damage(effect):
        target = effect.target
        amount = effect.amount

        if effect.is_attack:
            for status in Resolver._ordered(effect.source):
                amount = status.modify_outgoing_damage(amount, target)

        for status in Resolver._ordered(target):
            amount = status.modify_incoming_damage(amount, effect.source)

        amount = max(0, int(amount))
        was_alive = target.is_alive()
        dealt = target.take_damage(amount)

        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            # `amount` is what got through Block; `total` is the whole swing,
            # which is what "damage dealt" means to Fisticuffs and Omnislice.
            "amount": dealt,
            "total": amount,
            "killed": was_alive and not target.is_alive(),
            "target_hp": target.current_hp,
            "target_block": target.block,
        }

    @staticmethod
    def _ordered(unit):
        return sorted(unit.statuses.values(), key=lambda s: s.DAMAGE_ORDER)

    @staticmethod
    def _resolve_instant_add_card(effect):
        pile = getattr(effect.target, effect.pile)
        # A copy each, not the same one N times: they are separate cards from
        # here on. Handed a ref, the copies inherit its state - Anger+ adds
        # Anger+.
        added = [new_ref(effect.card_id) for _ in range(effect.amount)]
        if effect.pile == InstantAddCard.DRAW and effect.rng is not None:
            # Each copy lands at its own random depth. Shuffling the whole pile
            # instead would also undo any order the player set up - Headbutt
            # puts a card on top, and that has to stay on top.
            for card_id in added:
                pile.insert(effect.rng.randint(0, len(pile)), card_id)
        else:
            pile.extend(added)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.target.unit_id,
            "card_id": effect.card_id,
            "pile": effect.pile,
            "amount": effect.amount,
        }

    @staticmethod
    def _resolve_instant_move_card(effect):
        target = effect.target
        # GONE as the source means the cards are in no pile at all: held out
        # of play by a status, on their way back (Bolas).
        held = effect.from_pile == InstantMoveCard.GONE
        source_pile = None if held else getattr(target, effect.from_pile)
        gone = effect.to_pile == InstantMoveCard.GONE
        dest_pile = None if gone else getattr(target, effect.to_pile)
        moved = []
        for card_id in effect.card_ids:
            if not held and not take(source_pile, card_id):
                continue
            if not gone:
                if effect.to_pile == InstantMoveCard.DRAW and effect.to_top:
                    dest_pile.append(card_id)   # drawn from the end
                else:
                    dest_pile.insert(0, card_id)
            moved.append(card_id)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "card_ids": moved,
            "amount": len(moved),
            "from_pile": effect.from_pile,
            "to_pile": effect.to_pile,
        }

    @staticmethod
    def _resolve_instant_exhaust(effect):
        target = effect.target
        moved = []
        for card_id in effect.card_ids:
            if take(target.hand, card_id):
                target.exhaust_pile.append(card_id)
                moved.append(card_id)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "card_ids": moved,
            "amount": len(moved),
            "exhaust_pile_count": len(target.exhaust_pile),
        }

    @staticmethod
    def _resolve_instant_upgrade_card(effect):
        upgraded = []
        for card_ref in effect.card_refs:
            # A bare id is a copy nobody can tell apart, so there is nothing
            # to mark - it stays un-upgraded rather than upgrading them all.
            if getattr(card_ref, "upgraded", None) is False:
                card_ref.upgraded = True
                upgraded.append(card_ref)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.target.unit_id,
            "card_ids": upgraded,
            "amount": len(upgraded),
        }

    @staticmethod
    def _resolve_instant_boost_card(effect):
        boosted = []
        for card_ref in effect.card_refs:
            if hasattr(card_ref, "bonus_damage"):
                card_ref.bonus_damage += effect.amount
                boosted.append(card_ref)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.target.unit_id,
            "card_ids": boosted,
            "amount": effect.amount,
        }

    @staticmethod
    def _resolve_instant_grant_replay(effect):
        granted = []
        for card_ref in effect.card_refs:
            if hasattr(card_ref, "replay"):
                card_ref.replay += effect.amount
                granted.append(card_ref)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.target.unit_id,
            "card_ids": granted,
            "amount": effect.amount,
        }

    @staticmethod
    def _resolve_instant_raise_cost(effect):
        raised = []
        for card_ref in effect.card_refs:
            if hasattr(card_ref, "cost_bump"):
                card_ref.cost_bump += effect.amount
                raised.append(card_ref)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.target.unit_id,
            "card_ids": raised,
            "amount": effect.amount,
        }

    @staticmethod
    def _resolve_instant_draw(effect):
        amount = effect.amount
        for status in Resolver._ordered(effect.target):
            amount = status.modify_cards_drawn(amount)
        drawn = effect.target.draw(max(0, int(amount)), effect.rng)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.target.unit_id,
            "amount": len(drawn),
            # Which cards, not just how many: Hellraiser and Void react to the
            # identity of what was drawn, not the count.
            "card_ids": drawn,
            "hand_size": len(effect.target.hand),
        }

    @staticmethod
    def _resolve_instant_draw_until(effect):
        from ..Registry.card_registry import create_card

        target = effect.target
        drawn = []
        # One at a time, because whether to keep going depends on what came up.
        # The stopping card is kept - Pillage draws THROUGH to a non-Attack.
        while True:
            if any(s.modify_cards_drawn(1) <= 0 for s in Resolver._ordered(target)):
                break
            got = target.draw(1, effect.rng)
            if not got:
                break
            drawn.append(got[0])
            if create_card(got[0]).card_type is not effect.while_type:
                break
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": len(drawn),
            "card_ids": drawn,
            "hand_size": len(target.hand),
        }

    @staticmethod
    def _resolve_instant_heal(effect):
        target = effect.target
        before = target.current_hp
        target.heal(effect.amount)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": target.current_hp - before,
            "target_hp": target.current_hp,
        }

    @staticmethod
    def _resolve_instant_max_hp_loss(effect):
        target = effect.target
        target.max_hp = max(1, target.max_hp - effect.amount)
        # Current HP cannot sit above the new maximum.
        target.current_hp = min(target.current_hp, target.max_hp)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": effect.amount,
            "max_hp": target.max_hp,
            "target_hp": target.current_hp,
        }

    @staticmethod
    def _resolve_instant_max_hp_gain(effect):
        target = effect.target
        target.max_hp += max(0, effect.amount)
        target.current_hp += max(0, effect.amount)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": max(0, effect.amount),
            "max_hp": target.max_hp,
            "target_hp": target.current_hp,
        }

    @staticmethod
    def _resolve_instant_energy(effect):
        if effect.amount >= 0:
            effect.target.gain_energy(effect.amount)
        else:
            # Void takes energy away. gain_energy ignores anything <= 0, and
            # spend_energy raises when you cannot afford it, so neither is the
            # right door for a loss that should just floor at zero.
            effect.target.energy = max(0, effect.target.energy + effect.amount)
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
        amount = effect.amount
        for status in Resolver._ordered(target):
            amount = status.modify_block_gained(amount)
        amount = max(0, int(amount))
        target.add_block(amount)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": amount,
            "target_block": target.block,
        }

    @staticmethod
    def _resolve_status(effect):
        target = effect.target
        if not target.is_alive():
            return None
        target.apply_status(copy.copy(effect))
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": target.unit_id,
            "amount": target.statuses[effect.effect_id].amount,
        }
