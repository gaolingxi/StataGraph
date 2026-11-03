from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from .history_parser import parse_history_markdown, scan_history_markdown
from .log_parser import LOG_SUFFIXES, parse_log_file
from .parser import parse_stata_file

STATA_SUFFIXES = {".do", ".ado", ".mata"}
SKIP_DIRS = {".git", ".statagraph", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}


def _norm_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def _dataset_key(value: str) -> str:
    return _norm_path(value)


def _search_norm(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold(), flags=re.UNICODE)


def _scan_files(root: Path, suffixes: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return sorted(files)


def scan_stata_files(root: Path) -> list[Path]:
    return _scan_files(root, STATA_SUFFIXES)


def scan_log_files(root: Path) -> list[Path]:
    return _scan_files(root, LOG_SUFFIXES)


def _history_tokens(record: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("record_id", "branch_id", "task_id", "run_id"):
        value = record.get(key)
        if value:
            tokens.add(_search_norm(str(value)))
    for value in record.get("task_ids", []):
        if value:
            tokens.add(_search_norm(str(value)))
    return {token for token in tokens if token}


def _link_history_records(records: list[dict[str, Any]]) -> None:
    token_map: dict[str, list[int]] = defaultdict(list)
    for i, record in enumerate(records):
        for token in _history_tokens(record):
            token_map[token].append(i)

    related: dict[int, set[int]] = defaultdict(set)
    for indexes in token_map.values():
        if len(indexes) < 2:
            continue
        for i in indexes:
            related[i].update(j for j in indexes if j != i)

    for i, record in enumerate(records):
        record["related_records"] = [
            {
                "source_type": records[j].get("source_type"),
                "file": records[j].get("file"),
                "record_id": records[j].get("record_id"),
            }
            for j in sorted(related.get(i, set()))
        ]


def build_index(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"Project directory not found: {root_path}")

    parsed_files = [parse_stata_file(path, root_path) for path in scan_stata_files(root_path)]
    parsed_logs = [parse_log_file(path, root_path) for path in scan_log_files(root_path)]
    parsed_history_docs = [
        parse_history_markdown(path, root_path)
        for path in scan_history_markdown(root_path, SKIP_DIRS)
    ]

    datasets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "read_by": [],
        "written_by": [],
        "merged_by": [],
        "appended_by": [],
        "derived_from": [],
    })
    variables: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "created_or_modified_by": [],
        "depends_on": [],
        "used_as_y": [],
        "used_on_rhs": [],
    })
    calls: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    macros: list[dict[str, Any]] = []
    programs: list[dict[str, Any]] = []

    for parsed in parsed_files:
        file = parsed["file"]
        inputs: list[str] = []
        outputs_here: list[str] = []

        for event in parsed["calls"]:
            calls.append({"source": file, **event})

        for event in parsed["data_reads"]:
            key = _dataset_key(event["path"])
            datasets[key]["read_by"].append({"file": file, "line": event["line"], "kind": event["kind"]})
            inputs.append(key)

        for event in parsed["data_merges"]:
            key = _dataset_key(event["path"])
            datasets[key]["merged_by"].append({"file": file, "line": event["line"]})
            inputs.append(key)

        for event in parsed["data_appends"]:
            key = _dataset_key(event["path"])
            datasets[key]["appended_by"].append({"file": file, "line": event["line"]})
            inputs.append(key)

        for event in parsed["data_writes"]:
            key = _dataset_key(event["path"])
            datasets[key]["written_by"].append({"file": file, "line": event["line"], "kind": event["kind"]})
            outputs_here.append(key)

        for output in outputs_here:
            for source in dict.fromkeys(inputs):
                if source != output and source not in datasets[output]["derived_from"]:
                    datasets[output]["derived_from"].append(source)

        for event in parsed["variables"]:
            entry = variables[event["name"]]
            entry["created_or_modified_by"].append({
                "file": file,
                "line": event["line"],
                "action": event["action"],
                "raw": event["raw"],
            })
            for dep in event.get("depends_on", []):
                if dep not in entry["depends_on"]:
                    entry["depends_on"].append(dep)

        for reg in parsed["regressions"]:
            reg_id = f"{reg['file']}:{reg['line']}"
            enriched = {"id": reg_id, **reg}
            regressions.append(enriched)
            if reg.get("y"):
                variables[reg["y"]]["used_as_y"].append(reg_id)
            for rhs in reg.get("rhs", []):
                variables[rhs]["used_on_rhs"].append(reg_id)

        for event in parsed["outputs"]:
            outputs.append({"file": file, **event})
        for event in parsed["macros"]:
            macros.append({"file": file, **event})
        for event in parsed["programs"]:
            programs.append({"file": file, **event})

    stata_by_stem: dict[str, list[str]] = defaultdict(list)
    for item in parsed_files:
        stata_by_stem[Path(item["file"]).stem].append(item["file"])

    logs: dict[str, dict[str, Any]] = {}
    log_results: list[dict[str, Any]] = []
    log_errors: list[dict[str, Any]] = []
    history_records: list[dict[str, Any]] = []

    for parsed in parsed_logs:
        file = parsed["file"]
        paired = stata_by_stem.get(Path(file).stem, [])
        compact = {key: value for key, value in parsed.items() if key != "results"}
        compact["paired_stata_files"] = paired
        logs[file] = compact

        for result in parsed["results"]:
            log_results.append({
                "id": f"{file}:{result['line']}",
                **result,
                "paired_stata_files": paired,
            })
        for error in parsed["errors"]:
            log_errors.append({
                "file": file,
                "run_id": parsed["run_id"],
                "task_ids": parsed["task_ids"],
                **error,
            })

        markers = parsed.get("markers", {})
        history_records.append({
            "source_type": "stata_log",
            "file": file,
            "record_id": parsed.get("run_id") or Path(file).stem,
            "run_id": parsed.get("run_id"),
            "branch_id": markers.get("BRANCH_ID"),
            "task_id": markers.get("TASK_ID"),
            "task_ids": parsed.get("task_ids", []),
            "title": Path(file).stem,
            "status": parsed.get("status"),
            "fields": markers,
            "paired_stata_files": paired,
            "result_count": parsed.get("result_count", 0),
            "error_count": parsed.get("error_count", 0),
        })

    history_docs: dict[str, dict[str, Any]] = {}
    for parsed in parsed_history_docs:
        file = parsed["file"]
        doc = {key: value for key, value in parsed.items() if key != "registry_rows"}
        history_docs[file] = doc
        fields = parsed.get("fields", {})
        history_records.append({
            **doc,
            "branch_id": fields.get("branch_id"),
            "task_id": fields.get("task_id"),
            "status": fields.get("status") or fields.get("decision"),
        })
        for row in parsed.get("registry_rows", []):
            row_fields = row.get("fields", {})
            history_records.append({
                **row,
                "branch_id": row_fields.get("branch_id"),
                "task_id": row_fields.get("task_id"),
                "status": row_fields.get("status") or row_fields.get("decision"),
            })

    _link_history_records(history_records)

    return {
        "schema_version": 3,
        "root": root_path.as_posix(),
        "files": {item["file"]: item for item in parsed_files},
        "calls": calls,
        "datasets": dict(datasets),
        "variables": dict(variables),
        "regressions": regressions,
        "outputs": outputs,
        "macros": macros,
        "programs": programs,
        "logs": logs,
        "log_results": log_results,
        "log_errors": log_errors,
        "history_docs": history_docs,
        "history_records": history_records,
        "summary": {
            "stata_files": len(parsed_files),
            "log_files": len(parsed_logs),
            "history_markdown_files": len(parsed_history_docs),
            "history_records": len(history_records),
            "datasets": len(datasets),
            "variables": len(variables),
            "regressions": len(regressions),
            "outputs": len(outputs),
            "calls": len(calls),
            "log_results": len(log_results),
            "log_errors": len(log_errors),
        },
    }


def save_index(index: dict[str, Any], root: str | Path) -> Path:
    root_path = Path(root).expanduser().resolve()
    target_dir = root_path / ".statagraph"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "index.json"
    target.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_or_build(root: str | Path, rebuild: bool = False) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    target = root_path / ".statagraph" / "index.json"
    if target.exists() and not rebuild:
        index = json.loads(target.read_text(encoding="utf-8"))
        if index.get("schema_version") == 3:
            return index
    index = build_index(root_path)
    save_index(index, root_path)
    return index


def find_variable(index: dict[str, Any], name: str) -> dict[str, Any] | None:
    return index.get("variables", {}).get(name)


def find_regressions(index: dict[str, Any], x: str | None = None, y: str | None = None) -> list[dict[str, Any]]:
    rows = index.get("regressions", [])
    result: list[dict[str, Any]] = []
    for row in rows:
        if y is not None and row.get("y") != y:
            continue
        if x is not None:
            rhs = row.get("rhs", [])
            raw = row.get("raw", "")
            if x not in rhs and x not in raw:
                continue
        result.append(row)
    return result


def find_log_results(
    index: dict[str, Any],
    x: str | None = None,
    y: str | None = None,
    task: str | None = None,
    p_lt: float | None = None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    x_norm = _search_norm(x) if x else None
    y_norm = _search_norm(y) if y else None
    task_norm = _search_norm(task) if task else None

    for row in index.get("log_results", []):
        if y_norm and _search_norm(str(row.get("outcome", ""))) != y_norm:
            continue

        task_id = str(row.get("markers", {}).get("TASK_ID", ""))
        if task_norm and task_norm not in _search_norm(task_id):
            continue

        coefficients = row.get("coefficients", [])
        selected = coefficients
        if x_norm:
            selected = [item for item in coefficients if _search_norm(str(item.get("name", ""))) == x_norm]
            if not selected:
                continue

        if p_lt is not None:
            selected = [item for item in selected if item.get("p") is not None and item["p"] < p_lt]
            if not selected:
                continue

        result.append({**row, "matched_coefficients": selected})
    return result


def get_log_errors(index: dict[str, Any]) -> list[dict[str, Any]]:
    return list(index.get("log_errors", []))


def search_logs(index: dict[str, Any], query: str, limit: int = 20, excerpts_per_file: int = 5) -> list[dict[str, Any]]:
    query_norm = _search_norm(query)
    if not query_norm:
        return []

    root = Path(index["root"])
    matches: list[dict[str, Any]] = []

    for file, meta in index.get("logs", {}).items():
        structured_text = json.dumps({
            "file": file,
            "run_id": meta.get("run_id"),
            "task_ids": meta.get("task_ids", []),
            "markers": meta.get("markers", {}),
            "errors": meta.get("errors", []),
        }, ensure_ascii=False)
        structured_hit = query_norm in _search_norm(structured_text)

        result_hits = []
        for row in index.get("log_results", []):
            if row.get("file") != file:
                continue
            searchable = json.dumps({
                "outcome": row.get("outcome"),
                "command": row.get("command"),
                "command_hints": row.get("command_hints", {}),
                "markers": row.get("markers", {}),
                "coefficients": [item.get("name") for item in row.get("coefficients", [])],
            }, ensure_ascii=False)
            if query_norm in _search_norm(searchable):
                result_hits.append({
                    "id": row.get("id"),
                    "outcome": row.get("outcome"),
                    "command_hints": row.get("command_hints", {}),
                    "stats": row.get("stats", {}),
                    "coefficients": row.get("coefficients", []),
                })

        excerpts: list[dict[str, Any]] = []
        path = root / file
        if path.exists():
            for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                if query_norm in _search_norm(line):
                    excerpts.append({"line": lineno, "text": line.strip()})
                    if len(excerpts) >= excerpts_per_file:
                        break

        if not structured_hit and not result_hits and not excerpts:
            continue

        score = (20 if structured_hit else 0) + 8 * len(result_hits) + len(excerpts)
        matches.append({
            "file": file,
            "score": score,
            "run_id": meta.get("run_id"),
            "task_ids": meta.get("task_ids", []),
            "markers": meta.get("markers", {}),
            "status": meta.get("status"),
            "paired_stata_files": meta.get("paired_stata_files", []),
            "result_hits": result_hits,
            "excerpts": excerpts,
        })

    matches.sort(key=lambda item: (-item["score"], item["file"]))
    return matches[:limit]


def search_history(
    index: dict[str, Any],
    query: str | None = None,
    branch: str | None = None,
    task: str | None = None,
    status: str | None = None,
    limit: int = 30,
    excerpts_per_file: int = 4,
) -> list[dict[str, Any]]:
    query_norm = _search_norm(query) if query else None
    branch_norm = _search_norm(branch) if branch else None
    task_norm = _search_norm(task) if task else None
    status_norm = _search_norm(status) if status else None
    root = Path(index["root"])
    matches: list[dict[str, Any]] = []

    for record in index.get("history_records", []):
        if branch_norm and branch_norm not in _search_norm(str(record.get("branch_id", ""))):
            continue

        task_values = [record.get("task_id")] + list(record.get("task_ids", []))
        if task_norm and not any(task_norm in _search_norm(str(value or "")) for value in task_values):
            continue

        record_status = str(record.get("status") or record.get("fields", {}).get("decision") or "")
        if status_norm and status_norm not in _search_norm(record_status):
            continue

        structured = json.dumps({
            "record_id": record.get("record_id"),
            "branch_id": record.get("branch_id"),
            "task_id": record.get("task_id"),
            "task_ids": record.get("task_ids", []),
            "title": record.get("title"),
            "status": record_status,
            "fields": record.get("fields", {}),
            "raw_fields": record.get("raw_fields", {}),
        }, ensure_ascii=False)
        structured_hit = not query_norm or query_norm in _search_norm(structured)

        excerpts: list[dict[str, Any]] = []
        if query_norm:
            path = root / str(record.get("file", ""))
            if path.exists() and path.suffix.lower() in {".md", ".log", ".smcl"}:
                for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                    if query_norm in _search_norm(line):
                        excerpts.append({"line": lineno, "text": line.strip()})
                        if len(excerpts) >= excerpts_per_file:
                            break

        if query_norm and not structured_hit and not excerpts:
            continue

        score = (20 if structured_hit and query_norm else 5) + len(excerpts)
        matches.append({
            **record,
            "score": score,
            "excerpts": excerpts,
        })

    matches.sort(key=lambda item: (-item["score"], str(item.get("file", "")), str(item.get("record_id", ""))))
    return matches[:limit]


def dataset_lineage(index: dict[str, Any], dataset: str) -> dict[str, Any]:
    datasets = index.get("datasets", {})
    key = _dataset_key(dataset)
    if key not in datasets:
        matches = [k for k in datasets if Path(k).name == Path(key).name]
        if len(matches) == 1:
            key = matches[0]
        else:
            return {"dataset": dataset, "found": False, "matches": matches}

    upstream: list[str] = []
    seen = {key}
    queue: deque[str] = deque(datasets[key].get("derived_from", []))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        upstream.append(current)
        for parent in datasets.get(current, {}).get("derived_from", []):
            queue.append(parent)

    downstream: list[str] = []
    for candidate, meta in datasets.items():
        if key in meta.get("derived_from", []):
            downstream.append(candidate)

    return {
        "dataset": key,
        "found": True,
        "metadata": datasets[key],
        "upstream": upstream,
        "direct_downstream": downstream,
    }
