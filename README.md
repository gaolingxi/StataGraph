# StataGraph

**Research-aware code, data, log, and experiment-history lineage for Stata projects.**

StataGraph turns a Stata research repository into a queryable project graph:

```text
raw data -> cleaned data -> analysis data -> variables -> regressions -> tables -> research history
```

The goal is practical recovery of empirical-research history, not a complete Stata language implementation.

## Why

Large Stata projects become difficult to re-enter because context is scattered across `.do` files, intermediate datasets, regressions, output tables, branch `.log` files, `research_logs/*.md`, and `BRANCH_REGISTRY.md`.

StataGraph answers questions such as:

- Which script creates `analysis_data_v2.dta`?
- Where is `ln_ai_patent` generated and used?
- Which regressions use household FE plus city-by-year FE?
- Has this branch/specification already been run?
- Which log contains `debt_participation`?
- In which run was `X_orig -> rho_main` significant?
- What was the decision on branch `B003`?
- Which TASK_ID, branch note, registry row, and Stata log refer to the same experiment?

## Install

```bash
pip install -e .
```

## Build the project index

```bash
statagraph index path/to/project
```

This writes `.statagraph/index.json`. The index stays lightweight: structured metadata/results are stored, while large raw logs and Markdown files remain the source evidence and are read only when queried.

## Code and data queries

```bash
statagraph summary path/to/project
statagraph find-variable path/to/project ln_ai_patent
statagraph find-regressions path/to/project --x ln_ai_patent
statagraph find-regressions path/to/project --y resilience
statagraph dataset-lineage path/to/project analysis_data_v2.dta
statagraph table-sources path/to/project
```

## Stata log queries

StataGraph scans `.log` and `.smcl` files and extracts:

- `TASK_ID`, `BRANCH_ID`, and other `KEY=VALUE` research markers
- FE / cluster / X markers when printed into the log
- run/file identity and timestamps
- regression outcomes, coefficients, standard errors, p-values, N, clusters, R-squared
- wrapper-command hints such as `table()`, `outcome()`, `label()`, `sample()`
- Stata runtime `r(#)` errors
- matching `.do` / `.ado` files when code and log share a stem

Examples:

```bash
statagraph search-logs path/to/project "debt_participation"
statagraph log-results path/to/project --x X_orig --y rho_main
statagraph log-results path/to/project --x X_orig --y rho_main --p-lt 0.05
statagraph log-errors path/to/project
```

## Unified experiment history — V0.2.1

StataGraph now indexes three durable research-history sources together:

1. Stata `.log` / `.smcl`
2. `research_logs/*.md` and related branch-log directories
3. `BRANCH_REGISTRY.md`

Markdown branch logs may use either English or common Chinese field names. Recognized concepts include:

- `BRANCH_ID` / 支线编号
- `TASK_ID`
- `BASE_DATA` / 项目数据
- `BASELINE` / 基准
- `PURPOSE` / 目的
- `CHANGE` / 改动
- `STATUS` / 状态
- `RESULT` / 结果
- `CONCLUSION` / 结论
- `DECISION` / 决策
- `PROMOTED_TO` / 晋升到
- `NEXT_STEP` / 下一步
- X / Y / 固定效应 / 聚类层级

`BRANCH_REGISTRY.md` Markdown tables are parsed row-by-row. Records sharing the same `BRANCH_ID` or `TASK_ID` are automatically linked through `related_records`.

Search without caring which file type contains the answer:

```bash
statagraph search-history path/to/project "收入风险"
statagraph search-history path/to/project "city year FE"
statagraph search-history path/to/project --branch B003
statagraph search-history path/to/project --task E149_INCOME_RISK
statagraph search-history path/to/project --status CLOSED_NULL
statagraph search-history path/to/project "debt participation" --status KEEP
```

The intended workflow is:

```text
branch idea
   -> temporary code may come and go
   -> Stata log retained
   -> branch Markdown retains interpretation/decision
   -> BRANCH_REGISTRY keeps the compact project map
   -> StataGraph links and searches all three
```

So branch code can be discarded when appropriate, while the experiment itself remains discoverable.

## Current parser scope

### Stata code

- `do`, `run`, `include`
- `use`, `save`, `merge`, `append`, `import`, `export`
- `gen`, `generate`, `egen`, `replace`, `rename`, including common `by:` / `bysort:` prefixes
- `global`, `local`
- `program define`
- common research regressions including `reghdfe`, `xtreg`, `ivreg2`, `ivreghdfe`, `csdid`, `ppmlhdfe`, logit/probit
- `eststo`, `esttab`, `estout`, `outreg2`, `collect`, `putexcel`

### Research history

- `.log` / `.smcl` structured result recovery
- raw-text log search
- `research_logs/*.md`, `branch_logs/*.md`, `BRANCH.md`, `BRANCH_LOG.md`
- Chinese and English branch metadata aliases
- `BRANCH_REGISTRY.md` table parsing
- branch/task identity linking across sources
- unified `search-history` query

## Design principles

1. **Research lineage first.** Data, variables, specifications, results, and decisions matter more than generic AST completeness.
2. **Logs are durable research history.** Temporary branch code can be discarded; branch evidence should remain searchable.
3. **Do not rewrite research history.** Git and original source files remain the source of truth.
4. **Tolerant before clever.** Preserve evidence and locations rather than inventing structure.
5. **Light index, raw evidence on demand.** Do not duplicate entire logs into the index.
6. **One experiment history, multiple source types.** Users should search by research question, not remember filenames.
7. **Agent-friendly output.** JSON structures are ready for a later MCP layer.

## Roadmap

### V0.1 — code/data MVP
- Stata parser
- dataset/variable/regression/output graph
- CLI and tests

### V0.2 — log lineage
- `.log` / `.smcl` indexing
- specification markers
- regression-result recovery
- raw log search
- runtime errors

### V0.2.1 — current
- research Markdown indexing
- `BRANCH_REGISTRY.md` row indexing
- unified experiment-history records
- automatic branch/task cross-source linking
- `search-history`

### Next
- stronger macro expansion and nested macros
- better IV/factor-variable parsing
- explicit table-to-estimate-to-log linking
- optional automatic branch-summary generation from retained evidence

### V0.3
- MCP server for OpenCode/Codex/Claude-compatible clients
- tools such as `stata_search_history`, `stata_find_regressions`, and `stata_find_result_history`

### V0.4
- optional Tree-sitter backend
- incremental/watch-mode indexing
- cross-project research context

## Status

V0.2.1 is driven by real empirical-economics repositories. The target is fast recovery of research history: what was tried, with which specification, what happened, why it was kept or closed, and where the supporting evidence lives.
