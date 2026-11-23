"""Bridge between the training environment and the CharacteristicAnalyzer package.

The package does all the analysis (import the FOLDER, use the functions from _api):
    CA.setProfileDir(directory)
    CA.newProfile(index, filename, overwrite)
    CA.updateProfile(index, [E_total, Used, Opp, incomingDamage, blockAtTurnEnd]) -> {A, S, T, c_A, c_S, c_T}

This file turns the engine's turn record into that history format, and keeps
each teammate's profile in memory, updated by the package's own pipeline - the
very steps updateProfile runs, without reading and writing a JSON file every
round. Training updates profiles every round in every env: a file each time is
slow, and on Windows replacing one fails now and then (WinError 5, while the
last write is still being scanned). With a profile_dir, each profile is also
saved there as the package saves it, one file per (env, seat), for looking at.
turn_evidence() scores one turn without any profile (the agent's own turns,
for f_0_variant3).
"""
import itertools
import os
import time

import CharacteristicAnalyzer as CA
from CharacteristicAnalyzer.Internals import (ActionEvaluation, BehavioralEvidence, ContextAnalysis,
                                              _Pipeline, _ProfileStore, _Validation)

OUTPUT_KEYS = ("A", "S", "T", "c_A", "c_S", "c_T")

_profile_dir = None
_env_ids = itertools.count()


def use_profile_dir(directory):
    """Point the package at one folder. Only resets it when the folder changes."""
    global _profile_dir
    directory = os.path.abspath(directory)
    if directory != _profile_dir:
        CA.setProfileDir(directory)
        _profile_dir = directory


def zero_profile():
    return {k: 0.0 for k in OUTPUT_KEYS}


def to_history(turn):
    """Engine turn record -> [E_total, Used, Opp, incomingDamage, blockAtTurnEnd].

    Opp is every card that was in hand this turn (used + left over), each with
    the values it showed in hand. incomingDamage is the hit aimed at the player
    when they ended; blockAtTurnEnd their Block then. The package takes off the
    Block that did not come from their own cards (start of turn, teammates):
    I = incomingDamage - (blockAtTurnEnd - Block of the used cards).
    """
    used = [[c, d, b, sorted(g)] for c, d, b, g in turn["used"]]
    left = [[c, d, b, sorted(g)] for c, d, b, g in turn["leftover"]]
    # the real engine hands over Opp as it was seen (a card drawn and discarded mid-turn too)
    opp = [[c, d, b, sorted(g)] for c, d, b, g in turn["opp"]] if "opp" in turn else left + used
    history = [turn["E_total"], used, opp, turn["intent"]]
    if "end_block" in turn:
        history.append(turn["end_block"])
    return history


def turn_evidence(turn):
    """One turn's evidence and weight per trait, {e_A, e_S, e_T, w_A, w_S, w_T},
    worked out as the package does but without reading or writing a profile."""
    context = ContextAnalysis.getDecisionContext(to_history(turn))
    return BehavioralEvidence.getUpdate(ActionEvaluation.getEvidence(context))


class TeamProfiles:
    """The profiles of one environment's teammates (seats 1-3). `values` holds what the agent
    sees (A, S, T, c_A, c_S, c_T); the package's whole profile (with d_A ...) is kept beside it."""

    def __init__(self, profile_dir=None):
        self.profile_dir = profile_dir
        if profile_dir:
            use_profile_dir(profile_dir)
        self.tag = f"env{os.getpid()}_{next(_env_ids)}"
        self.values = {}
        self._full = {}

    def new_team(self, seats):
        """New teammates: fresh all-zero profiles (and files, with a profile_dir)."""
        self.values, self._full = {}, {}
        for seat in seats:
            self._full[seat] = _ProfileStore.zeroProfile()
            self.values[seat] = zero_profile()
            if self.profile_dir:
                name = f"{self.tag}_seat{seat}"
                CA.newProfile(name, name, overwrite=True)

    def update(self, seat, turn):
        """One turn into the profile, as CA.updateProfile does it: check the history, run the
        pipeline on the old profile, check the result."""
        history = to_history(turn)
        _Validation.checkHistory(history)
        profile = _Pipeline.run(history, self._full[seat])
        _Validation.checkFinite(profile)
        self._full[seat] = profile
        self.values[seat] = _Pipeline.output(profile)
        if self.profile_dir:
            self._save(f"{self.tag}_seat{seat}", profile)

    @staticmethod
    def _save(name, profile, tries=5):
        """The package's own write, tried again when Windows refuses the replace for a moment."""
        for attempt in range(tries):
            try:
                _ProfileStore.write(_ProfileStore._pathFor(name), profile)
                return
            except PermissionError:
                if attempt == tries - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))

    def get(self, seat):
        return self.values.get(seat)


def profile_vector(p):
    """The 6 numbers the agent sees: A, S, T, C_A, C_S, C_T."""
    return [p["A"], p["S"], p["T"], p["c_A"], p["c_S"], p["c_T"]]
