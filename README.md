# Agent Task Manager — Gate Runner

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![SQLite](https://img.shields.io/badge/db-sqlite-003b57)]()

A SQLite-backed gate runner for AI agents. Prevents fake `done` by enforcing gates, evidence, and verdicts through deterministic Python, not agent prose.

## What's New: Gate Runner (v0.1)

The `gate_agent.py` adds a gate state machine on top of the existing task system:

### CLI Commands

```
atm init-run --id <run> --profile demo       # Create a new run
atm import-gates --profile demo               # Import gate profile
atm next                                      # Next unblocked gate
atm start --gate <id>                         # Start working on a gate
atm run --gate <id> --command '<cmd>'          # Run command gate (exit-code based)
atm pass --gate <id> --note '...'             # Pass manual gate
atm fail --gate <id> --reason '...'           # Fail a gate
atm evidence --gate <id> --file <path>         # Attach evidence
atm status                                     # Run overview
atm verify                                     # Check for contradictions
atm verdict                                    # Computed final status
atm export --out <dir>                         # Export run evidence
```

### Gate Types

| Type | Description | Pass condition |
|------|-------------|---------------|
| `command` | Runs shell command | Exit code 0 only |
| `manual` | Agent judgment | Requires evidence or note |
| `file_exists` | Required files | Files must exist on disk |
| `screenshot_set` | Screenshot quality | Min count + min size |
| `composite` | Computed verdict | ATM logic |

### Demo

```bash
python3 src/demo_flow.py
```

Shows: init → import gates → run build → pass discovery → run E2E → evidence → verify → verdict → export.

### Architecture

```
src/
├── gateboard.py       # Gate ORM, CLI logic, SQLite schema
├── gate_agent.py     # CLI entry point
├── demo_flow.py      # End-to-end demo
├── taskboard.py      # (existing) Task state machine
├── read_agent.py     # (existing)
├── workitem_agent.py # (existing)
└── status_agent.py   # (existing)
.atm/state.db         # SQLite database (auto-created)
```

### SQLite Tables

- `runs` — run metadata and verdict
- `gates` — gates with kind, severity, status, spec
- `gate_events` — append-only event log
- `evidence_refs` — evidence files and notes
- `command_runs` — command execution logs
- `verdicts` — computed verdict history
