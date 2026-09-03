# Legacy VeriEdge EuroSys Archive

This directory preserves the earlier VeriEdge manuscript, figures, scripts,
review-era experiments, and delivery artifacts that preceded the current PACT
redesign. It exists for provenance and for reusing validated runtime or
placement infrastructure.

## Use Boundary

- Do not treat legacy experiment numbers as current Route B results.
- Revalidate protocol, workload, hardware, and statistics before carrying any
  number into a new manuscript.
- Prefer the active design and claim ledger under `../docs/`.
- Prefer active verification experiments under `../experiments/pact_offline/`.
- Treat `experimental_assets/` as historical deliveries with heterogeneous
  naming and completeness, not as a uniform benchmark suite.

## Private-Repository Boundary

This archive may contain old manuscripts, review analysis, hardware details,
large derived tables, and operating notes. Keep it private until the owners
approve disclosure. Archive metadata such as `__MACOSX/` and `._*` is ignored
by the Route B `.gitignore` and should not be added to a new repository.
