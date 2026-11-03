from __future__ import annotations

import re
from pathlib import Path
from typing import Any

HISTORY_FILENAMES = {"branch_registry.md", "branch_log.md", "branch.md"}
HISTORY_DIR_NAMES = {
    "research_logs",
    "research_log",
    "research-logs",
    "research-log",
    "branch_logs",
    "branch_log",
    "branch-logs",
    "branch-log",
    "研究日志",
    "支线日志",
}

FIELD_ALIASES = {
    "branch_id": {"branch_id", "branch id", "id", "支线id", "支线_id", "支线编号"},
    "task_id": {"task_id", "task id", "任务id", "任务_id"},
    "date": {"date", "日期", "time", "时间"},
    "base_data": {"base_data", "base data", "data", "dataset", "数据", "基础数据", "项目数据"},
    "baseline": {"baseline", "base_spec", "base spec", "基准", "基准规格", "基于"},
    "purpose": {"purpose", "goal", "目的", "目标", "支线", "name", "名称"},
    "change": {"change", "changes", "改动", "调整", "变化"},
    "status": {"status", "状态"},
    "result": {"result", "results", "结果"},
    "conclusion": {"conclusion", "结论"},
    "decision": {"decision", "决策", "处理"},
    "promoted_to": {"promoted_to", "promoted to", "晋升", "晋升到", "主线位置"},
    "next_step": {"next_step", "next step", "下一步"},
    "x": {"x", "解释变量", "核心x"},
    "y": {"y", "被解释变量", "因变量", "结果变量"},
    "fe": {"fe", "fixed effects", "固定效应"},
    "cluster": {"cluster", "clustering", "聚类", "聚类层级"},
}


def _norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold().replace("：", ":"))


_ALIAS_LOOKUP: dict[str, str] = {}
for canonical, aliases in FIELD_ALIASES.items():
    for alias in aliases:
        _ALIAS_LOOKUP[_norm_key(alias)] = canonical


def _canonical_key(value: str) -> str | None:
    key = _norm_key(value).rstrip(":")
    return _ALIAS_LOOKUP.get(key)


def is_history_markdown(path: Path, root: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    rel = path.relative_to(root)
    if path.name.casefold() in HISTORY_FILENAMES:
        return True
    return any(part.casefold() in HISTORY_DIR_NAMES for part in rel.parts[:-1])


def scan_history_markdown(root: Path, skip_dirs: set[str] | None = None) -> list[Path]:
    skip_dirs = skip_dirs or set()
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        if is_history_markdown(path, root):
            files.append(path)
    return sorted(files)


def _strip_inline(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'", "`"}:
        return value[1:-1].strip()
    return value


def _parse_front_matter(lines: list[str]) -> tuple[dict[str, str], int]:
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fields: dict[str, str] = {}
    for i in range(1, len(lines)):
        line = lines[i]
        if line.strip() == "---":
            return fields, i + 1
        match = re.match(r"^([^:#][^:]*):\s*(.*)$", line)
        if match:
            canonical = _canonical_key(match.group(1))
            if canonical:
                fields[canonical] = _strip_inline(match.group(2))
    return fields, 0


def _parse_key_values(lines: list[str], start: int = 0) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        match = re.match(r"^(?:[-*]\s*)?([^:：]{1,40})[:：]\s*(.+)$", stripped)
        if not match:
            continue
        canonical = _canonical_key(match.group(1))
        if canonical:
            fields[canonical] = _strip_inline(match.group(2))
    return fields


def _heading_title(lines: list[str], fallback: str) -> str:
    for line in lines:
        match = re.match(r"^#{1,3}\s+(.+?)\s*$", line.strip())
        if match:
            return match.group(1).strip()
    return fallback


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _parse_registry_tables(lines: list[str], file: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    i = 0
    while i + 1 < len(lines):
        if "|" not in lines[i] or "|" not in lines[i + 1]:
            i += 1
            continue
        headers = _split_table_row(lines[i])
        separator = _split_table_row(lines[i + 1])
        if len(headers) < 2 or len(headers) != len(separator) or not _is_separator_row(separator):
            i += 1
            continue

        j = i + 2
        while j < len(lines) and "|" in lines[j] and lines[j].strip():
            cells = _split_table_row(lines[j])
            if len(cells) != len(headers):
                break
            raw_fields = dict(zip(headers, cells))
            normalized: dict[str, str] = {}
            for key, value in raw_fields.items():
                canonical = _canonical_key(key)
                if canonical and value:
                    normalized[canonical] = _strip_inline(value)
            if normalized:
                branch_id = normalized.get("branch_id") or normalized.get("task_id") or f"row-{j + 1}"
                rows.append({
                    "source_type": "branch_registry_row",
                    "file": file,
                    "line": j + 1,
                    "record_id": branch_id,
                    "title": normalized.get("purpose") or branch_id,
                    "fields": normalized,
                    "raw_fields": raw_fields,
                })
            j += 1
        i = max(j, i + 1)
    return rows


def parse_history_markdown(path: Path, root: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    front, start = _parse_front_matter(lines)
    fields = {**_parse_key_values(lines, start=start), **front}
    title = _heading_title(lines, path.stem)
    branch_id = fields.get("branch_id")
    task_id = fields.get("task_id")
    record_id = branch_id or task_id or path.stem

    registry_rows: list[dict[str, Any]] = []
    if path.name.casefold() == "branch_registry.md":
        registry_rows = _parse_registry_tables(lines, rel)

    return {
        "source_type": "research_markdown",
        "file": rel,
        "record_id": record_id,
        "title": title,
        "fields": fields,
        "registry_rows": registry_rows,
    }
