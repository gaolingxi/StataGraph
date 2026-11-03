import tempfile
import unittest
from pathlib import Path

from statagraph.parser import parse_stata_file


SAMPLE = r'''
* baseline pipeline
clear all
global controls age educ hhsize
local y resilience

do "01_clean.do"
use "analysis_data_v2.dta", clear
use hhid city_lab using "master_city.dta", clear
merge 1:1 hhid year using "city_controls.dta"

gen ln_ai = ln(ai_patent + 1)
egen mean_income = mean(income)
bysort hhid: egen max_income = max(income)
by hhid (year): gen first_obs = _n == 1
replace ln_ai = . if ai_patent < 0
rename old_debt debt

eststo base: reghdfe `y' ln_ai $controls, absorb(hhid city#year) vce(cluster city)
esttab base using "table1.rtf", replace
save "analysis_ready.dta", replace
'''


class ParserTests(unittest.TestCase):
    def test_core_constructs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dofile = root / "main.do"
            dofile.write_text(SAMPLE, encoding="utf-8")
            parsed = parse_stata_file(dofile, root)

        self.assertEqual(parsed["calls"][0]["target"], "01_clean.do")
        self.assertEqual(parsed["data_reads"][0]["path"], "analysis_data_v2.dta")
        self.assertEqual(parsed["data_reads"][1]["path"], "master_city.dta")
        self.assertEqual(parsed["data_merges"][0]["path"], "city_controls.dta")
        self.assertEqual(parsed["data_writes"][0]["path"], "analysis_ready.dta")

        variables = {row["name"]: row for row in parsed["variables"]}
        self.assertIn("ln_ai", variables)
        self.assertIn("ai_patent", variables["ln_ai"]["depends_on"])
        self.assertIn("max_income", variables)
        self.assertIn("income", variables["max_income"]["depends_on"])
        self.assertIn("first_obs", variables)
        self.assertIn("debt", variables)
        self.assertEqual(variables["debt"]["depends_on"], ["old_debt"])

        self.assertEqual(len(parsed["regressions"]), 1)
        reg = parsed["regressions"][0]
        self.assertEqual(reg["estimator"], "reghdfe")
        self.assertEqual(reg["estimate_name"], "base")
        self.assertEqual(reg["y"], "`y'")
        self.assertIn("ln_ai", reg["rhs"])
        self.assertEqual(reg["fe"], "hhid city#year")
        self.assertEqual(reg["cluster"], "city")
        self.assertIn("controls", reg["macro_refs"])

        self.assertEqual(parsed["outputs"][0]["using"], "table1.rtf")


if __name__ == "__main__":
    unittest.main()
