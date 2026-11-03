from __future__ import annotations

import re
from pathlib import Path
from typing import Any

LOG_SUFFIXES = {".log", ".smcl"}

_MARKER_RE = re.compile(r"^([A-Z][A-Z0-9_]{1,})\s*=\s*(.+)$")
_COEF_HEADER_RE = re.compile(r"^\s*([^|]+?)\s*\|\s*Coefficient\s+Std\.?\s*err\.?", re.I)
_COEF_ROW_RE = re.compile(
    r"^\s*([^|]+?)\s*\|\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"(?:([0-9]*\.?[0-9]+)|<\s*([0-9]*\.?[0-9]+))"
)
_RC_RE = re.compile(r"^r\((\d+)\);\s*$", re.I)
_NUMBER_OBS_RE = re.compile(r"Number of obs\s*=\s*([0-9,]+)", re.I)
_CLUSTER_RE = re.compile(r"Number of clusters\s*\(([^)]+)\)\s*=\s*([0-9,]+)", re.I)
_R2_RE = re.compile(r"(?<!Within )R-squared\s*=\s*([-+0-9.eE]+)", re.I)
_WITHIN_R2_RE = re.compile(r"Within R-sq\.\s*=\s*([-+0-9.eE]+)", re.I)
_OPENED_RE = re.compile(r"opened on:\s*(.+)$", re.I)
_CLOSED_RE = re.compile(r"closed on:\s*(.+)$", re.I)


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def _parse_markers(line: str) -> dict[str, str]:
    stripped = line.strip()
    if not stripped or stripped.startswith((".", ">")):
        return {}

    result: dict[str, str] = {}
    for chunk in stripped.split(";"):
        match = _MARKER_RE.match(chunk.strip())
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def _command_hints(command: str | None) -> dict[str, str]:
    if not command:
        return {}
    result: dict[str, str] = {}
    for key in ("table", "outcome", "label", "sample", "oldn"):
        match = re.search(rf"\b{key}\(\s*(?:\"([^\"]+)\"|([^\)]+))\s*\)", command, re.I)
        if match:
            result[key] = (match.group(1) or match.group(2) or "").strip()
    match = re.search(r"\babsorb\((.*?)\)", command, re.I)
    if match:
        result["fe"] = match.group(1).strip()
    match = re.search(r"\bvce\(cluster\s+([^\)]+)\)", command, re.I)
    if match:
        result["cluster"] = match.group(1).strip()
    return result


def _run_id_from_name(path: Path) -> str:
    stem = path.stem
    return stem.split("_", 1)[0] if stem else ""


def parse_log_file(path: Path, root: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    markers: dict[str, str] = {}
    marker_events: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    opened_on: str | None = None
    closed_on: str | None = None

    last_command: dict[str, Any] | None = None
    stats: dict[str, Any] = {}
    current_result: dict[str, Any] | None = None
    seen_coefficient = False
    previous_nonempty = ""

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()

        opened = _OPENED_RE.search(line)
        if opened:
            opened_on = opened.group(1).strip()
        closed = _CLOSED_RE.search(line)
        if closed:
            closed_on = closed.group(1).strip()

        if line.startswith(". "):
            command = line[2:].strip()
            last_command = {"line": lineno, "command": command}
            commands.append(last_command)
        elif line.startswith("> ") and last_command is not None:
            last_command["command"] += " " + line[2:].strip()

        found_markers = _parse_markers(line)
        if found_markers:
            for key, value in found_markers.items():
                markers[key] = value
                marker_events.append({"line": lineno, "key": key, "value": value})

        obs = _NUMBER_OBS_RE.search(line)
        if obs:
            stats["N"] = _int(obs.group(1))
        cluster = _CLUSTER_RE.search(line)
        if cluster:
            stats["cluster_variable"] = cluster.group(1).strip()
            stats["clusters"] = _int(cluster.group(2))
        within = _WITHIN_R2_RE.search(line)
        if within:
            stats["within_r2"] = _float(within.group(1))
        r2 = _R2_RE.search(line)
        if r2 and "Within R-sq." not in line:
            stats["r2"] = _float(r2.group(1))

        rc = _RC_RE.match(stripped)
        if rc:
            errors.append({
                "line": lineno,
                "rc": int(rc.group(1)),
                "message": previous_nonempty,
            })

        header = _COEF_HEADER_RE.match(line)
        if header:
            current_result = {
                "file": rel,
                "line": lineno,
                "run_id": _run_id_from_name(path),
                "outcome": header.group(1).strip(),
                "command": last_command["command"] if last_command else None,
                "command_line": last_command["line"] if last_command else None,
                "command_hints": _command_hints(last_command["command"] if last_command else None),
                "markers": dict(markers),
                "stats": dict(stats),
                "coefficients": [],
            }
            seen_coefficient = False
            continue

        if current_result is not None:
            coefficient = _COEF_ROW_RE.match(line)
            if coefficient:
                name = coefficient.group(1).strip()
                p_value = _float(coefficient.group(4) or coefficient.group(5))
                current_result["coefficients"].append({
                    "name": name,
                    "b": _float(coefficient.group(2)),
                    "se": _float(coefficient.group(3)),
                    "stat": _float(coefficient.group(4)) if False else _float(coefficient.group(4)),
                    "p": p_value,
                })
                # group(4) is p in the regex. Recompute the test statistic from b/se below.
                row = current_result["coefficients"][-1]
                if row["b"] is not None and row["se"] not in (None, 0):
                    row["stat"] = row["b"] / row["se"]
                seen_coefficient = True
                continue

            if seen_coefficient and stripped and set(stripped) <= {"-", "+"}:
                results.append(current_result)
                current_result = None
                seen_coefficient = False
                stats = {}
                continue

        if stripped:
            previous_nonempty = stripped

    if current_result is not None and current_result["coefficients"]:
        results.append(current_result)

    task_ids = sorted({event["value"] for event in marker_events if event["key"] == "TASK_ID"})
    status = "error" if errors else ("closed" if closed_on else "open_or_unknown")

    return {
        "file": rel,
        "run_id": _run_id_from_name(path),
        "opened_on": opened_on,
        "closed_on": closed_on,
        "status": status,
        "task_ids": task_ids,
        "markers": markers,
        "marker_events": marker_events,
        "command_count": len(commands),
        "result_count": len(results),
        "error_count": len(errors),
        "errors": errors,
        "results": results,
    }
