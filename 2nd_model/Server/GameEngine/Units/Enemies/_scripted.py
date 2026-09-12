from ._enemy import Enemy


class Move:
    """One thing an enemy can do on its turn.

    `effects(enemy, context)` builds what it does; `kind`, `damage` and `hits`
    are what the client is shown as the intent. `damage` is per hit, before
    the enemy's own Strength.
    """

    ATTACK = "attack"
    BLOCK = "block"
    BUFF = "buff"
    DEBUFF = "debuff"

    def __init__(self, name, kind, effects, damage=0, hits=1, targeted=None):
        self.name = name
        self.kind = kind
        self.effects = effects
        self.damage = damage
        self.hits = hits
        # Whether one player is picked for it. Attacks always; a debuff aimed
        # at one player (Aeonglass's Intensity) opts in.
        self.targeted = (kind == Move.ATTACK) if targeted is None else targeted


class ScriptedEnemy(Enemy):
    """An enemy that follows a move list: `pick_move(turn)` says which.

    A single-target Attack picks its victim when the intent is chosen, not when
    it lands, so the client can show who is about to be hit. Combat honours
    that pick if the ally is still standing (`_enemy_target`).
    """

    # Base HP is the single-player number; Combat scales it for co-op, and
    # sets block_scale, which the resolver applies to Block this enemy gains.
    CATEGORY = "normal"

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self.turn = 0
        self.move = None
        self.target_id = None
        self.block_scale = 1.0

    def pick_move(self, turn):
        raise NotImplementedError

    def choose_intent(self, context=None):
        self.move = self.pick_move(self.turn)
        self.turn += 1
        self.target_id = None
        if self.move.targeted and context is not None:
            living = [a for a in context.all_allies if a.is_alive()]
            if living:
                self.target_id = context.rng.choice(living).unit_id
        self.intent = {
            "type": self.move.kind,
            "name": self.move.name,
            "amount": self.move.damage,
            "hits": self.move.hits,
            "target": self.target_id,
        }

    def get_effects(self, context):
        return self.move.effects(self, context)


# Real STS2 co-op scaling: enemy HP is multiplied by the player count and an
# act factor. Single player is unscaled.
ACT_SCALING = {"act1": 1.1, "act2": 1.2, "act3": 1.2, "act3boss": 1.3}


def hp_scale(player_count, act="act1"):
    if player_count <= 1:
        return 1.0
    return player_count * ACT_SCALING.get(act, 1.0)


def block_scale(player_count, act="act1"):
    # Block scales harder than HP for two players: flat x2, no act factor.
    if player_count <= 1:
        return 1.0
    if player_count == 2:
        return 2.0
    return player_count * ACT_SCALING.get(act, 1.0)
