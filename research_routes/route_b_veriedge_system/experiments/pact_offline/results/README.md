# PACT Result Snapshots

Each subdirectory is the output of one experiment configuration. CSV files are
machine-readable measurements, JSON files record run metadata and checks, PNG
files are derived figures, and SQLite is used only by the transactional state
machine test.

These snapshots include smoke tests, P0 matrices, high-precision coefficient
audits, protocol checks, and negative controls. They are retained so figures
and written conclusions can be traced to concrete outputs. They are not a
substitute for rerunning an experiment in the release environment.

The six-prompt capture subset does not support a final 1% false-positive-rate
claim. Directory names containing `smoke` or `p0` mean engineering validation,
not final evaluation results.

For a new run, choose a fresh output directory instead of overwriting an
existing snapshot. Record the full command and environment in the associated
research log or result note.
