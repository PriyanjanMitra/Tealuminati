import unittest

from tealuminati.services.region_logic import can_notify, confirm_changes, update_counters


class UpdateCountersTests(unittest.TestCase):
    def test_join_increments(self):
        counters = {}
        update_counters(counters, {"a"}, set())
        self.assertEqual(counters["a"], 1)

    def test_leave_decrements(self):
        counters = {}
        update_counters(counters, set(), {"a"})
        update_counters(counters, set(), {"a"})
        self.assertEqual(counters["a"], -2)

    def test_flip_cancels(self):
        counters = {"a": -1}
        update_counters(counters, {"a"}, set())
        self.assertNotIn("a", counters)

        counters = {"b": 3}
        update_counters(counters, set(), {"b"})
        self.assertNotIn("b", counters)

    def test_decay_when_absent(self):
        counters = {"a": 2, "b": -2}
        update_counters(counters, set(), set())
        self.assertEqual(counters, {"a": 1, "b": -1})
        update_counters(counters, set(), set())
        self.assertEqual(counters, {})


class ConfirmChangesTests(unittest.TestCase):
    def test_thresholds(self):
        counters = {"joiner": 3, "leaver": -20, "pending": 2}
        joins, leaves = confirm_changes(counters, join_threshold=3, leave_threshold=20)
        self.assertEqual(joins, {"joiner"})
        self.assertEqual(leaves, {"leaver"})


class CanNotifyTests(unittest.TestCase):
    def test_first_time(self):
        self.assertTrue(can_notify(None, now=1000.0, cooldown=300))

    def test_within_cooldown(self):
        self.assertFalse(can_notify(900.0, now=1000.0, cooldown=300))

    def test_after_cooldown(self):
        self.assertTrue(can_notify(600.0, now=1000.0, cooldown=300))


if __name__ == "__main__":
    unittest.main()
