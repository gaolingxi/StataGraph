# StataGraph

**Research-aware code and data lineage for Stata projects.**

StataGraph turns a Stata research repository into a queryable project graph. The first goal is not full Stata language completeness; it is to recover the relationships that matter most in empirical research:

```text
raw data -> cleaned data -> analysis data -> variables -> regressions -> tables -> research logs
```

## Why

Large Stata projects often become slow for humans and coding agents to re-enter because the important context is spread across many `.do` files, macros, intermediate datasets, regressions, output commands, and branch logs. StataGraph indexes those relationships once so an agent can answer questions such as:

- Which script creates `analysis_data_v2.dta`?
- Where is `ln_ai_patent` generated and where is it used?
- Which regressions use household FE plus city-by-year FE?
- Which script produces Table 3?
- Which files call `baseline.do`?
- What datasets are upstream of the final regression sample?

## MVP scope

The initial parser recognizes the most common research workflow constructs:

- file execution: `do`, `run`, `include`
- data I/O: `use`, `save`, `merge`, `append`, `import`, `export`
- variables: `gen`, `generate`, `egen`, `replace`, `rename`
- macros: `global`, `local`
- programs: `program define`
- regressions: `reg`, `regress`, `reghdfe`, `xtreg`, `areg`, `ivreg2`, `ivreghdfe`, `csdid`, `didregress`, `xtivreg2`, `poisson`, `ppmlhdfe`, `logit`, `probit`
- estimates/tables: `eststo`, `esttab`, `estout`, `outreg2`, `collect`, `putexcel`

The parser is intentionally research-oriented and tolerant. It records raw commands and line numbers so uncertain cases remain inspectable instead of being silently invented.

## Install

```bash
pip install -e .
```

## Quick start

Index a project:

```bash
statagraph index path/to/project
```

This writes `.statagraph/index.json` inside the project.

Get a project summary:

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

Find likely sources of a table/output:

```bash
statagraph table-sources path/to/project
```

## Design principles

1. **Research lineage first.** Data, variables, specifications, and tables matter more than generic AST completeness.
2. **Do not rewrite research history.** StataGraph indexes logs; Git remains the source of truth.
3. **Tolerant before clever.** If parsing is uncertain, preserve the raw command and location.
4. **Incremental path.** Start with a dependency-free parser, then add Tree-sitter where it materially improves accuracy.
5. **Agent-friendly output.** JSON structures are stable enough to expose through an MCP layer later.

## Roadmap

### V0.1 — current MVP
- project scanner
- Stata command parser
- dataset/variable/regression/output graph
- CLI queries
- JSON persistence
- unit tests

### V0.2
- stronger macro expansion and nested macros
- `#delimit ;`
- better IV and factor-variable parsing
- explicit table-to-estimate linking
- Markdown research-log indexing (`research_logs/`, `BRANCH_REGISTRY.md`)

### V0.3
- MCP server for OpenCode/Codex/Claude-compatible clients
- agent tools such as `stata_find_regressions`, `stata_variable_lineage`, and `stata_find_table_source`

### V0.4
- optional Tree-sitter Stata backend
- incremental/watch-mode indexing
- cross-project research context

## Parser strategy

Existing Stata Tree-sitter grammars are promising but still incomplete in areas such as nested macros and some command options. For that reason V0.1 uses a small, testable research-command parser. The parser API is separated from storage/query logic so a Tree-sitter backend can be added without changing the CLI or graph model.

## Status

Early development. The target is practical usefulness on real empirical-economics repositories rather than perfect Stata language coverage.