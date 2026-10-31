from ._scripted import ScriptedEnemy, Move, attack, buff
from ...Effects.InstantEffects.instant_heal import InstantHeal
from ...Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ...Effects.StatusEffects.steam_eruption import SteamEruption
from ...Effects.StatusEffects.weak import Weak


class WaterfallGiant(ScriptedEnemy):
    """Underdocks boss (WaterfallGiantBoss). Pressurize - 15 Steam Eruption -
    then Stomp 15 and 1 Weak, Ram 10, Siphon (heals 10 per player), Pressure
    Gun 20 (5 more each time), Pressure Up 13, and round from Stomp; every
    move after the first adds 3 Steam Eruption.

    Brought down while holding it, it does not die: it cannot be hurt any
    more, its next move is About to Blow (nothing), and the one after that
    Explode - its Steam Eruption as damage to every player - and then it is
    dead. The game's TriggerAboutToBlowState."""

    NAME = "Waterfall Giant"
    CATEGORY = "boss"
    DEFAULT_MAX_HP = 240
    DEFAULT_HP_VARIANCE = 0
    PRESSURIZE = 15
    STEAM = 3
    STOMP = 15
    STOMP_WEAK = 1
    RAM = 10
    SIPHON_HEAL = 10
    PRESSURE_GUN = 20
    PRESSURE_GUN_STEP = 5
    PRESSURE_UP = 13
    # The HP it is left with while about to blow: out of reach, as the game's.
    BLOWN_HP = 999999999

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        steam = (SteamEruption, self.STEAM)
        self._pressurize = buff("Pressurize", SteamEruption, self.PRESSURIZE)
        self._cycle = (
            attack("Stomp", self.STOMP, inflict=(Weak, self.STOMP_WEAK), gain=steam),
            attack("Ram", self.RAM, gain=steam),
            Move("Siphon", "heal", self._siphon_effects),
            None,                                   # Pressure Gun, built as it comes up
            attack("Pressure Up", self.PRESSURE_UP, gain=steam),
        )
        self.pressure_gun = self.PRESSURE_GUN
        self._about_to_blow = Move("About to Blow", "stun", self._about_to_blow_effects)
        # None, then "pending" once brought down, "exploding" once it has
        # made About to Blow.
        self.blowing = None
        self.eruption = 0

    def _siphon_effects(self, enemy, context):
        return [InstantHeal(source=enemy, target=enemy,
                            amount=self.SIPHON_HEAL * len(context.all_allies)),
                SteamEruption(source=enemy, target=enemy, amount=self.STEAM)]

    def _pressure_gun(self):
        gun = attack("Pressure Gun", self.pressure_gun, gain=(SteamEruption, self.STEAM))
        def effects(enemy, context):
            out = gun.effects(enemy, context)
            enemy.pressure_gun += self.PRESSURE_GUN_STEP
            return out
        return Move("Pressure Gun", Move.ATTACK, effects, damage=self.pressure_gun)

    def _about_to_blow_effects(self, enemy, context):
        steam = enemy.get_status("steam_eruption")
        enemy.eruption = steam.amount if steam is not None else 0
        enemy.remove_status("steam_eruption")
        enemy.blowing = "exploding"
        return []

    def _explode(self):
        blast = attack("Explode", self.eruption)
        def effects(enemy, context):
            # Then it dies (CreatureCmd.Kill), the pressure gone: for good.
            return blast.effects(enemy, context) + [
                InstantHpLoss(source=enemy, target=enemy, amount=enemy.max_hp)]
        return Move("Explode", Move.ATTACK, effects, damage=self.eruption)

    def on_death(self, context):
        if self.get_status("steam_eruption") is None:
            return []
        self.max_hp = self.current_hp = self.BLOWN_HP
        self.blowing = "pending"
        # Its move is About to Blow from now (SetMoveImmediate).
        self.move = self._about_to_blow
        self.skipped_move = False
        self.intent = {"type": "stun", "name": "About to Blow", "amount": 0, "hits": 1, "block": 0}
        return []

    def pick_move(self, turn):
        if self.blowing == "pending":
            return self._about_to_blow
        if self.blowing == "exploding":
            return self._explode()
        if turn == 0:
            return self._pressurize
        move = self._cycle[(turn - 1) % len(self._cycle)]
        return move if move is not None else self._pressure_gun()
