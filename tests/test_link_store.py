import tempfile
import unittest
from pathlib import Path

import link_store


class TestLinkStore(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "links.json"

    def test_empty_when_missing(self):
        store = link_store.LinkStore(self.path)
        self.assertIsNone(store.get(1))
        self.assertEqual(store.all(), {})

    def test_set_get_roundtrip(self):
        store = link_store.LinkStore(self.path)
        store.set(1, "emp-1")
        self.assertEqual(store.get(1), "emp-1")
        self.assertEqual(store.get("1"), "emp-1")  # normaliza a str

    def test_persists_across_instances(self):
        link_store.LinkStore(self.path).set(42, "emp-42")
        reloaded = link_store.LinkStore(self.path)
        self.assertEqual(reloaded.get(42), "emp-42")

    def test_remove(self):
        store = link_store.LinkStore(self.path)
        store.set(1, "emp-1")
        store.remove(1)
        self.assertIsNone(store.get(1))

    def test_corrupt_file_is_tolerated(self):
        self.path.write_text("{ no es json", encoding="utf-8")
        store = link_store.LinkStore(self.path)
        self.assertEqual(store.all(), {})


if __name__ == "__main__":
    unittest.main()
