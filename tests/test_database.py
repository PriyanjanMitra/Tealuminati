import tempfile
import time
import unittest

from tealuminati.services.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(f"{self.tmp.name}/test.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_meta_roundtrip(self):
        self.assertIsNone(self.db.get_meta("missing"))
        self.assertEqual(self.db.get_meta_int("missing", 7), 7)
        self.db.set_meta("check_count", 42)
        self.assertEqual(self.db.get_meta_int("check_count"), 42)
        self.db.set_meta("check_count", 43)
        self.assertEqual(self.db.get_meta_int("check_count"), 43)

    def test_baseline_roundtrip(self):
        self.assertEqual(self.db.load_baseline(), set())
        self.db.save_baseline({"b", "a"})
        self.assertEqual(self.db.load_baseline(), {"a", "b"})
        self.db.save_baseline({"c"})
        self.assertEqual(self.db.load_baseline(), {"c"})

    def test_stability_roundtrip(self):
        self.db.save_stability({"x": 2, "y": -1, "z": 0})
        loaded = self.db.load_stability()
        self.assertEqual(loaded, {"x": 2, "y": -1})

    def test_notified_and_prune(self):
        self.db.record_notified("n", when=100.0)
        self.db.prune_notified(older_than=50.0)
        self.assertIn("n", self.db.load_notified())
        self.db.prune_notified(older_than=150.0)
        self.assertNotIn("n", self.db.load_notified())

    def test_ping_roles_defaults_and_override(self):
        from tealuminati import config

        roles = self.db.load_ping_roles()
        self.assertEqual(roles["home"], config.DEFAULT_PING_ROLES["home"])
        self.db.set_ping_role("home", 999)
        self.assertEqual(self.db.load_ping_roles()["home"], 999)
        self.assertEqual(
            self.db.load_ping_roles()["deputy"], config.DEFAULT_PING_ROLES["deputy"]
        )


if __name__ == "__main__":
    unittest.main()
