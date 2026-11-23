"""Run:  python test_CharacteristicAnalyzer.py   (from inside this folder)"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import CharacteristicAnalyzer as CA
import Internals.ContextAnalysis as ContextAnalysis, Internals.ActionEvaluation as ActionEvaluation, Internals.BehavioralEvidence as BehavioralEvidence, Internals.CharacteristicUpdate as CharacteristicUpdate
import History.AggressiveAgent as AggressiveAgent
import History.DefensiveAgent as DefensiveAgent
import History.PlayerRefCheese as CheeseAgent
import History.RandomAgent as RandomAgent
import History.AChangeOfHeart as ChangeAgent

HISTORIES = {
    "Aggressive": AggressiveAgent.getHistory(),
    "Defensive": DefensiveAgent.getHistory(),
    "Cheese": CheeseAgent.getHistory(),
    "Random": RandomAgent.getHistory(),
    "Change": ChangeAgent.getHistory(),
}
ZERO = {k: 0 for k in ("A", "S", "T", "d_A", "d_S", "d_T", "c_A", "c_S", "c_T")}


def reference(history, old):
    """The original test.py pipeline, one turn."""
    dc = ContextAnalysis.getDecisionContext(history)
    ev = ActionEvaluation.getEvidence(dc)
    up = BehavioralEvidence.getUpdate(ev)
    return CharacteristicUpdate.getNewProfile(up, old)


class Tests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        CA.setProfileDir(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, name):
        with open(os.path.join(self.dir, name + ".json")) as fh:
            return json.load(fh)

    def test_new_profile_creates_zero_json(self):
        CA.newProfile(1, "ally1")
        self.assertEqual(self.read("ally1"), ZERO)

    def test_new_profile_does_not_wipe_existing(self):
        CA.newProfile(1, "ally1")
        CA.updateProfile(1, HISTORIES["Aggressive"][0])
        saved = self.read("ally1")
        with self.assertRaises(FileExistsError):
            CA.newProfile(1, "ally1")
        self.assertEqual(self.read("ally1"), saved)
        CA.newProfile(1, "ally1", overwrite=True)
        self.assertEqual(self.read("ally1"), ZERO)

    def test_filename_with_or_without_extension(self):
        CA.newProfile(1, "a.json")
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "a.json")))
        with self.assertRaises(ValueError):
            CA.newProfile(2, "../escape")

    def test_connect_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            CA.connectProfile(1, "nope")

    def test_update_without_attach(self):
        with self.assertRaises(KeyError):
            CA.updateProfile(3, HISTORIES["Aggressive"][0])

    def test_matches_original_pipeline_for_all_histories(self):
        for i, (name, hist) in enumerate(HISTORIES.items(), start=1):
            CA.newProfile(i, name)
            old = dict(ZERO)
            for t in range(100):
                old = reference(hist[t], old)
                out = CA.updateProfile(i, hist[t])
                self.assertEqual(sorted(out), sorted(["A", "S", "T", "c_A", "c_S", "c_T"]))
                for k in out:
                    self.assertEqual(out[k], old[k], f"{name} turn {t} {k}")
            self.assertEqual(self.read(name), old)       # JSON holds the full profile

    def test_three_allies_are_independent(self):
        for i in (1, 2, 3):
            CA.newProfile(i, f"ally{i}")
        for t in range(20):
            a = CA.updateProfile(1, HISTORIES["Aggressive"][t])
            d = CA.updateProfile(2, HISTORIES["Defensive"][t])
        self.assertGreater(a["A"], 0)
        self.assertLess(d["A"], 0)
        self.assertEqual(self.read("ally3"), ZERO)

    def test_reconnect_continues_from_saved_state(self):
        hist = HISTORIES["Aggressive"]
        CA.newProfile(1, "x")
        for t in range(10):
            CA.updateProfile(1, hist[t])
        CA.setProfileDir(self.dir)                       # drops connections (like a restart)
        CA.connectProfile(1, "x")
        old = self.read("x")
        out = CA.updateProfile(1, hist[10])
        expected = reference(hist[10], old)
        self.assertEqual(out["A"], expected["A"])

    def test_bad_history_leaves_file_untouched(self):
        CA.newProfile(1, "x")
        CA.updateProfile(1, HISTORIES["Aggressive"][0])
        before = self.read("x")
        for bad in ([3, [[-1, 6, 0, []]], [], 0], [3, [], []], "nonsense", [3, [[1, 6, 0]], [], 0]):
            with self.assertRaises(ValueError):
                CA.updateProfile(1, bad)
        self.assertEqual(self.read("x"), before)

    def test_corrupt_json_is_rejected(self):
        with open(os.path.join(self.dir, "bad.json"), "w") as fh:
            fh.write("{ not json")
        with self.assertRaises(ValueError):
            CA.connectProfile(1, "bad")


if __name__ == "__main__":
    unittest.main(verbosity=2)
