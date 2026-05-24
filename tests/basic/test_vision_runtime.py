import pickle
import shutil
import tempfile
import unittest
from pathlib import Path

from aider_vision_core.vision_runtime import (
    CACHE_LOAD_ERRORS,
    LEGACY_PYTHON_PACKAGE,
    REPO_MAP_CACHE_DIRNAME,
    purge_legacy_tag_caches,
    safe_cache_len,
)


class TestVisionRuntime(unittest.TestCase):
    def test_purge_legacy_tag_caches(self):
        root = Path(tempfile.mkdtemp())
        try:
            (root / ".aider.tags.cache.v3").mkdir()
            (root / ".aider.tags.cache.v4").mkdir()
            (root / REPO_MAP_CACHE_DIRNAME).mkdir()
            (root / "src").mkdir()
            removed = purge_legacy_tag_caches(root)
            self.assertEqual(len(removed), 2)
            self.assertFalse((root / ".aider.tags.cache.v3").exists())
            self.assertTrue((root / REPO_MAP_CACHE_DIRNAME).exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_safe_cache_len_on_bad_pickle(self):
        class BadCache:
            def __len__(self):
                raise ModuleNotFoundError(f"No module named '{LEGACY_PYTHON_PACKAGE}'")

        self.assertEqual(safe_cache_len(BadCache()), -1)

    def test_cache_load_errors_includes_unpickle(self):
        self.assertIn(pickle.UnpicklingError, CACHE_LOAD_ERRORS)


if __name__ == "__main__":
    unittest.main()
