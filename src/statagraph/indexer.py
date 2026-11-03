from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from .parser import parse_stata_file

STATA_SUFFIXES = {".do", ".ado", ".mata"}
SKIP_DIRS = {".git", ".statagraph", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}


def _norm_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def _dataset_key(value: str) -> str:
    return _norm_path(value)


def scan_stata_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in STATA_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return sorted(files)


def build_index(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"Project directory not found: {root_path}")

    parsed_files = [parse_stata_file(path, root_path) for path in scan_stata_files(root_path)]

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

        # Coarse but useful file-level lineage: every dataset written by a do-file
        # is downstream of datasets read/merged/appended by that same file.
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

    return {
        "schema_version": 1,
        "root": root_path.as_posix(),
        "files": {item["file"]: item for item in parsed_files},
        "calls": calls,
        "datasets": dict(datasets),
        "variables": dict(variables),
        "regressions": regressions,
        "outputs": outputs,
        "macros": macros,
        "programs": programs,
        "summary": {
            "stata_files": len(parsed_files),
            "datasets": len(datasets),
            "variables": len(variables),
            "regressions": len(regressions),
            "outputs": len(outputs),
            "calls": len(calls),
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
        return json.loads(target.read_text(encoding="utf-8"))
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


def dataset_lineage(index: dict[str, Any], dataset: str) -> dict[str, Any]:
    datasets = index.get("datasets", {})
    key = _dataset_key(dataset)
    if key not in datasets:
        # Convenient basename fallback when stored path includes macros/folders.
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
