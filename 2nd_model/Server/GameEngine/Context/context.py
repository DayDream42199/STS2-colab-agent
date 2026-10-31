class PendingChoice:
    """A question a card has put to the player.

    `options` are card ids, so it is JSON-safe as it stands. `resolve` turns
    the id the player picked into the effects that carry the choice out.

    `can_stop` marks an "up to N" question (Purity, Neow's Fury): the player
    may answer STOP instead of an option, which picks nothing and asks nothing
    more. The game's selector allows zero picks there.
    """

    STOP = -1

    def __init__(self, ally, prompt, options, resolve, can_stop=False):
        self.ally = ally
        self.prompt = prompt
        self._options = options
        self.resolve = resolve
        self.can_stop = can_stop
        self._asked = None
        # The card play that asked, so what the answer does (a Block gained)
        # counts as part of it.
        self.play_id = None

    @property
    def options(self):
        """What the player may pick, worked out when the question is put.

        A card that asks several questions in a row queues them together, but
        each has to see the piles as the answer before it left them - hence a
        callable. Fixed once read, so the index the player sends still means
        what they were shown.
        """
        if self._asked is None:
            source = self._options
            self._asked = list(source() if callable(source) else source)
        return self._asked

    def to_dict(self):
        # Imported here: the card registry sits above this module.
        from ..Registry.card_registry import create_card
        from ..Cards._text import card_text
        return {
            "unit_id": self.ally.unit_id,
            "prompt": self.prompt,
            "options": [str(option) for option in self.options],
            # What each option does, so the player can choose knowingly.
            "option_text": [card_text(create_card(option)) for option in self.options],
            "can_stop": self.can_stop,
        }


class Context:
    def __init__(self, source, target=None, all_allies=None, all_enemies=None,
                 rng=None, payload=None, counters=None, x_amount=0, asks=None, rngs=None):
        self.source = source
        self.target = target
        self.all_allies = all_allies if all_allies is not None else []
        self.all_enemies = all_enemies if all_enemies is not None else []
        self.rng = rng
        # The fight's streams by purpose (rng_streams.py): a card making a
        # card draws from rngs.card_generation, one picking a random target
        # from rngs.targets, a draw that reshuffles from rngs.shuffle.
        self.rngs = rngs
        self.payload = payload if payload is not None else {}
        # Combat-wide tallies, as against the per-unit per-turn ones on
        # unit.turn_counters. A card counting every card exhausted in the
        # fight by anyone, which belongs to no unit in particular.
        self.counters = counters if counters is not None else {}
        # Energy actually spent on an X-cost card; zero for everything else.
        self.x_amount = x_amount
        # Questions raised while this action resolves. The list belongs to
        # Combat, which answers them once the action is finished.
        self.asks = asks if asks is not None else []
        # The copy being played, when this context is a card's. In the game
        # it sits in the play pile until it has resolved, so a question about
        # the pile it then lands in (Headbutt's discard) must not offer it -
        # here it is put away before the question is read.
        self.played = None
        # And which play of it this is: every play, a Replay's second one too,
        # is its own - the game's CardPlay. What it does carries the number.
        self.play_id = None

    @property
    def solo(self):
        """A fight with one player, where the co-op cards are never made at
        random (generatable_card_ids)."""
        return len(self.all_allies) == 1

    def ask(self, ally, prompt, options, resolve, can_stop=False):
        """Put a question to the player, to be answered after this action.

        Nothing happens now: `resolve(chosen)` returns the effects that carry
        the answer out, and Combat runs them once there is an answer. With no
        client attached the answer is picked at random, so a headless run plays
        on rather than stalling. `can_stop`: the player may pick nothing.
        """
        if not callable(options):
            options = list(options)
            if not options:
                return
        choice = PendingChoice(ally, prompt, options, resolve, can_stop)
        choice.play_id = self.play_id
        self.asks.append(choice)
