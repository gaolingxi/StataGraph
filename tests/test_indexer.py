import tempfile
import unittest
from pathlib import Path

from statagraph.indexer import build_index, dataset_lineage, find_regressions, find_variable


class IndexerTests(unittest.TestCase):
    def test_project_index_and_lineage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "01_clean.do").write_text(
                'use "raw.dta", clear\n'
                'gen ln_x = ln(x + 1)\n'
                'save "analysis.dta", replace\n',
                encoding="utf-8",
            )
            (root / "02_reg.do").write_text(
                'use "analysis.dta", clear\n'
                'reghdfe y ln_x control1, absorb(id year) vce(cluster id)\n'
                'esttab using "table1.rtf", replace\n',
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index["summary"]["stata_files"], 2)
        self.assertEqual(index["summary"]["regressions"], 1)

        variable = find_variable(index, "ln_x")
        self.assertIsNotNone(variable)
        self.assertEqual(variable["created_or_modified_by"][0]["file"], "01_clean.do")
        self.assertEqual(len(variable["used_on_rhs"]), 1)

        regressions = find_regressions(index, x="ln_x", y="y")
        self.assertEqual(len(regressions), 1)
        self.assertEqual(regressions[0]["fe"], "id year")

        lineage = dataset_lineage(index, "analysis.dta")
        self.assertTrue(lineage["found"])
        self.assertIn("raw.dta", lineage["upstream"])


if __name__ == "__main__":
    unittest.main()
