# StataGraph

**Research-aware code, data, and log lineage for Stata projects.**

StataGraph turns a Stata research repository into a queryable project graph:

```text
raw data -> cleaned data -> analysis data -> variables -> regressions -> tables -> research logs
```

The goal is practical recovery of empirical-research history, not a complete Stata language implementation.

## Why

Large Stata projects become difficult to re-enter because context is scattered across `.do` files, intermediate datasets, regressions, output tables, and many branch `.log` files. StataGraph indexes the parts that matter for research questions such as:

- Which script creates `analysis_data_v2.dta`?
- Where is `ln_ai_patent` generated and used?
- Which regressions use household FE plus city-by-year FE?
- Which script produces Table 3?
- Has this branch/specification already been run?
- Which log contains `debt_participation`?
- In which run was `X_orig -> rho_main` significant?
- Which TASK_ID produced a runtime error?

## Install

```bash
pip install -e .
```

## Build the project index

```bash
statagraph index path/to/project
```

This writes `.statagraph/index.json` inside the project. The index is deliberately lightweight: it stores structured log metadata/results, but does **not** duplicate entire log files into JSON. Full-text log searches read the original logs only when queried.

## Code and data queries

Project summary:

```bash
statagraph summary path/to/project
```

Find a variable:

```bash
statagraph find-variable path/to/project ln_ai_patent
```

Find regressions using an X or Y:

```bash
statagraph find-regressions path/to/project --x ln_ai_patent
statagraph find-regressions path/to/project --y resilience
```

Trace dataset relationships:

```bash
statagraph dataset-lineage path/to/project analysis_data_v2.dta
```

Find likely sources of tables/outputs:

```bash
statagraph table-sources path/to/project
```

## Log queries — V0.2

StataGraph scans `.log` and `.smcl` files and extracts:

- `TASK_ID` and other `KEY=VALUE` research markers
- FE / cluster / X markers when printed into the log
- run/file identity and open/close timestamps
- regression outcomes, coefficients, standard errors, p-values, N, clusters, R-squared
- wrapper-command hints such as `table()`, `outcome()`, `label()`, `sample()`
- Stata runtime `r(#)` errors and the preceding error message
- matching `.do` / `.ado` file when the log and code share a stem

Search both structured metadata and the original raw log text:

```bash
statagraph search-logs path/to/project "debt_participation"
statagraph search-logs path/to/project "HOUSEHOLD_AND_CITY_YEAR"
statagraph search-logs path/to/project "E176_MAIN_TABLES_CITYYEAR_FE_20261103"
```

Find structured regression results recovered from logs:

```bash
statagraph log-results path/to/project --x X_orig --y rho_main
statagraph log-results path/to/project --x X_orig --y rho_main --p-lt 0.05
statagraph log-results path/to/project --task E176_MAIN_TABLES_CITYYEAR_FE
```

Find runtime errors across all branch logs:

```bash
statagraph log-errors path/to/project
```

This is intended to make branch history durable even when temporary branch code is later removed. The log remains searchable evidence of what specification was run and what it returned.

## Current parser scope

### Stata code

- file execution: `do`, `run`, `include`
- data I/O: `use`, `save`, `merge`, `append`, `import`, `export`
- variables: `gen`, `generate`, `egen`, `replace`, `rename`, including common `by:` / `bysort:` prefixes
- macros: `global`, `local`
- programs: `program define`
- regressions: `reg`, `regress`, `reghdfe`, `xtreg`, `areg`, `ivreg2`, `ivreghdfe`, `csdid`, `didregress`, `xtivreg2`, `poisson`, `ppmlhdfe`, `logit`, `probit`
- estimates/tables: `eststo`, `esttab`, `estout`, `outreg2`, `collect`, `putexcel`

### Stata logs

- `.log` and `.smcl` discovery
- structured `KEY=VALUE` marker extraction
- coefficient-table recovery
- common regression statistics
- runtime error recovery
- raw-text search without duplicating full logs into the index

## Design principles

1. **Research lineage first.** Data, variables, specifications, results, and logs matter more than generic AST completeness.
2. **Logs are durable research history.** Temporary branch code can be discarded; branch logs should remain searchable.
3. **Do not rewrite research history.** StataGraph indexes files; Git and the original logs remain the source of truth.
4. **Tolerant before clever.** If parsing is uncertain, keep locations and raw evidence rather than inventing structure.
5. **Light index, raw evidence on demand.** Structured fields live in `.statagraph/index.json`; large raw logs are searched in place.
6. **Agent-friendly output.** JSON structures are designed so an MCP layer can be added later.

## Roadmap

### V0.1 — code/data MVP
- project scanner
- Stata command parser
- dataset/variable/regression/output graph
- CLI queries
- unit tests

### V0.2 — current
- branch `.log` / `.smcl` indexing
- TASK/specification marker extraction
- regression-result recovery from logs
- full-text log search
- log-to-code pairing
- runtime error search

### Next V0.2.x
- Markdown `research_logs/` and `BRANCH_REGISTRY.md` indexing
- stronger macro expansion and nested macros
- better IV/factor-variable parsing
- explicit table-to-estimate-to-log linking

### V0.3
- MCP server for OpenCode/Codex/Claude-compatible clients
- agent tools such as `stata_find_regressions`, `stata_search_logs`, and `stata_find_result_history`

### V0.4
- optional Tree-sitter Stata backend
- incremental/watch-mode indexing
- cross-project research context

## Status

V0.2 is driven by real empirical-economics repositories. The target is fast recovery of research history: what was run, with which specification, where the result is, and whether the same branch has already been tried.
