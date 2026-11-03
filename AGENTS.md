# AGENTS.md — StataGraph

StataGraph is a research-aware code/data/log/experiment-history tool with a metadata-only database graph for Stata projects.

## Goal

Help humans and coding agents recover the structure and experiment history of empirical Stata projects without rereading the repository from scratch.

Primary graph:

`raw data -> cleaned data -> analysis data -> variables -> regressions -> tables -> experiment history`

## Priorities

1. Practical usefulness on real `.do` / `.ado` / `.log` projects.
2. Correct locations and raw evidence when a construct is recognized.
3. Data lineage, variable lineage, regression specification, output provenance, and branch-result history.
4. Unified research-history search across Stata logs, Markdown branch notes, and branch registries.
5. Stable machine-readable output for a later MCP layer.
6. Parser completeness only when it improves the above.

## Research-history rule

Branch history is durable even when temporary code is disposable. The durable sources are:

- Stata `.log` / `.smcl`
- `research_logs/*.md`, `branch_logs/*.md`, `BRANCH.md`, `BRANCH_LOG.md`
- `BRANCH_REGISTRY.md`

StataGraph should make it easy to answer:

- Has this specification already been run?
- Which branch/TASK_ID contains a variable, FE, cluster rule, sample, or result?
- What coefficient / SE / p-value / N did a branch produce?
- Why was a branch kept, closed, dropped, or promoted?
- Which `.do` file corresponds to the log?
- Which Markdown note and registry row describe the same experiment?
- Which runs stopped with a Stata `r(#)` error?

Use a lightweight structured index for metadata/results and search original source files on demand. Do not duplicate every full log or Markdown file into `.statagraph/index.json`.

Records sharing a `BRANCH_ID` or `TASK_ID` should be linked through `related_records`. Search should be organized around the research question or experiment identity, not around remembering filenames.

Temporary branch code may be discarded by the research workflow; retained log/Markdown/registry evidence must remain searchable. StataGraph indexes history but never rewrites or deletes source evidence.

## Non-goals

- Full Stata language implementation.
- Executing Stata.
- Replacing Git/research logs with an internal memory system.
- Treating every textual warning as a runtime error; Stata `r(#)` evidence is the primary runtime-error signal.
- Building generic software call graphs when no research use case depends on them.
- Engineering a checker/automation stack before the index proves useful.

## Parser rule

Use dependency-free tolerant parsing first. Do not switch the whole project to Tree-sitter merely for architectural purity. Add a Tree-sitter backend only after real-project tests show a concrete accuracy gain.

Existing `tree-sitter-stata` projects may be studied or optionally integrated later, but incomplete macro/options support must not block practical indexing.

## Database graph rule

The database graph is a metadata-only layer over the user's central `gaolingxi/data` control repository.

Allowed inputs:
- `catalog/datasets.csv` for dataset identity and release metadata
- `catalog/data_registry.csv` for current local path and verification status
- `metadata/<dataset>/files.csv` for file inventory
- sibling `metadata/<dataset>/variables.csv` for variable names, labels, storage types, and original display formats

Hard boundaries:
1. Read these metadata files only. Do not open raw microdata files, inspect observation-level values, or sample records to build the database index.
2. Do not recursively scan the local data mirror to guess paths. Resolve data identity from `dataset_id`; the only current local path authority is `catalog/data_registry.csv`.
3. Expose a local path only when `verification_status=VERIFIED` and `canonical_local_relpath` is present. `BLOCKED`, `REVIEW`, `UNRESOLVED`, missing, and unregistered entries may remain searchable as catalog metadata but are never approved local inputs.
4. Keep the generated `.statagraph/database_index.json` as a local ignored cache. Do not commit it or write it into the raw data mirror.
5. Preserve source metadata file and row references for every result.
6. A year parsed from a file path is only a search hint. Do not treat it as proof of survey wave or cross-wave comparability.
7. Variable-name/label similarity is not evidence that two variables share the same definition, unit, respondent, or statistical universe. Preserve missing labels as missing; do not invent definitions.
8. The database indexer must never modify `gaolingxi/data` catalog files, registry rows, metadata, or raw data.

The database graph is separate from a project's research graph. A later MCP layer may query both and link an original database variable to a project variable only when the source evidence supports the match.

## Research workflow compatibility

StataGraph must work with the repository workflow defined in `gaolingxi/research-project-orchestrator`:

- source/raw-data preparation
- project-ready analysis data
- model regression: mainline + branches
- branch logs retained even when temporary branch code is discarded
- branch Markdown stores interpretation/decision when available
- `BRANCH_REGISTRY.md` provides the compact project map
- promoted mainline results retain formal code + log + outputs

## Development sequence

- V0.1: Stata code/data lineage + CLI + tests
- V0.2: Stata log index/search + result/error recovery
- V0.2.1: unified log + research Markdown + branch-registry history
- V0.2.2: metadata-only microdata database graph + dataset/file/variable search
- V0.3: MCP server for OpenCode/Codex/Claude-compatible clients, querying both project and database graphs
- V0.4: optional Tree-sitter backend and incremental indexing

Prefer small changes driven by failures on actual Stata and microdata repositories.
