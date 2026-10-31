from ._scripted import ScriptedEnemy, Move, Branch, attack, debuff
from ...Effects.InstantEffects.instant_summon import InstantSummon
from ...Effects.StatusEffects.frail import Frail


class TwoTailedRat(ScriptedEnemy):
    """Underdocks, three of them (TwoTailedRatsNormal). Scratch 8, Disease
    Bite 6, Screech (1 Frail) - the three open on three different ones - then
    at random, never the same twice running, Screech not again within three.

    Call for Backup brings in one more rat, at most once per rat and three
    times in the fight among them all, only after it has made two other
    moves, while there is room (five rats) and no other rat is about to.
    When it may, it is three times as likely as all the rest together."""

    NAME = "Two-Tailed Rat"
    HP_RANGE = (17, 21)
    SCRATCH = 8
    DISEASE_BITE = 6
    SCREECH_FRAIL = 1
    # Moves it makes before it may call (the game's TurnsUntilSummonable).
    MOVES_BEFORE_BACKUP = 2
    BACKUP_LIMIT = 3
    SLOTS = 5
    BACKUP_WEIGHT = 0.75
    # What each of the other three weighs while a call is possible.
    QUIET_WEIGHT = 1 / 12

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._scratch = self._counted(attack("Scratch", self.SCRATCH))
        self._disease_bite = self._counted(attack("Disease Bite", self.DISEASE_BITE))
        self._screech = self._counted(debuff("Screech", Frail, self.SCREECH_FRAIL))
        self._call = Move("Call for Backup", Move.SUMMON, self._call_effects)
        self.starter = None
        self.moves_before_backup = self.MOVES_BEFORE_BACKUP
        # Calls made so far in the fight, kept the same on every rat.
        self.backups_called = 0

    @staticmethod
    def _counted(move):
        """`move`, counting down to when a call is allowed as it is made."""
        def effects(enemy, context):
            enemy.moves_before_backup -= 1
            return move.effects(enemy, context)
        return Move(move.name, move.kind, effects, damage=move.damage, hits=move.hits)

    def _rats(self, context):
        return [e for e in context.all_enemies if isinstance(e, TwoTailedRat) and e.is_alive()]

    def on_combat_start(self, context):
        # Backup arrives knowing how many calls have been made.
        self.backups_called = max((r.backups_called for r in self._rats(context) if r is not self),
                                  default=0)
        return []

    def _call_effects(self, enemy, context):
        out = []
        if len([e for e in context.all_enemies if e.is_alive()]) < self.SLOTS:
            out.append(InstantSummon(source=enemy, type_ids=[TwoTailedRat.type_id()]))
        called = max(r.backups_called for r in self._rats(context)) + 1
        for rat in self._rats(context):
            rat.backups_called = called
        return out

    def _can_call(self, context):
        if self.moves_before_backup > 0 or self.backups_called >= self.BACKUP_LIMIT:
            return False
        if len([e for e in context.all_enemies if e.is_alive()]) >= self.SLOTS:
            return False
        return not any(r is not self and r.move is r._call for r in self._rats(context))

    def pick_move(self, turn):
        if turn == 0 and self.leader is None:
            if self.starter is None:
                # The encounter's one random start; each rat the next along.
                rats = [e for e in self.context.all_enemies if isinstance(e, TwoTailedRat)]
                first = self.choose_index(3)
                for i, rat in enumerate(rats):
                    if rat.starter is None:
                        rat.starter = (first + i) % 3
            return (self._scratch, self._disease_bite, self._screech)[self.starter]
        can = self._can_call(self.context)
        quiet = self.QUIET_WEIGHT if can else 1.0
        return self.choose([
            Branch(self._scratch, Branch.NO_REPEAT, weight=quiet),
            Branch(self._disease_bite, Branch.NO_REPEAT, weight=quiet),
            Branch(self._screech, Branch.NO_REPEAT, cooldown=3, weight=quiet),
            Branch(self._call, Branch.ONCE, weight=self.BACKUP_WEIGHT if can else 0.0),
        ])
