from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

DATABASE_SCHEMA_VERSION = 1


def _norm(value: Any) -> str:
    return re.sub(r"[\\W_]+", "", str(value or "").casefold(), flags=re.UNICODE)


def _norm_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip().lstrip("./")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as stream:
                return [dict(row) for row in csv.DictReader(stream)]
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def _json_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw = str(value).strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if item not in (None, "")]
    except (json.JSONDecodeError, TypeError):
        pass
    return [item.strip() for item in raw.split(";") if item.strip()]


def _field(row: dict[str, Any], aliases: tuple[str, ...], default: str = "") -> str:
    normalized = {_norm(key): str(value or "").strip() for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(_norm(alias), "")
        if value:
            return value
    return default


def _number(value: Any, cast: type = int) -> int | float | None:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        return cast(float(raw)) if cast is int else cast(raw)
    except (TypeError, ValueError, OverflowError):
        return None


def _local_path_relative(canonical: str, relative_path: str, verified: bool) -> str | None:
    if not verified or not canonical or not relative_path:
        return None
    root_parts = [part for part in canonical.replace("/", "\\").split("\\") if part]
    file_parts = [part for part in relative_path.replace("/", "\\").split("\\") if part]
    if not root_parts or not file_parts:
        return None
    # Metadata paths are rooted at the dataset name (e.g. CFPS\\rawdata\\...),
    # while the canonical registry path already ends in CFPS. Strip only that exact prefix.
    if file_parts[0].casefold() == root_parts[-1].casefold():
        file_parts = file_parts[1:]
    return "\\".join(root_parts + file_parts)


def _year_hint(relative_path: str, dataset_id: str) -> int | None:
    parts = _norm_path(relative_path).split("/")
    for part in reversed(parts[:-1]):
        if re.fullmatch(r"(?:19|20)\\d{2}", part):
            return int(part)
    stem = Path(parts[-1]).stem if parts else ""
    prefix = re.escape(dataset_id)
    match = re.search(rf"{prefix}[_-]?(19\\d{{2}}|20\\d{{2}})", stem, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _metadata_paths(control_root: Path, dataset_row: dict[str, str]) -> tuple[list[Path], Path | None]:
    listed = _json_list(_field(dataset_row, ("metadata_files_json",)))
    file_metadata = [
        (control_root / Path(item.replace("\\", "/")))
        for item in listed
        if Path(item.replace("\\", "/")).name.casefold() == "files.csv"
    ]
    existing_files = [path for path in file_metadata if path.is_file()]
    variables_path = existing_files[0].parent / "variables.csv" if existing_files else None
    return existing_files, variables_path if variables_path and variables_path.is_file() else None


def _file_record(
    dataset_id: str,
    dataset_name: str,
    row: dict[str, str],
    source_file: str,
    source_row: int,
    canonical: str,
    verified: bool,
) -> dict[str, Any]:
    relative_path = _field(row, ("relative_path", "file", "filename", "file_name", "path"))
    extension = _field(row, ("extension", "ext")) or Path(relative_path).suffix.lower()
    return {
        "file_id": f"{dataset_id}:{_norm_path(relative_path)}",
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "relative_path": relative_path,
        "local_path_relative": _local_path_relative(canonical, relative_path, verified),
        "extension": extension.lower(),
        "size_mb": _number(_field(row, ("size_mb", "size")) , float),
        "n_obs": _number(_field(row, ("n_obs", "observations", "rows"))),
        "n_vars": _number(_field(row, ("n_vars", "variables", "columns"))),
        "extra": _field(row, ("extra", "notes")),
        "source_metadata_file": source_file,
        "source_row": source_row,
    }


def build_database_index(control_root: str | Path) -> dict[str, Any]:
    """Build a metadata-only index from gaolingxi/data control files.

    This function never opens raw microdata files and never recursively scans the
    data mirror. It reads only catalog/*.csv and metadata/<dataset>/*.csv.
    """
    root = Path(control_root).expanduser().resolve()
    datasets_path = root / "catalog" / "datasets.csv"
    registry_path = root / "catalog" / "data_registry.csv"
    if not datasets_path.is_file():
        raise FileNotFoundError(f"Missing database catalog: {datasets_path}")

    dataset_rows = _read_csv(datasets_path)
    registry_rows = _read_csv(registry_path)
    registry = {
        _field(row, ("dataset_id",)): row
        for row in registry_rows
        if _field(row, ("dataset_id",))
    }

    datasets: dict[str, dict[str, Any]] = {}
    files: list[dict[str, Any]] = []
    variables: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    unparsed_variable_rows = 0
    metadata_files_read: list[str] = []

    for dataset_row in dataset_rows:
        dataset_id = _field(dataset_row, ("dataset_id", "id"))
        if not dataset_id:
            continue
        dataset_name = _field(dataset_row, ("name", "dataset_name")) or dataset_id
        registry_row = registry.get(dataset_id, {})
        status = _field(registry_row, ("verification_status", "status")).upper() or "NOT_REGISTERED"
        verified = status == "VERIFIED"
        canonical = _field(registry_row, ("canonical_local_relpath", "canonical_path")) if verified else ""

        categories = _json_list(_field(dataset_row, ("categories_json", "categories")))
        metadata_file_paths, variables_path = _metadata_paths(root, dataset_row)
        shared_root_metadata = any(path.parent.name.casefold() == "_root_files" for path in metadata_file_paths)
        category_names = {_norm(Path(item).name) for item in categories}
        dataset_files: list[dict[str, Any]] = []
        file_lookup: dict[str, dict[str, Any]] = {}
        basename_lookup: dict[str, list[dict[str, Any]]] = {}
        for metadata_path in metadata_file_paths:
            rel_source = metadata_path.relative_to(root).as_posix()
            metadata_files_read.append(rel_source)
            metadata_rows = _read_csv(metadata_path)
            if shared_root_metadata:
                # _root_files metadata is shared by several one-file catalog entries.
                # Scope it to the exact filename recorded in this dataset's category.
                metadata_rows = [
                    row for row in metadata_rows
                    if _norm(Path(_field(row, ("relative_path", "file", "filename", "file_name", "path"))).name)
                    in category_names
                ]
            for row_number, row in enumerate(metadata_rows, start=2):
                record = _file_record(
                    dataset_id, dataset_name, row, rel_source, row_number, canonical, verified
                )
                if not record["relative_path"]:
                    continue
                dataset_files.append(record)
                files.append(record)
                file_lookup[_norm_path(record["relative_path"]).casefold()] = record
                basename = Path(record["relative_path"].replace("\\", "/")).name.casefold()
                basename_lookup.setdefault(basename, []).append(record)

        dataset_variables: list[dict[str, Any]] = []
        if variables_path:
            rel_source = variables_path.relative_to(root).as_posix()
            metadata_files_read.append(rel_source)
            for row_number, row in enumerate(_read_csv(variables_path), start=2):
                relative_path = _field(row, ("relative_path", "file", "filename", "file_name", "path"))
                variable = _field(row, ("variable", "variable_name", "var_name", "varname", "field", "column"))
                label = _field(row, ("label", "variable_label", "var_label", "description", "变量标签", "变量说明"))
                storage_type = _field(row, ("type", "storage_type", "variable_type", "stata_type", "dtype"))
                original_type = _field(row, ("original_type", "display_format", "format", "fmt"))
                if not variable:
                    unparsed_variable_rows += 1
                    continue

                linked_file = file_lookup.get(_norm_path(relative_path).casefold())
                if linked_file is None:
                    basename = Path(relative_path.replace("\\", "/")).name.casefold()
                    candidates = basename_lookup.get(basename, [])
                    if len(candidates) == 1:
                        linked_file = candidates[0]
                if shared_root_metadata and linked_file is None:
                    # Never attach shared root-file metadata to the wrong catalog dataset.
                    continue

                # XLSX sheet names are documented as "sheet:<name>" in label;
                # keep them as documentation entries, not as data variables.
                if label.casefold().startswith("sheet:") and not storage_type:
                    documents.append({
                        "dataset_id": dataset_id,
                        "dataset_name": dataset_name,
                        "relative_path": relative_path,
                        "title": variable,
                        "kind": "spreadsheet_sheet",
                        "sheet": label.split(":", 1)[1].strip(),
                        "source_metadata_file": rel_source,
                        "source_row": row_number,
                    })
                    continue

                year = _year_hint(relative_path, dataset_id)
                variable_record = {
                    "variable_id": f"{dataset_id}:{_norm_path(relative_path)}:{variable}",
                    "dataset_id": dataset_id,
                    "dataset_name": dataset_name,
                    "variable": variable,
                    "label": label,
                    "type": storage_type,
                    "original_type": original_type,
                    "relative_path": relative_path,
                    "local_path_relative": (
                        linked_file.get("local_path_relative") if linked_file else
                        _local_path_relative(canonical, relative_path, verified)
                    ),
                    "extension": (
                        linked_file.get("extension") if linked_file else Path(relative_path).suffix.lower()
                    ),
                    "n_obs": linked_file.get("n_obs") if linked_file else None,
                    "n_vars": linked_file.get("n_vars") if linked_file else None,
                    "year": year,
                    "registry_status": status,
                    "source_metadata_file": rel_source,
                    "source_row": row_number,
                }
                dataset_variables.append(variable_record)
                variables.append(variable_record)

        extension_counts: dict[str, int] = {}
        for record in dataset_files:
            ext = record.get("extension") or "(unknown)"
            extension_counts[ext] = extension_counts.get(ext, 0) + 1

        datasets[dataset_id] = {
            "dataset_id": dataset_id,
            "name": dataset_name,
            "release_tag": _field(dataset_row, ("release_tag",)),
            "release_url": _field(dataset_row, ("release_url",)),
            "role": _field(dataset_row, ("role",)),
            "categories": categories,
            "verification_status": status,
            "canonical_local_relpath": canonical or None,
            "original_files": _number(_field(dataset_row, ("original_files",))),
            "original_bytes": _number(_field(dataset_row, ("original_bytes",))),
            "assets": _number(_field(dataset_row, ("assets",))),
            "asset_bytes": _number(_field(dataset_row, ("asset_bytes",))),
            "files_count": len(dataset_files),
            "variable_count": len(dataset_variables),
            "extension_counts": extension_counts,
            "metadata_files": [path.relative_to(root).as_posix() for path in metadata_file_paths]
            + ([variables_path.relative_to(root).as_posix()] if variables_path else []),
        }

    return {
        "schema_version": DATABASE_SCHEMA_VERSION,
        "root": root.as_posix(),
        "datasets": datasets,
        "files": files,
        "variables": variables,
        "documents": documents,
        "summary": {
            "datasets": len(datasets),
            "files": len(files),
            "variables": len(variables),
            "documentation_entries": len(documents),
            "unparsed_variable_rows": unparsed_variable_rows,
            "metadata_files_read": len(set(metadata_files_read)),
            "registered_verified": sum(
                1 for item in datasets.values() if item["verification_status"] == "VERIFIED"
            ),
            "not_verified_or_unregistered": sum(
                1 for item in datasets.values() if item["verification_status"] != "VERIFIED"
            ),
        },
    }


def save_database_index(index: dict[str, Any], control_root: str | Path, output: str | Path | None = None) -> Path:
    root = Path(control_root).expanduser().resolve()
    target = Path(output).expanduser().resolve() if output else root / ".statagraph" / "database_index.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_database_index(control_root: str | Path, rebuild: bool = False) -> dict[str, Any]:
    root = Path(control_root).expanduser().resolve()
    target = root / ".statagraph" / "database_index.json"
    if target.is_file() and not rebuild:
        index = json.loads(target.read_text(encoding="utf-8"))
        if index.get("schema_version") == DATABASE_SCHEMA_VERSION:
            return index
    index = build_database_index(root)
    save_database_index(index, root)
    return index


def _search_score(query: str, fields: list[str]) -> int:
    q = _norm(query)
    if not q:
        return 0
    normalized = [_norm(value) for value in fields if value]
    if any(value == q for value in normalized):
        return 100
    if any(q in value for value in normalized):
        return 80
    tokens = [_norm(token) for token in re.split(r"\s+", query.strip()) if _norm(token)]
    if len(tokens) > 1 and all(any(token in value for value in normalized) for token in tokens):
        return 50
    return 0


def search_databases(index: dict[str, Any], query: str = "", limit: int = 20) -> list[dict[str, Any]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    for dataset in index.get("datasets", {}).values():
        fields = [
            dataset.get("dataset_id", ""),
            dataset.get("name", ""),
            dataset.get("release_tag", ""),
            dataset.get("role", ""),
            *dataset.get("categories", []),
        ]
        score = _search_score(query, fields) if query else 1
        if score:
            rows.append((score, dataset))
    rows.sort(key=lambda item: (-item[0], item[1].get("name", "")))
    return [dict(item, search_score=score) for score, item in rows[: max(0, limit)]]


def search_database_files(
    index: dict[str, Any], query: str = "", dataset_id: str | None = None, limit: int = 30
) -> list[dict[str, Any]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    for record in index.get("files", []):
        if dataset_id and record.get("dataset_id", "").casefold() != dataset_id.casefold():
            continue
        fields = [
            record.get("relative_path", ""),
            record.get("extension", ""),
            record.get("dataset_id", ""),
            record.get("dataset_name", ""),
            record.get("extra", ""),
        ]
        score = _search_score(query, fields) if query else 1
        if score:
            rows.append((score, record))
    rows.sort(key=lambda item: (-item[0], item[1].get("dataset_name", ""), item[1].get("relative_path", "")))
    return [dict(item, search_score=score) for score, item in rows[: max(0, limit)]]


def search_database_variables(
    index: dict[str, Any],
    query: str,
    dataset_id: str | None = None,
    file_query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    for record in index.get("variables", []):
        if dataset_id and record.get("dataset_id", "").casefold() != dataset_id.casefold():
            continue
        if file_query and _search_score(file_query, [record.get("relative_path", "")]) == 0:
            continue
        score = _search_score(query, [
            record.get("variable", ""),
            record.get("label", ""),
            record.get("type", ""),
            record.get("original_type", ""),
            record.get("relative_path", ""),
            record.get("dataset_id", ""),
            record.get("dataset_name", ""),
        ])
        if score:
            rows.append((score, record))
    rows.sort(key=lambda item: (
        -item[0],
        item[1].get("dataset_name", ""),
        item[1].get("year") or 0,
        item[1].get("relative_path", ""),
        item[1].get("variable", ""),
    ))
    return [dict(item, search_score=score) for score, item in rows[: max(0, limit)]]


def database_profile(index: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    dataset = index.get("datasets", {}).get(dataset_id)
    if dataset is None:
        return {"found": False, "dataset_id": dataset_id}
    files = [row for row in index.get("files", []) if row.get("dataset_id") == dataset_id]
    variables = [row for row in index.get("variables", []) if row.get("dataset_id") == dataset_id]
    years = sorted({row["year"] for row in variables if row.get("year") is not None})
    return {
        "found": True,
        **dataset,
        "years_inferred_from_file_paths": years,
        "files": files,
        "variable_examples": variables[:30],
        "variable_metadata_source": "metadata/variables.csv",
        "note": "Years are filename/path hints, not independently verified survey-wave definitions.",
    }
