import json
import tempfile
import unittest
from pathlib import Path

from mldtools_media.config_store import ConfigStore, PERFORMANCE_PROFILES


class ConfigStoreTests(unittest.TestCase):
    def test_defaults_are_created_and_limits_are_normalised(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)
            updated = store.update(
                {
                    "threads_per_file": 999,
                    "parallel_downloads": 0,
                    "namespace": "",
                    "keep_original_filename": True,
                }
            )
            self.assertEqual(updated["threads_per_file"], 32)
            self.assertEqual(updated["parallel_downloads"], 1)
            self.assertEqual(updated["namespace"], "default")
            self.assertTrue(updated["keep_original_filename"])
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["threads_per_file"], 32)
            self.assertTrue(payload["keep_original_filename"])

    def test_aggressive_profile_is_accepted_without_clamping(self):
        threads, parallel, pool = PERFORMANCE_PROFILES["aggressive"]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)
            updated = store.update(
                {
                    "threads_per_file": threads,
                    "parallel_downloads": parallel,
                    "dc_pool": pool,
                }
            )

        self.assertEqual(updated["threads_per_file"], 24)
        self.assertEqual(updated["parallel_downloads"], 8)
        self.assertEqual(updated["dc_pool"], 16)


if __name__ == "__main__":
    unittest.main()
