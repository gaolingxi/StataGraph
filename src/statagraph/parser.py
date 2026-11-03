from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REGRESSION_COMMANDS = {
    "reg",
    "regress",
    "reghdfe",
    "xtreg",
    "areg",
    "ivreg2",
    "ivreghdfe",
    "csdid",
    "didregress",
    "xtivreg2",
    "poisson",
    "ppmlhdfe",
    "logit",
    "probit",
}

OUTPUT_COMMANDS = {"esttab", "estout", "outreg2", "collect", "putexcel"}
PREFIXES = {"capture", "cap", "quietly", "qui", "noisily", "noi"}
IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
MACRO_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?|`([^']+)'" )


def _strip_block_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _logical_lines(text: str) -> list[tuple[int, str]]:
    text = _strip_block_comments(text)
    result: list[tuple[int, str]] = []
    buffer = ""
    start = 1

    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("*") or stripped.startswith("//"):
            continue

        # Preserve URLs/quoted text reasonably well; only strip trailing // comments.
        line = re.sub(r"\s+//.*$", "", raw).rstrip()
        if not buffer:
            start = lineno

        if line.rstrip().endswith("///"):
            buffer += line.rstrip()[:-3] + " "
            continue

        buffer += line
        if buffer.strip():
            result.append((start, buffer.strip()))
        buffer = ""

    if buffer.strip():
        result.append((start, buffer.strip()))
    return result


def _unquote(value: str) -> str:
    value = value.strip().rstrip(",")
    if len(value) >= 2 and value[0] in {'"', "'"} and value[-1] == value[0]:
        return value[1:-1]
    return value


def _extract_path_after_keyword(command: str, keyword: str) -> str | None:
    match = re.search(rf"\b{keyword}\b\s+(?:using\s+)?(\"[^\"]+\"|'[^']+'|[^,\s]+)", command, flags=re.I)
    return _unquote(match.group(1)) if match else None


def _extract_using_path(command: str) -> str | None:
    match = re.search(r"\busing\b\s+(\"[^\"]+\"|'[^']+'|[^,\s]+)", command, flags=re.I)
    return _unquote(match.group(1)) if match else None


def _macro_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in MACRO_RE.finditer(text):
        name = match.group(1) or match.group(2)
        if name and name not in refs:
            refs.append(name)
    return refs


def _identifiers(expr: str) -> list[str]:
    stop = {
        "if", "in", "using", "clear", "replace", "float", "double", "long", "int", "byte",
        "true", "false", "missing", "ln", "log", "exp", "sqrt", "abs", "cond", "min", "max",
    }
    names: list[str] = []
    for token in IDENT_RE.findall(expr):
        low = token.lower()
        if low in stop or token.isdigit():
            continue
        if token not in names:
            names.append(token)
    return names


def _strip_prefixes(command: str) -> str:
    text = command.strip()
    while True:
        match = re.match(r"^([A-Za-z]+)\s+", text)
        if not match or match.group(1).lower() not in PREFIXES:
            return text
        text = text[match.end():].lstrip()


def _strip_by_prefix(command: str) -> str:
    """Strip Stata by/bysort prefixes so the underlying command is indexed.

    Examples:
        bysort hhid: egen x = max(y)
        by hhid (year): gen first = _n == 1
    """
    match = re.match(r"^(?:by|bysort)\b[^:]*:\s*(.+)$", command, flags=re.I)
    return match.group(1).strip() if match else command


def _split_main_options(command: str) -> tuple[str, str]:
    # In Stata, local macros use `name' syntax. The apostrophe therefore must
    # not be treated as a string delimiter. Double quotes are Stata's normal
    # string/path delimiter for the cases relevant to option splitting.
    in_double_quotes = False
    paren_depth = 0
    for i, ch in enumerate(command):
        if ch == '"':
            in_double_quotes = not in_double_quotes
        elif not in_double_quotes:
            if ch == "(":
                paren_depth += 1
            elif ch == ")" and paren_depth:
                paren_depth -= 1
            elif ch == "," and paren_depth == 0:
                return command[:i].strip(), command[i + 1 :].strip()
    return command.strip(), ""


def _parse_regression(command: str, file: str, line: int, estimate_name: str | None = None) -> dict[str, Any] | None:
    normalized = _strip_by_prefix(_strip_prefixes(command))
    main, options = _split_main_options(normalized)
    tokens = main.split()
    if not tokens:
        return None

    estimator = tokens[0].lower()
    if estimator not in REGRESSION_COMMANDS:
        return None

    payload = tokens[1:]
    y = payload[0] if payload else None
    rhs = payload[1:] if len(payload) > 1 else []

    # Stop simple RHS tokenization at common sample/weight clauses.
    clean_rhs: list[str] = []
    for token in rhs:
        if token.lower() in {"if", "in"} or token.startswith("["):
            break
        clean_rhs.append(token)

    absorb = None
    cluster = None
    match = re.search(r"\babsorb\((.*?)\)", options, flags=re.I)
    if match:
        absorb = match.group(1).strip()
    match = re.search(r"\bvce\(cluster\s+([^\)]+)\)", options, flags=re.I)
    if match:
        cluster = match.group(1).strip()
    else:
        match = re.search(r"\bcluster\((.*?)\)", options, flags=re.I)
        if match:
            cluster = match.group(1).strip()

    return {
        "file": file,
        "line": line,
        "estimator": estimator,
        "estimate_name": estimate_name,
        "y": y,
        "rhs": clean_rhs,
        "macro_refs": _macro_refs(normalized),
        "fe": absorb,
        "cluster": cluster,
        "options": options,
        "raw": command,
    }


def parse_stata_file(path: Path, root: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    parsed: dict[str, Any] = {
        "file": rel,
        "calls": [],
        "data_reads": [],
        "data_writes": [],
        "data_merges": [],
        "data_appends": [],
        "variables": [],
        "macros": [],
        "programs": [],
        "regressions": [],
        "outputs": [],
    }

    for line, original in _logical_lines(text):
        command = _strip_by_prefix(_strip_prefixes(original))
        lower = command.lower()

        # eststo name: <regression>
        eststo = re.match(r"^eststo\s+([^:\s]+)\s*:\s*(.+)$", command, flags=re.I)
        if eststo:
            regression = _parse_regression(eststo.group(2), rel, line, estimate_name=eststo.group(1))
            if regression:
                parsed["regressions"].append(regression)
            continue

        first = command.split(None, 1)[0].lower() if command.split() else ""

        if first in {"do", "run", "include"}:
            target = _extract_path_after_keyword(command, first)
            if target:
                parsed["calls"].append({"line": line, "kind": first, "target": target, "raw": original})
            continue

        if first == "use":
            # Stata supports both `use "file.dta"` and
            # `use varlist using "file.dta"`; prefer the explicit using path.
            target = _extract_using_path(command) or _extract_path_after_keyword(command, "use")
            if target:
                parsed["data_reads"].append({"line": line, "path": target, "kind": "use", "raw": original})
            continue

        if first == "save":
            target = _extract_path_after_keyword(command, "save")
            if target:
                parsed["data_writes"].append({"line": line, "path": target, "kind": "save", "raw": original})
            continue

        if first == "merge":
            target = _extract_using_path(command)
            if target:
                parsed["data_merges"].append({"line": line, "path": target, "kind": "merge", "raw": original})
            continue

        if first == "append":
            target = _extract_using_path(command)
            if target:
                parsed["data_appends"].append({"line": line, "path": target, "kind": "append", "raw": original})
            continue

        if first == "import":
            target = _extract_using_path(command)
            if not target:
                match = re.search(r"^import\s+\w+\s+(\"[^\"]+\"|'[^']+'|[^,\s]+)", command, flags=re.I)
                target = _unquote(match.group(1)) if match else None
            if target:
                parsed["data_reads"].append({"line": line, "path": target, "kind": "import", "raw": original})
            continue

        if first == "export":
            target = _extract_using_path(command)
            if not target:
                match = re.search(r"^export\s+\w+\s+(\"[^\"]+\"|'[^']+'|[^,\s]+)", command, flags=re.I)
                target = _unquote(match.group(1)) if match else None
            if target:
                parsed["data_writes"].append({"line": line, "path": target, "kind": "export", "raw": original})
            continue

        macro = re.match(r"^(global|local)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(.*)$", command, flags=re.I)
        if macro:
            parsed["macros"].append({
                "line": line,
                "scope": macro.group(1).lower(),
                "name": macro.group(2),
                "value": macro.group(3).strip(),
                "raw": original,
            })
            continue

        program = re.match(r"^program\s+define\s+([A-Za-z_][A-Za-z0-9_]*)", command, flags=re.I)
        if program:
            parsed["programs"].append({"line": line, "name": program.group(1), "raw": original})
            continue

        var = re.match(r"^(gen|generate|egen|replace)\s+(?:(?:byte|int|long|float|double|str\d*)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", command, flags=re.I)
        if var:
            expr = var.group(3).strip()
            parsed["variables"].append({
                "line": line,
                "action": var.group(1).lower(),
                "name": var.group(2),
                "expression": expr,
                "depends_on": [x for x in _identifiers(expr) if x != var.group(2)],
                "macro_refs": _macro_refs(expr),
                "raw": original,
            })
            continue

        rename = re.match(r"^rename\s+([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)", command, flags=re.I)
        if rename:
            parsed["variables"].append({
                "line": line,
                "action": "rename",
                "name": rename.group(2),
                "depends_on": [rename.group(1)],
                "macro_refs": [],
                "raw": original,
            })
            continue

        regression = _parse_regression(command, rel, line)
        if regression:
            parsed["regressions"].append(regression)
            continue

        if first in OUTPUT_COMMANDS or lower.startswith("collect "):
            parsed["outputs"].append({
                "line": line,
                "command": first,
                "using": _extract_using_path(command),
                "macro_refs": _macro_refs(command),
                "raw": original,
            })

    return parsed
