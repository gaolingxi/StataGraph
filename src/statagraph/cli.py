from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .indexer import (
    build_index,
    dataset_lineage,
    find_log_results,
    find_regressions,
    find_variable,
    get_log_errors,
    load_or_build,
    save_index,
    search_logs,
)


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def cmd_index(args: argparse.Namespace) -> int:
    index = build_index(args.project)
    target = save_index(index, args.project)
    _print_json({"status": "ok", "index": target.as_posix(), "summary": index["summary"]})
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    _print_json(index["summary"])
    return 0


def cmd_find_variable(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    result = find_variable(index, args.name)
    if result is None:
        _print_json({"found": False, "variable": args.name})
        return 1
    _print_json({"found": True, "variable": args.name, **result})
    return 0


def cmd_find_regressions(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    result = find_regressions(index, x=args.x, y=args.y)
    _print_json({"count": len(result), "regressions": result})
    return 0


def cmd_dataset_lineage(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    result = dataset_lineage(index, args.dataset)
    _print_json(result)
    return 0 if result.get("found") else 1


def cmd_table_sources(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    _print_json({"count": len(index.get("outputs", [])), "outputs": index.get("outputs", [])})
    return 0


def cmd_calls(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    rows = index.get("calls", [])
    if args.target:
        target_name = Path(args.target).name
        rows = [row for row in rows if Path(row.get("target", "")).name == target_name]
    _print_json({"count": len(rows), "calls": rows})
    return 0


def cmd_search_logs(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    rows = search_logs(index, args.query, limit=args.limit)
    _print_json({"query": args.query, "count": len(rows), "matches": rows})
    return 0 if rows else 1


def cmd_log_results(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    rows = find_log_results(index, x=args.x, y=args.y, task=args.task, p_lt=args.p_lt)
    _print_json({"count": len(rows), "results": rows})
    return 0 if rows else 1


def cmd_log_errors(args: argparse.Namespace) -> int:
    index = load_or_build(args.project, rebuild=args.rebuild)
    rows = get_log_errors(index)
    _print_json({"count": len(rows), "errors": rows})
    return 0 if rows else 1


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project", help="Path to the Stata project")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the index before querying")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="statagraph", description="Research-aware lineage for Stata projects")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("index", help="Build .statagraph/index.json")
    p.add_argument("project")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("summary", help="Show project index summary")
    _add_common(p)
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("find-variable", help="Show where a variable is created and used")
    _add_common(p)
    p.add_argument("name")
    p.set_defaults(func=cmd_find_variable)

    p = sub.add_parser("find-regressions", help="Find regressions by X and/or Y")
    _add_common(p)
    p.add_argument("--x")
    p.add_argument("--y")
    p.set_defaults(func=cmd_find_regressions)

    p = sub.add_parser("dataset-lineage", help="Trace upstream/downstream datasets")
    _add_common(p)
    p.add_argument("dataset")
    p.set_defaults(func=cmd_dataset_lineage)

    p = sub.add_parser("table-sources", help="List estimate/table output commands")
    _add_common(p)
    p.set_defaults(func=cmd_table_sources)

    p = sub.add_parser("calls", help="List do/run/include relationships")
    _add_common(p)
    p.add_argument("--target")
    p.set_defaults(func=cmd_calls)

    p = sub.add_parser("search-logs", help="Search raw Stata logs plus structured log metadata/results")
    _add_common(p)
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_search_logs)

    p = sub.add_parser("log-results", help="Find structured regression results recovered from Stata logs")
    _add_common(p)
    p.add_argument("--x", help="Coefficient/variable name")
    p.add_argument("--y", help="Outcome variable")
    p.add_argument("--task", help="TASK_ID or substring")
    p.add_argument("--p-lt", type=float, help="Keep matched coefficients with p below this threshold")
    p.set_defaults(func=cmd_log_results)

    p = sub.add_parser("log-errors", help="List Stata runtime r(#) errors found in logs")
    _add_common(p)
    p.set_defaults(func=cmd_log_errors)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
