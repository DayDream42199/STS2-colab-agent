"""CombatEngine: runs a full battle between 1-4 Players (coop, per confirmed STS2 multiplayer..."""

from typing import List, NamedTuple, Optional
from .entities import Player
from .enemies import Enemy, scale_enemy_for_players
from .cards import Card, CardType, TargetMode
from .statuses import StatusType


class _HandContext(NamedTuple):
    """The facts why_not_playable needs that describe the HAND AS A WHOLE rather than the card in front..."""
    play_cap: Optional[int]
    first_enthralled: Optional[Card]


class CombatEngine:
    def __init__(self, players: List[Player], enemies: List[Enemy], seed: Optional[int] = None,
                 act: str = "act1", scale_enemies: bool = True):
        """act: "act1" | "act2" | "act3" -- used for multiplayer enemy HP scaling (see..."""
        assert 1 <= len(players) <= 4, "STS2 multiplayer supports 1 (solo) to 4 players"
        self.players = players
        self.enemies = enemies
        self.act = act
        self.log: List[str] = []
        self.turn_number = 0
        self.seed = seed
        self._combat_over = False
        self._victory = False
        self.total_exhausted_this_combat = 0
        self.pending_eruptions: List = []
        self.choice_resolver = None

        for i, p in enumerate(self.players):
            p.start_combat(seed=(seed + i if seed is not None else None))
            p.engine = self
            self._apply_innate(p)
        for i, e in enumerate(self.enemies):
            if scale_enemies:
                scale_enemy_for_players(e, len(self.players), act)
            e.start_combat(seed=(seed + 100 + i if seed is not None else None))

    MAX_ENEMIES = 12

    def summon_enemy(self, new_enemies, summoner: Optional[Enemy] = None,
                      stunned: bool = False) -> List[Enemy]:
        """Bring one or more enemies into an ongoing fight."""
        if isinstance(new_enemies, Enemy):
            new_enemies = [new_enemies]
        spawned = []
        for e in new_enemies:
            if len(self.enemies) >= self.MAX_ENEMIES:
                self.log.append(f"summon blocked: enemy cap ({self.MAX_ENEMIES}) reached")
                break
            scale_enemy_for_players(e, len(self.players), self.act)
            e.start_combat(seed=(self.seed + 500 + len(self.enemies)
                                  if self.seed is not None else None))
            if stunned:
                e.stunned_turns = 1
            if summoner is not None and e.leader is None:
                e.leader = summoner
            self.enemies.append(e)
            spawned.append(e)
            self.log.append(
                f"{summoner.name if summoner else 'The fight'} summons {e.name}")
        return spawned

    def handle_enemy_death(self, enemy: Enemy):
        """Fire an enemy's on_death effect, then clear out any minions whose leader just died."""
        if enemy.death_resolved:
            return
        enemy.death_resolved = True
        for e in self.enemies:
            if e.alive and e.is_minion and e.leader is enemy:
                e.alive = False
                e.death_resolved = True
                self.log.append(f"{e.name} abandons the fight without its leader")
        steam = enemy.get_status(StatusType.STEAM_ERUPTION)
        if steam > 0:
            self.pending_eruptions.append([steam, 1])
            self.log.append(f"{enemy.name} will erupt for {steam} at the end of your next turn")
        for e in self.enemies:
            if not (e.alive and e is not enemy):
                continue
            rav = e.get_status(StatusType.RAVENOUS)
            if rav:
                e.add_status(StatusType.STRENGTH, rav)
                e.stunned_turns = max(e.stunned_turns, 1)
                self.log.append(f"{e.name} devours {enemy.name}: +{rav} Strength, stunned")
        if enemy.on_death is not None:
            enemy.on_death(self, enemy)

    @staticmethod
    def _apply_innate(player: Player):
        """Innate: "start each combat with this card in your Hand."""
        innate = [c for c in player.draw_pile if c.is_innate()]
        if not innate:
            return
        for c in innate:
            player.draw_pile.remove(c)
        player.draw_pile.extend(innate)

    def enemies_alive(self) -> List[Enemy]:
        return [e for e in self.enemies if e.alive]

    def players_alive(self) -> List[Player]:
        return [p for p in self.players if p.alive]

    def other_player(self, player: Player) -> Optional[Player]:
        """First other living player."""
        for p in self.players:
            if p is not player and p.alive:
                return p
        return None

    def other_players(self, player: Player) -> List[Player]:
        """All other living players -- use this for anything that should genuinely consider every teammate..."""
        return [p for p in self.players if p is not player and p.alive]

    def pick_enemy_attack_target(self) -> Player:
        """Very simple enemy targeting: random among living players."""
        alive = self.players_alive()
        if not alive:
            return self.players[0]
        picked = self.enemies[0].rng.choice(alive) if self.enemies else alive[0]
        for p in alive:
            if p is not picked and picked in p.redirect_attacks_from:
                self.log.append(f"{p.name} intercepts the attack aimed at {picked.name}")
                return p
        return picked

    def random_alive_enemy(self, rng_owner: Player) -> Optional[Enemy]:
        """Random living enemy, for relics/cards that hit 'random' (e.g."""
        alive = self.enemies_alive()
        if not alive:
            return None
        return rng_owner.rng.choice(alive)

    def draw_extra(self, player: Player, n: int):
        player.draw_cards(n, self.log)

    def has_enemy_category(self, category: str) -> bool:
        """Whether this fight contains an enemy of the given category ("elite"/"boss")."""
        return any(e.category == category for e in self.enemies)

    def start_player_turn(self):
        self.turn_number += 1
        for e in self.enemies:
            e.attacked_by_this_turn = []
            e.knockdown = None
        self.log.append(f"--- Turn {self.turn_number}: Player phase ---")
        for p in self.players:
            if p.alive:
                p.start_turn(self.log)
                p.acted_this_turn = False
                if p.pending_relic_block:
                    gained = p.gain_block(p.pending_relic_block, from_card=False)
                    self.log.append(f"{p.name} gains {gained} block (relic, promised last turn)")
                    p.pending_relic_block = 0
                if p.pending_relic_draw:
                    self.draw_extra(p, p.pending_relic_draw)
                    self.log.append(f"{p.name} draws {p.pending_relic_draw} additional cards (relic, promised last turn)")
                    p.pending_relic_draw = 0
                if p.pending_relic_energy:
                    p.energy += p.pending_relic_energy
                    self.log.append(f"{p.name} gains {p.pending_relic_energy} energy (relic, promised last turn)")
                    p.pending_relic_energy = 0
                for relic in p.relics:
                    if relic.on_turn_start:
                        relic.on_turn_start(self, p, self.turn_number)
                p.fire_hook("turn_start", turn_number=self.turn_number)
                self._tick_sandpit(p)

    def _tick_sandpit(self, player: Player):
        """Sandpit (The Insatiable): "In X turns, you will be eaten and die." A hard countdown on the..."""
        stacks = player.get_status(StatusType.SANDPIT)
        if stacks <= 0:
            return
        player.add_status(StatusType.SANDPIT, -1)
        remaining = player.get_status(StatusType.SANDPIT)
        if remaining <= 0:
            player.hp = 0
            player.alive = False
            self.log.append(f"{player.name} is swallowed by the sandpit and DIES")
        else:
            self.log.append(f"{player.name} sinks: {remaining} turn(s) before being eaten")

    def request_choice(self, player: Player, options, prompt: str = "",
                        kind: str = "card"):
        """The single funnel for every "choose a card" the rules describe."""
        options = list(options)
        if not options:
            return None
        if len(options) == 1:
            return options[0]
        if self.choice_resolver is None:
            return player.rng.choice(options)
        chosen = self.choice_resolver(self, player, options, prompt, kind)
        if any(chosen is o for o in options):
            return chosen
        self.log.append(f"choice resolver returned an option that was not offered ({prompt})")
        return options[0]

    def _hand_context(self, player: Player) -> _HandContext:
        """Answer the hand-wide half of why_not_playable's rules, in ONE pass over the hand."""
        cap = None
        first_enthralled = None
        caps = self.PLAY_CAP_CARDS
        for c in player.hand:
            name = c.name
            limit = caps.get(name)
            if limit is not None and (cap is None or limit < cap):
                cap = limit
            if first_enthralled is None and name == "Enthralled":
                first_enthralled = c
        return _HandContext(play_cap=cap, first_enthralled=first_enthralled)

    def why_not_playable(self, player: Player, card: Card,
                          ctx: Optional[_HandContext] = None) -> Optional[str]:
        """THE single source of truth for "may this card be played from hand"."""
        if self._combat_over:
            return "combat is over"
        if ctx is None:
            ctx = self._hand_context(player)
        if card not in player.hand:
            return f"{card.name} not in {player.name}'s hand"
        if card.is_unplayable():
            return f"{card.name} is unplayable"
        if player.get_status(StatusType.RINGING) > 0 and player.cards_played_this_turn >= 1:
            return f"{player.name} has Ringing and has already played a card this turn"
        if (card.card_type == CardType.SKILL
                and player.get_status(StatusType.SMOGGY) > 0
                and player.skills_played_this_turn >= 1):
            return f"{player.name} has Smoggy and has already played a Skill this turn"
        if card.bound and player.bound_played_this_turn >= 1:
            return f"{card.name} is Bound and one Bound card has already been played"
        cap = ctx.play_cap
        if cap is not None and player.cards_played_this_turn >= cap:
            return f"{player.name} cannot play more than {cap} cards this turn"
        if ctx.first_enthralled is not None and card is not ctx.first_enthralled:
            return f"{player.name} must play Enthralled first"
        if card.playable_if is not None and not card.playable_if(card, player):
            return f"{card.name}'s play condition is not met"
        if card.target == TargetMode.ALLY and not self.other_players(player):
            return f"{card.name} needs an ally and there is none"
        cost = card.current_cost(player)
        if cost != "X" and player.energy < cost:
            return f"{player.name} lacks energy for {card.name}"
        return None

    def play_card(self, player: Player, card: Card, target: Optional[Enemy] = None,
                   ally_target: Optional[Player] = None) -> bool:
        """Returns True if the card was successfully played."""
        reason = self.why_not_playable(player, card)
        if reason is not None:
            if not self._combat_over:
                self.log.append(f"ILLEGAL: {reason}")
            return False

        card_cost = card.current_cost(player)
        is_x_cost = (card_cost == "X")
        actual_cost = player.energy if is_x_cost else card_cost

        resolved_target = None
        if card.target == TargetMode.SINGLE_ENEMY:
            if target is None or not target.alive:
                candidates = self.enemies_alive()
                if not candidates:
                    return False
                target = candidates[0]
            resolved_target = target
        elif card.target == TargetMode.ALLY:
            resolved_target = ally_target or self.other_player(player)
        elif card.target == TargetMode.ALL_ENEMIES:
            resolved_target = None
        elif card.target in (TargetMode.SELF, TargetMode.SELF_OR_ALLY):
            resolved_target = ally_target if (card.target == TargetMode.SELF_OR_ALLY and ally_target) else player

        if card.card_type == CardType.ATTACK and player.next_attack_free:
            player.next_attack_free = False

        player.energy -= actual_cost
        player.hand.remove(card)
        cost_label = f"X={actual_cost}" if is_x_cost else str(actual_cost)
        self.log.append(f"{player.name} plays {card.name} (cost {cost_label})")
        player.cards_played_this_turn += 1
        if card.bound:
            player.bound_played_this_turn += 1
        tender = player.get_status(StatusType.TENDER)
        if tender:
            player.add_status(StatusType.STRENGTH_LOSS_THIS_TURN, tender)
            player.add_status(StatusType.DEXTERITY_LOSS_THIS_TURN, tender)
        if card.card_type == CardType.SKILL:
            player.skills_played_this_turn += 1
        if card.card_type == CardType.ATTACK:
            player.attacks_played_this_turn += 1

        x_amount = actual_cost if is_x_cost else 0
        player.card_damage_bonus = self._card_damage_bonus(player, card)
        downgraded = player.get_status(StatusType.DOWNGRADED) > 0 and card.upgraded
        if downgraded:
            card.upgraded = False
        try:
            self.resolve_card_effect(player, card, resolved_target, x_amount)
        finally:
            if downgraded:
                card.upgraded = True
            player.card_damage_bonus = 0

        forced_exhaust = player.exhaust_skills and card.card_type == CardType.SKILL
        if card.exhausts_now() or forced_exhaust:
            self.exhaust_card(player, card)
        elif self._goes_on_top_of_draw(player, card):
            player.draw_pile.append(card)
            self.log.append(f"{card.name} goes on top of {player.name}'s draw pile")
        else:
            player.discard_pile.append(card)

        self._check_victory_defeat()
        return True

    PLAY_CAP_CARDS = {"Sloth": 3, "Normality": 3}

    def play_cap(self, player: Player):
        """Lowest play cap imposed by anything in hand, or None."""
        return self._hand_context(player).play_cap

    def _goes_on_top_of_draw(self, player: Player, card: Card) -> bool:
        """Rebound ("put the NEXT card you play this turn on top of your Draw Pile") and Nostalgia ("the..."""
        armed_by = player.rebound_next_card
        if armed_by is not None and armed_by is not card:
            player.rebound_next_card = None
            return True
        if (player.nostalgia and not player.nostalgia_done_this_turn
                and card.card_type in (CardType.ATTACK, CardType.SKILL)):
            player.nostalgia_done_this_turn = True
            return True
        return False

    def resolve_card_effect(self, player: Player, card: Card,
                             target: Optional[Enemy] = None, x_amount: int = 0):
        """Run a card's effect and fire every 'a card was played' event it should trigger -- with NO..."""
        enemies_before = {id(e) for e in self.enemies if e.alive}
        for e in self.enemies:
            e.hit_by_current_card = False

        card.effect(self, player, target, card, x_amount)
        self._resolve_skittish()
        player.acted_this_turn = True
        player.cards_played_this_combat += 1
        player.fire_hook("card_played", card=card)
        if card.card_type == CardType.ATTACK:
            player.fire_hook("attack_played", card=card)
        elif card.card_type == CardType.SKILL:
            player.fire_hook("skill_played", card=card)
        elif card.card_type == CardType.POWER:
            player.fire_hook("power_played", card=card)

        newly_dead = [e for e in self.enemies if not e.alive and id(e) in enemies_before]
        if newly_dead:
            for p in self.players:
                if p.alive:
                    for _ in newly_dead:
                        p.fire_hook("enemy_died")

        replays = 0
        if not player._replaying_attack and not self._combat_over:
            if card.card_type == CardType.ATTACK and player.extra_attack_plays > 0:
                player.extra_attack_plays -= 1
                replays += 1
            if player.extra_card_plays > 0:
                player.extra_card_plays -= 1
                replays += 1
            replays += card.replay
        if replays:
            player._replaying_attack = True
            try:
                for _ in range(replays):
                    if self._combat_over:
                        break
                    self.log.append(f"{card.name} is played an extra time")
                    self.resolve_card_effect(player, card, target, x_amount)
            finally:
                player._replaying_attack = False

    AUTO_PLAY_MAX_DEPTH = 5

    def auto_play_card(self, player: Player, card: Card, target: Optional[Enemy] = None,
                        source: str = "", from_exhaust: bool = False) -> bool:
        """Play a card outside the normal pay-cost-from-hand flow."""
        if self._combat_over or not player.alive:
            return False
        if player._auto_play_depth >= self.AUTO_PLAY_MAX_DEPTH:
            self.log.append(f"{card.name} not auto-played ({source}): chain depth cap reached")
            return False
        if card.card_type == CardType.STATUS:
            return False

        resolved = target
        if card.target == TargetMode.SINGLE_ENEMY and (resolved is None or not resolved.alive):
            alive = self.enemies_alive()
            if not alive:
                return False
            resolved = alive[0]
        elif card.target in (TargetMode.SELF, TargetMode.SELF_OR_ALLY):
            resolved = player
        elif card.target == TargetMode.ALLY:
            resolved = self.other_player(player)

        if card in player.hand:
            player.hand.remove(card)
        self.log.append(f"{player.name} plays {card.name} automatically ({source})")

        player._auto_play_depth += 1
        try:
            self.resolve_card_effect(player, card, resolved)
        finally:
            player._auto_play_depth -= 1

        if not from_exhaust:
            if card.exhausts_now() or (player.exhaust_skills and card.card_type == CardType.SKILL):
                self.exhaust_card(player, card)
            else:
                player.discard_pile.append(card)
        self._check_victory_defeat()
        return True

    def use_potion(self, player: Player, potion, target: Optional[Enemy] = None) -> bool:
        """Potions aren't Cards -- no cost, no hand/discard/exhaust pile, no card_type -- so this is a..."""
        if self._combat_over:
            return False
        if potion not in player.potions:
            self.log.append(f"ILLEGAL: {potion.name} not in {player.name}'s inventory")
            return False
        if potion.target == "enemy" and (target is None or not target.alive):
            return False

        player.potions.remove(potion)
        self.log.append(f"{player.name} uses {potion.name}")
        potion.effect(self, player, target=target)
        player.fire_hook("use_potion", potion=potion)

        self._check_victory_defeat()
        return True

    def exhaust_card(self, player: Player, card: Card):
        """Move a card into player's exhaust pile and update every counter real cards read off of it (Dark..."""
        if card in player.hand:
            player.hand.remove(card)
        elif card in player.discard_pile:
            player.discard_pile.remove(card)
        player.exhaust_pile.append(card)
        player.exhausted_this_turn.append(card)
        self.total_exhausted_this_combat += 1
        self.log.append(f"{player.name} exhausts {card.name}")
        player.fire_hook("card_exhausted", card=card)

    def end_player_turn(self):
        if self._combat_over:
            return
        for p in self.players:
            if p.alive:
                p.fire_hook("turn_end")
        if self._combat_over:
            return
        for p in self.players:
            if p.alive:
                self._resolve_constrict(p)
                self._resolve_infection(p)
                for c in p.hand + p.draw_pile + p.discard_pile:
                    c.bound = False
                self._resolve_eruptions(p)
                p.end_turn(self.log)
                for relic in p.relics:
                    if relic.on_turn_end:
                        relic.on_turn_end(self, p)
        self._check_victory_defeat()

    @staticmethod
    def _card_damage_bonus(player: Player, card: Card) -> int:
        """Flat per-card damage from relics that key off the card itself."""
        if card.card_type != CardType.ATTACK:
            return 0
        bonus = 0
        for relic in player.relics:
            if relic.name == "Strike Dummy" and "Strike" in card.name:
                bonus += 3
            elif relic.name == "Miniature Cannon" and card.upgraded:
                bonus += 3
        return bonus

    def _resolve_eruptions(self, player: Player):
        """Steam Eruption's posthumous damage, ticking down at the end of each player turn."""
        still = []
        for bomb in self.pending_eruptions:
            bomb[1] -= 1
            if bomb[1] <= 0:
                player.take_damage(bomb[0], source_is_attack=False,
                                    log=self.log, label="Steam Eruption")
            else:
                still.append(bomb)
        self.pending_eruptions = still

    def _resolve_skittish(self):
        """Skittish: "The first time this creature is hit each turn, it gains X Block." Fires once per..."""
        for e in self.enemies:
            if not (e.alive and e.hit_by_current_card):
                continue
            e.hit_by_current_card = False
            amount = e.get_status(StatusType.SKITTISH)
            if amount > 0 and not e.skittish_used_this_turn:
                e.skittish_used_this_turn = True
                gained = e.gain_block(amount)
                self.log.append(f"{e.name} gains {gained} block (Skittish)")

    def _resolve_constrict(self, player: Player):
        """Slithering Strangler's Constrict: 'while the Slithering Strangler is alive, at the end of your..."""
        stacks = player.get_status(StatusType.CONSTRICT)
        if stacks <= 0:
            return
        if any(e.alive and e.name == "Slithering Strangler" for e in self.enemies):
            player.take_damage(stacks, source_is_attack=False, log=self.log, label="Constrict")

    END_OF_TURN_HAND_PENALTIES = {
        "Infection":      ("damage", 3, False),
        "Beckon":         ("hp_loss", 6, False),
        "Toxic":          ("damage", 5, True),
        "Burn":           ("damage", 2, False),
        "Disintegration": ("damage", 6, False),
        "Bad Luck":       ("hp_loss", 13, False),
        "Decay":          ("damage", 2, False),
        "Regret":         ("hp_per_card", 1, False),
        "Doubt":          (StatusType.WEAK, 1, False),
        "Shame":          (StatusType.FRAIL, 1, False),
    }

    def _resolve_infection(self, player: Player):
        """Resolve every "if this is in your Hand at end of turn" status card."""
        for card in [c for c in player.hand if c.name.startswith("Wither")]:
            player.take_damage(card.val("damage", 3), source_is_attack=False,
                                log=self.log, label=card.name)
        for name, (kind, amount, exhausts) in self.END_OF_TURN_HAND_PENALTIES.items():
            held = [c for c in player.hand if c.name == name]
            for card in held:
                if kind == "hp_loss":
                    player.lose_hp(amount, log=self.log, label=name)
                elif kind == "damage":
                    player.take_damage(amount, source_is_attack=False,
                                        log=self.log, label=name)
                elif kind == "hp_per_card":
                    player.lose_hp(amount * len(player.hand), log=self.log, label=name)
                else:
                    player.pending_end_of_turn_statuses.append((kind, amount, name))
                if exhausts:
                    self.exhaust_card(player, card)

    def run_enemy_turn(self):
        if self._combat_over:
            return
        extra = [p for p in self.players_alive() if p.extra_turns > 0]
        if extra:
            for p in extra:
                p.extra_turns -= 1
            self.log.append("The enemies lose their turn (extra turn taken)")
            return
        self.log.append(f"--- Turn {self.turn_number}: Enemy phase ---")
        for e in list(self.enemies):
            if e.revive_in > 0:
                e.revive_in -= 1
                if e.revive_in <= 0 and e.on_revive is not None:
                    e.on_revive(self, e)
        for e in list(self.enemies):
            if e.alive and self.players_alive():
                if e.stunned_turns > 0:
                    e.stunned_turns -= 1
                    self.log.append(f"{e.name} is stunned and does nothing")
                    continue
                e.take_turn(self)
                for p in self.players:
                    if p.alive:
                        p.fire_hook("enemy_turn_end", enemy=e)
                self._check_victory_defeat()
                if self._combat_over:
                    break

    def _check_victory_defeat(self):
        for e in list(self.enemies):
            if not e.alive and not e.death_resolved:
                self.handle_enemy_death(e)
        if not self.players_alive():
            self._combat_over = True
            self._victory = False
            self.log.append("=== DEFEAT: all players down ===")
        elif not self.enemies_alive():
            self._combat_over = True
            self._victory = True
            self.log.append("=== VICTORY: all enemies defeated ===")
            for p in self.players:
                if p.alive:
                    for relic in p.relics:
                        if relic.on_combat_end:
                            relic.on_combat_end(self, p)
            for p in self.players:
                p.revert_combat_upgrades()
                p.clear_temp_costs("combat")
                p.clear_temp_replays()

    @property
    def is_over(self) -> bool:
        return self._combat_over

    @property
    def victory(self) -> bool:
        return self._victory

    def playable_cards(self, player: Player) -> List[Card]:
        """Every card in hand that play_card would actually accept right now."""
        ctx = self._hand_context(player)
        return [c for c in player.hand
                if self.why_not_playable(player, c, ctx) is None]
