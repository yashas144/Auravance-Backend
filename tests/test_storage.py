from __future__ import annotations

import unittest

from app.core.config import settings
from app.core.database import _adapt_sql, storage_dialect, uses_postgres


class StorageAdapterTests(unittest.TestCase):
    def test_empty_database_url_is_sqlite(self) -> None:
        original = settings.database_url
        settings.database_url = ""
        try:
            self.assertFalse(uses_postgres())
            self.assertEqual(storage_dialect(), "sqlite")
            self.assertEqual(_adapt_sql("SELECT asset_id FROM assets WHERE asset_id = ?"), "SELECT asset_id FROM assets WHERE asset_id = ?")
        finally:
            settings.database_url = original

    def test_database_url_switches_placeholders(self) -> None:
        original = settings.database_url
        settings.database_url = "postgresql://auravance:auravance@127.0.0.1:5432/auravance"
        try:
            self.assertTrue(uses_postgres())
            self.assertEqual(storage_dialect(), "postgresql")
            self.assertEqual(
                _adapt_sql("SELECT asset_id FROM assets WHERE asset_id = ?"),
                "SELECT asset_id FROM assets WHERE asset_id = %s",
            )
        finally:
            settings.database_url = original


if __name__ == "__main__":
    unittest.main()
