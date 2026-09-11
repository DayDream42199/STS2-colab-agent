class PendingChoice:
    """A question a card has put to the player.

    `options` are card ids, so it is JSON-safe as it stands. `resolve` turns
    the id the player picked into the effects that carry the choice out.
    """

    def __init__(self, ally, prompt, options, resolve):
        self.ally = ally
        self.prompt = prompt
        self._options = options
        self.resolve = resolve
        self._asked = None

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
        return {
            "unit_id": self.ally.unit_id,
            "prompt": self.prompt,
            "options": [str(option) for option in self.options],
        }


class Context:
    def __init__(self, source, target=None, all_allies=None, all_enemies=None,
                 rng=None, payload=None, counters=None, x_amount=0, asks=None):
        self.source = source
        self.target = target
        self.all_allies = all_allies if all_allies is not None else []
        self.all_enemies = all_enemies if all_enemies is not None else []
        self.rng = rng
        self.payload = payload if payload is not None else {}
        # Combat-wide tallies, as against the per-unit per-turn ones on
        # unit.turn_counters. Midnight counts every card exhausted in the
        # fight by anyone, which belongs to no unit in particular.
        self.counters = counters if counters is not None else {}
        # Energy actually spent on an X-cost card; zero for everything else.
        self.x_amount = x_amount
        # Questions raised while this action resolves. The list belongs to
        # Combat, which answers them once the action is finished.
        self.asks = asks if asks is not None else []

    def ask(self, ally, prompt, options, resolve):
        """Put a question to the player, to be answered after this action.

        Nothing happens now: `resolve(chosen)` returns the effects that carry
        the answer out, and Combat runs them once there is an answer. With no
        client attached the answer is picked at random, so a headless run plays
        on rather than stalling.
        """
        if not callable(options):
            options = list(options)
            if not options:
                return
        self.asks.append(PendingChoice(ally, prompt, options, resolve))
