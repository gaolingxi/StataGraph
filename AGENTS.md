# AGENTS.md — StataGraph

StataGraph is a research-aware code/data lineage tool for Stata projects.

## Goal

Help humans and coding agents recover the structure of empirical Stata projects without rereading the repository from scratch.

Primary graph:

`raw data -> cleaned data -> analysis data -> variables -> regressions -> tables -> research logs`

## Priorities

1. Practical usefulness on real `.do` / `.ado` projects.
2. Correct locations and raw commands when a construct is recognized.
3. Data lineage, variable lineage, regression specification, and output provenance.
4. Stable machine-readable output for a later MCP layer.
5. Parser completeness only when it improves the above.

## Non-goals for the MVP

- Full Stata language implementation.
- Executing Stata.
- Replacing Git/research logs with an internal memory system.
- Building generic software call graphs when no research use case depends on them.
- Engineering a checker/automation stack before the parser proves useful.

## Parser rule

V0.1 uses a dependency-free tolerant parser. Do not switch the whole project to Tree-sitter merely for architectural purity. Add a Tree-sitter backend only after real-project tests show a concrete accuracy gain.

Existing `tree-sitter-stata` projects may be studied or optionally integrated later, but their incomplete macro/options support must not block the MVP.

## Research workflow compatibility

StataGraph must work with the repository workflow defined in `gaolingxi/research-project-orchestrator`:

- source/raw-data preparation
- project-ready analysis data
- model regression: mainline + branches
- branch logs retained even when temporary branch code is discarded
- promoted mainline results retain formal code + log + outputs

Future Markdown indexing should treat `research_logs/` and `BRANCH_REGISTRY.md` as durable research history, not rewrite or delete them.

## Development sequence

- V0.1: parser + index + CLI + tests
- V0.2: macros, IV/factor parsing, research-log index, table-estimate links
- V0.3: MCP server for OpenCode/Codex/Claude-compatible clients
- V0.4: optional Tree-sitter backend and incremental indexing

Prefer small changes driven by failures on actual Stata repositories.