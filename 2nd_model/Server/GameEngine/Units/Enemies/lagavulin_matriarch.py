from ._scripted import ScriptedEnemy, Move, attack, players
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.StatusEffects.asleep import Asleep
from ...Effects.StatusEffects.dexterity import Dexterity
from ...Effects.StatusEffects.plating import Plating, plating_for
from ...Effects.StatusEffects.strength import Strength
from ...Effects.StatusEffects.stun import Stun


class LagavulinMatriarch(ScriptedEnemy):
    """Underdocks boss (LagavulinMatriarchBoss). Arrives asleep for three
    turns behind 12 Plating (and that much Block). Hit through its Block and
    it wakes: the Plating goes, it is stunned a turn, then Slash. Awake it
    goes Slash 19, Disembowel 9 x 2, Slash 12 and 12 Block, Soul Siphon - 2
    Strength and 2 Dexterity off every player, 2 Strength for itself - and
    round again."""

    NAME = "Lagavulin Matriarch"
    CATEGORY = "boss"
    DEFAULT_MAX_HP = 222
    DEFAULT_HP_VARIANCE = 0
    PLATING = 12
    ASLEEP = 3
    SLASH = 19
    SLASH2 = 12
    SLASH2_BLOCK = 12
    DISEMBOWEL = 9
    DISEMBOWEL_HITS = 2
    SOUL_SIPHON = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._sleep = Move("Sleep", Move.SLEEP, lambda enemy, context: [])
        self._slash = attack("Slash", self.SLASH)
        self._disembowel = attack("Disembowel", self.DISEMBOWEL, hits=self.DISEMBOWEL_HITS)
        self._slash2 = attack("Slash", self.SLASH2, block=self.SLASH2_BLOCK)
        self._soul_siphon = Move("Soul Siphon", Move.DEBUFF, self._siphon_effects)
        self._after = {self._slash: self._disembowel, self._disembowel: self._slash2,
                       self._slash2: self._soul_siphon, self._soul_siphon: self._slash}

    def on_combat_start(self, context):
        plating = plating_for(len(context.all_allies), self.PLATING)
        # Asleep first: it has to be heard before the Plating (see Asleep).
        return [Asleep(source=self, target=self, amount=self.ASLEEP),
                Plating(source=self, target=self, amount=plating),
                InstantBlock(source=self, target=self, amount=plating, powered=False, card=False)]

    def _siphon_effects(self, enemy, context):
        out = []
        for p in players(context):
            out.append(Strength(source=enemy, target=p, amount=-self.SOUL_SIPHON))
            out.append(Dexterity(source=enemy, target=p, amount=-self.SOUL_SIPHON))
        out.append(Strength(source=enemy, target=enemy, amount=self.SOUL_SIPHON))
        return out

    def woken(self):
        """Hit awake: stunned a turn, then Slash (CreatureCmd.Stun with
        SLASH_MOVE to follow)."""
        self.apply_status(Stun(source=self, target=self, amount=1))
        self.move = self._slash

    def pick_move(self, turn):
        if self.get_status("asleep") is not None:
            return self._sleep
        return self._after.get(self.move, self._slash)
