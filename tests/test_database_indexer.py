import csv
import json
import tempfile
import unittest
from pathlib import Path

from statagraph.database_indexer import (
    build_database_index,
    database_profile,
    search_database_files,
    search_database_variables,
    search_databases,
)


class DatabaseIndexerTests(unittest.TestCase):
    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_registry_metadata_and_variable_search(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_csv(root / "catalog" / "datasets.csv", [{
                "dataset_id": "cfps",
                "name": "CFPS",
                "release_tag": "dataset-cfps",
                "release_url": "https://example.test/cfps",
                "original_files": "2",
                "original_bytes": "1024",
                "categories_json": '["家庭与个人微观调查"]',
                "metadata_files_json": '["metadata/CFPS/files.csv"]',
                "assets": "1",
                "asset_bytes": "1024",
                "role": "DATA",
            }])
            self._write_csv(root / "catalog" / "data_registry.csv", [{
                "dataset_id": "cfps",
                "dataset_name": "CFPS",
                "canonical_local_relpath": "01_家庭与个人微观调查\\CFPS",
                "release_tag": "dataset-cfps",
                "metadata_files_json": '["metadata/CFPS/files.csv"]',
                "verification_status": "VERIFIED",
                "verified_at": "2026-11-03",
                "verification_basis": "PATH+SIZE",
                "notes": "",
            }])
            self._write_csv(root / "metadata" / "CFPS" / "files.csv", [{
                "relative_path": "CFPS\\rawdata\\2018\\cfps2018person.dta",
                "extension": ".dta",
                "size_mb": "10.5",
                "n_obs": "1000",
                "n_vars": "120",
                "extra": "",
            }])
            self._write_csv(root / "metadata" / "CFPS" / "variables.csv", [
                {
                    "relative_path": "CFPS\\rawdata\\2018\\cfps2018person.dta",
                    "variable": "pid",
                    "label": "个人id",
                    "type": "double",
                    "original_type": "%12.0g",
                },
                {
                    "relative_path": "CFPS\\rawdata\\2018\\cfps2018person.dta",
                    "variable": "income",
                    "label": "个人收入",
                    "type": "double",
                    "original_type": "%12.0g",
                },
                {
                    "relative_path": "CFPS\\rawdata\\2018\\codebook.xlsx",
                    "variable": "2018成人问卷",
                    "label": "sheet:Sheet1",
                    "type": "",
                    "original_type": "",
                },
            ])

            index = build_database_index(root)

        self.assertEqual(index["summary"]["datasets"], 1)
        self.assertEqual(index["summary"]["files"], 1)
        self.assertEqual(index["summary"]["variables"], 2)
        self.assertEqual(index["summary"]["documentation_entries"], 1)

        hits = search_database_variables(index, "个人收入", dataset_id="cfps")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["variable"], "income")
        self.assertEqual(hits[0]["year"], 2018)
        self.assertEqual(
            hits[0]["local_path_relative"],
            "01_家庭与个人微观调查\\CFPS\\rawdata\\2018\\cfps2018person.dta",
        )

        self.assertEqual(search_databases(index, "CFPS")[0]["dataset_id"], "cfps")
        self.assertEqual(search_database_files(index, "person")[0]["n_obs"], 1000)
        profile = database_profile(index, "cfps")
        self.assertEqual(profile["years_inferred_from_file_paths"], [2018])

    def test_non_verified_registry_does_not_expose_local_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_csv(root / "catalog" / "datasets.csv", [{
                "dataset_id": "blocked",
                "name": "Blocked dataset",
                "release_tag": "dataset-blocked",
                "release_url": "",
                "original_files": "1",
                "original_bytes": "10",
                "categories_json": "[]",
                "metadata_files_json": '["metadata/blocked/files.csv"]',
                "assets": "1",
                "asset_bytes": "10",
                "role": "DATA",
            }])
            self._write_csv(root / "catalog" / "data_registry.csv", [{
                "dataset_id": "blocked",
                "dataset_name": "Blocked dataset",
                "canonical_local_relpath": "_unclassified\\blocked",
                "release_tag": "dataset-blocked",
                "metadata_files_json": '["metadata/blocked/files.csv"]',
                "verification_status": "BLOCKED",
                "verified_at": "",
                "verification_basis": "",
                "notes": "manual review required",
            }])
            self._write_csv(root / "metadata" / "blocked" / "files.csv", [{
                "relative_path": "blocked\\raw.dta",
                "extension": ".dta",
                "size_mb": "1",
                "n_obs": "10",
                "n_vars": "2",
                "extra": "",
            }])
            self._write_csv(root / "metadata" / "blocked" / "variables.csv", [{
                "relative_path": "blocked\\raw.dta",
                "variable": "income",
                "label": "收入",
                "type": "double",
                "original_type": "%9.0g",
            }])
            index = build_database_index(root)

        self.assertEqual(index["datasets"]["blocked"]["verification_status"], "BLOCKED")
        self.assertIsNone(index["datasets"]["blocked"]["canonical_local_relpath"])
        self.assertIsNone(index["variables"][0]["local_path_relative"])


    def test_shared_root_metadata_is_scoped_by_catalog_category(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shared = '["metadata/_root_files/files.csv"]'
            self._write_csv(root / "catalog" / "datasets.csv", [
                {
                    "dataset_id": "dataset_a",
                    "name": "Dataset A",
                    "categories_json": '["a.csv"]',
                    "metadata_files_json": shared,
                },
                {
                    "dataset_id": "dataset_b",
                    "name": "Dataset B",
                    "categories_json": '["b.csv"]',
                    "metadata_files_json": shared,
                },
            ])
            self._write_csv(root / "metadata" / "_root_files" / "files.csv", [
                {"relative_path": "a.csv", "extension": ".csv", "size_mb": "1", "n_obs": "", "n_vars": "1", "extra": ""},
                {"relative_path": "b.csv", "extension": ".csv", "size_mb": "2", "n_obs": "", "n_vars": "1", "extra": ""},
            ])
            self._write_csv(root / "metadata" / "_root_files" / "variables.csv", [
                {"relative_path": "a.csv", "variable": "alpha", "label": "Alpha field", "type": "", "original_type": ""},
                {"relative_path": "b.csv", "variable": "beta", "label": "Beta field", "type": "", "original_type": ""},
            ])
            index = build_database_index(root)

        self.assertEqual(index["datasets"]["dataset_a"]["files_count"], 1)
        self.assertEqual(index["datasets"]["dataset_a"]["variable_count"], 1)
        self.assertEqual(index["datasets"]["dataset_b"]["files_count"], 1)
        self.assertEqual(index["datasets"]["dataset_b"]["variable_count"], 1)
        self.assertEqual({row["variable"] for row in index["variables"]}, {"alpha", "beta"})


if __name__ == "__main__":
    unittest.main()
