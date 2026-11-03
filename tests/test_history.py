import tempfile
import unittest
from pathlib import Path

from statagraph.history_parser import parse_history_markdown
from statagraph.indexer import build_index, search_history


class HistoryTests(unittest.TestCase):
    def test_markdown_branch_log_and_registry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logs = root / "research_logs"
            logs.mkdir()
            branch = logs / "B003_income_risk.md"
            branch.write_text(
                "# Income downside risk\n\n"
                "BRANCH_ID: B003\n"
                "TASK_ID: E149_INCOME_RISK\n"
                "BASE_DATA: analysis_data_v2.dta\n"
                "BASELINE: baseline_v4\n"
                "PURPOSE: 检验收入下行风险机制\n"
                "CHANGE: Y 改为 downside_risk，其他规格不变\n"
                "STATUS: CLOSED_NULL\n"
                "RESULT: beta=-0.001, p=0.63\n"
                "DECISION: DROP\n",
                encoding="utf-8",
            )
            registry = root / "BRANCH_REGISTRY.md"
            registry.write_text(
                "| ID | 支线 | 基于 | 改动 | 状态 | 结论 |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| B003 | 收入风险 | baseline_v4 | 换Y | CLOSED_NULL | 不支持 |\n"
                "| B004 | 非就业 | baseline_v4 | 换Y | KEEP | 支持 |\n",
                encoding="utf-8",
            )

            parsed = parse_history_markdown(branch, root)
            self.assertEqual(parsed["fields"]["branch_id"], "B003")
            self.assertEqual(parsed["fields"]["task_id"], "E149_INCOME_RISK")
            self.assertEqual(parsed["fields"]["status"], "CLOSED_NULL")

            reg_parsed = parse_history_markdown(registry, root)
            self.assertEqual(len(reg_parsed["registry_rows"]), 2)
            self.assertEqual(reg_parsed["registry_rows"][0]["fields"]["branch_id"], "B003")
            self.assertEqual(reg_parsed["registry_rows"][1]["fields"]["status"], "KEEP")

    def test_unified_history_links_log_markdown_registry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logs = root / "research_logs"
            logs.mkdir()
            (logs / "B003.md").write_text(
                "BRANCH_ID: B003\n"
                "TASK_ID: E149_INCOME_RISK\n"
                "PURPOSE: income downside risk\n"
                "STATUS: KEEP\n",
                encoding="utf-8",
            )
            (root / "BRANCH_REGISTRY.md").write_text(
                "| ID | 支线 | 状态 | 结论 |\n"
                "| --- | --- | --- | --- |\n"
                "| B003 | income downside risk | KEEP | promoted |\n",
                encoding="utf-8",
            )
            (root / "E149.log").write_text(
                "TASK_ID=E149_INCOME_RISK\n"
                "BRANCH_ID=B003\n"
                "closed on: 3 Nov 2026\n",
                encoding="utf-8",
            )

            index = build_index(root)

            self.assertEqual(index["schema_version"], 3)
            self.assertEqual(index["summary"]["log_files"], 1)
            self.assertEqual(index["summary"]["history_markdown_files"], 2)
            self.assertGreaterEqual(index["summary"]["history_records"], 4)

            branch_hits = search_history(index, branch="B003")
            source_types = {row["source_type"] for row in branch_hits}
            self.assertIn("stata_log", source_types)
            self.assertIn("research_markdown", source_types)
            self.assertIn("branch_registry_row", source_types)

            md_hit = next(row for row in branch_hits if row["source_type"] == "research_markdown" and row["file"].endswith("B003.md"))
            related_types = {row["source_type"] for row in md_hit["related_records"]}
            self.assertIn("stata_log", related_types)
            self.assertIn("branch_registry_row", related_types)

            query_hits = search_history(index, query="downside risk")
            self.assertTrue(any(row.get("branch_id") == "B003" for row in query_hits))

            keep_hits = search_history(index, status="KEEP")
            self.assertTrue(any(row.get("branch_id") == "B003" for row in keep_hits))


if __name__ == "__main__":
    unittest.main()
