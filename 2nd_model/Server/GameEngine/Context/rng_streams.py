import random


class RngStreams:
    """One seeded random stream per purpose, as the game's RunRngSet keeps:
    drawing from one never moves another, so a reshuffle cannot change which
    move a slime picks, nor a Discovery the card a later Jackpot makes.

    Each stream is seeded from the fight's seed and its own name, as the game
    seeds seed + hash(name). random.Random seeds a string through SHA-512, so
    the streams come out the same in every process, whatever PYTHONHASHSEED.
    """

    # The game's RunRngType, the ones a fight uses: Shuffle (draw pile,
    # reshuffles, a card put in at random), CombatCardGeneration (cards made),
    # CombatCardSelection (cards picked at random), CombatTargets (random
    # targets), MonsterAi (moves) and Niche (monster HP). `answers` is ours: a
    # question answered at random for a player - headless, or after they left.
    NAMES = ("shuffle", "card_generation", "card_selection", "targets",
             "monster_ai", "niche", "answers")

    def __init__(self, seed):
        self.seed = seed
        for name in self.NAMES:
            setattr(self, name, random.Random("%s/%s" % (seed, name)))

    @classmethod
    def from_rng(cls, rng):
        """Streams for a caller that hands over one random.Random: seeded from
        it, so the same rng state still gives the same fight."""
        return cls(rng.getrandbits(64))
