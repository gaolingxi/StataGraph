import tempfile
import unittest
from pathlib import Path

from statagraph.indexer import build_index, find_log_results, get_log_errors, search_logs
from statagraph.log_parser import parse_log_file


GOOD_LOG = r'''
name: <unnamed>
log: C:/project/E176_main_tables.log
log type: text
opened on: 3 Nov 2026, 14:00:26

. di "TASK_ID=E176_MAIN_TABLES_CITYYEAR_FE_20261103"
TASK_ID=E176_MAIN_TABLES_CITYYEAR_FE_20261103
. di "FE=HOUSEHOLD_AND_CITY_YEAR; CLUSTER=PROVINCE; X=ORIGINAL"
FE=HOUSEHOLD_AND_CITY_YEAR; CLUSTER=PROVINCE; X=ORIGINAL

. e176_run, table("Table1") outcome(rho_main) label("rho_M4") oldn(28022)
HDFE Linear regression                            Number of obs   =     28,022
Number of clusters (province_cluster) =         29
                                                  R-squared       =     0.9185
                                                  Within R-sq.    =     0.1604

                            (Std. err. adjusted for 29 clusters in province_cluster)
------------------------------------------------------------------------------------
                   |               Robust
          rho_main | Coefficient  std. err.      t    P>|t|     [95% conf. interval]
-------------------+----------------------------------------------------------------
            X_orig |  -.0063757   .0018522    -3.44   0.002    -.0101698   -.0025816
     finres_hhsize |  -.0305211   .0009667   -31.57   0.000    -.0325013    -.028541
             _cons |    .916472    .021977    41.70   0.000     .8714542    .9614898
------------------------------------------------------------------------------------

closed on: 3 Nov 2026, 14:01:02
'''

ERROR_LOG = r'''
opened on: 3 Nov 2026, 15:00:00
. use "missing_file.dta", clear
file missing_file.dta not found
r(601);
closed on: 3 Nov 2026, 15:00:01
'''


class LogParserTests(unittest.TestCase):
    def test_realistic_log_result_and_markers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "E176_main_tables.log"
            path.write_text(GOOD_LOG, encoding="utf-8")
            parsed = parse_log_file(path, root)

        self.assertEqual(parsed["status"], "closed")
        self.assertEqual(parsed["markers"]["FE"], "HOUSEHOLD_AND_CITY_YEAR")
        self.assertEqual(parsed["markers"]["CLUSTER"], "PROVINCE")
        self.assertEqual(parsed["task_ids"], ["E176_MAIN_TABLES_CITYYEAR_FE_20261103"])
        self.assertEqual(len(parsed["results"]), 1)

        result = parsed["results"][0]
        self.assertEqual(result["outcome"], "rho_main")
        self.assertEqual(result["stats"]["N"], 28022)
        self.assertEqual(result["stats"]["clusters"], 29)
        self.assertEqual(result["command_hints"]["table"], "Table1")
        self.assertEqual(result["command_hints"]["label"], "rho_M4")

        x = next(row for row in result["coefficients"] if row["name"] == "X_orig")
        self.assertAlmostEqual(x["b"], -0.0063757)
        self.assertAlmostEqual(x["se"], 0.0018522)
        self.assertAlmostEqual(x["p"], 0.002)

    def test_index_query_pairing_search_and_errors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "E176_main_tables.do").write_text(
                'reghdfe rho_main X_orig, absorb(hhid cityyear) vce(cluster province)\n',
                encoding="utf-8",
            )
            (root / "E176_main_tables.log").write_text(GOOD_LOG, encoding="utf-8")
            (root / "E177_failed.log").write_text(ERROR_LOG, encoding="utf-8")

            index = build_index(root)

            self.assertEqual(index["summary"]["log_files"], 2)
            self.assertEqual(index["summary"]["log_results"], 1)
            self.assertEqual(index["summary"]["log_errors"], 1)
            self.assertEqual(
                index["logs"]["E176_main_tables.log"]["paired_stata_files"],
                ["E176_main_tables.do"],
            )

            rows = find_log_results(index, x="X_orig", y="rho_main", p_lt=0.05)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["matched_coefficients"][0]["p"], 0.002)

            matches = search_logs(index, "HOUSEHOLD_AND_CITY_YEAR")
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["file"], "E176_main_tables.log")

            raw_matches = search_logs(index, "finres_hhsize")
            self.assertEqual(len(raw_matches), 1)
            self.assertTrue(raw_matches[0]["result_hits"] or raw_matches[0]["excerpts"])

            errors = get_log_errors(index)
            self.assertEqual(errors[0]["rc"], 601)
            self.assertIn("not found", errors[0]["message"])


if __name__ == "__main__":
    unittest.main()
