# AGENTS.md — StataGraph

StataGraph is a research-aware code/data/log lineage tool for Stata projects.

## Goal

Help humans and coding agents recover the structure and experiment history of empirical Stata projects without rereading the repository from scratch.

Primary graph:

`raw data -> cleaned data -> analysis data -> variables -> regressions -> tables -> research logs`

## Priorities

1. Practical usefulness on real `.do` / `.ado` / `.log` projects.
2. Correct locations and raw evidence when a construct is recognized.
3. Data lineage, variable lineage, regression specification, output provenance, and branch-result history.
4. Stable machine-readable output for a later MCP layer.
5. Parser completeness only when it improves the above.

## Log rule

Branch logs are durable research history. StataGraph should make it easy to answer:

- Has this specification already been run?
- Which TASK_ID/log contains a variable, FE, cluster rule, sample, or result?
- What coefficient / SE / p-value / N did a branch produce?
- Which `.do` file corresponds to the log?
- Which runs stopped with a Stata `r(#)` error?

Use a lightweight structured index for metadata/results and search the original raw log on demand. Do not duplicate every full log into `.statagraph/index.json`.

Temporary branch code may be discarded by the research workflow; the corresponding branch log should remain searchable. StataGraph indexes logs but never rewrites or deletes them.

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

## Research workflow compatibility

StataGraph must work with the repository workflow defined in `gaolingxi/research-project-orchestrator`:

- source/raw-data preparation
- project-ready analysis data
- model regression: mainline + branches
- branch logs retained even when temporary branch code is discarded
- promoted mainline results retain formal code + log + outputs

Future Markdown indexing should treat `research_logs/` and `BRANCH_REGISTRY.md` as durable research history, not rewrite or delete them.

## Development sequence

- V0.1: parser + code/data index + CLI + tests
- V0.2: Stata log index/search + result/error recovery + later Markdown research-log index
- V0.3: MCP server for OpenCode/Codex/Claude-compatible clients
- V0.4: optional Tree-sitter backend and incremental indexing

Prefer small changes driven by failures on actual Stata repositories.
