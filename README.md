# Agent Task Manager

## Rules (Invariants)

- All task state is in `plans.db` (SQLite). Never write plans in Markdown.
- Use CLI scripts for all database operations. Never write raw SQL.
- One task at a time. Claim, work, verify, done.
- Never delete tasks. Use `status=cancelled` instead.
- Every task belongs to a milestone. Every milestone belongs to a phase.

## Quick Start

```bash
# Initialize (once)
python3 src/taskboard.py

# See what's in the database
python3 src/db_log.py

# See project status
python3 src/read_agent.py phases

# Get next task
python3 src/read_agent.py next

# Load task context (description + milestone + logs)
python3 src/read_agent.py context <id>

# Claim and start working
python3 src/workitem_agent.py claim <id>

# Write code, then mark complete
python3 src/workitem_agent.py update-status <id> --status done
```

## CLI Reference

| Script | Purpose | AI Access |
|--------|---------|-----------|
| `src/read_agent.py` | List phases, milestones, tasks, get context, view logs | Read |
| `src/workitem_agent.py` | Create, claim, update status, add log entries | Read+Write |
| `src/status_agent.py` | Validate status transitions, verify tasks | Read+Write |
| `src/milestone_agent.py` | Create, activate, complete milestones | Read+Write |
| `src/taskboard.py` | ORM layer (typed SQLite, init DB) | None (API only) |
| `src/db_log.py` | Readable dump of everything in the database | Read |

## State Machine

```
todo -> in_progress -> needs_review -> done
  |        |              |            |
  v        v              |            |
blocked <-+               +------------+
  |
  v
todo / in_progress

done / cancelled -> (locked, no further transitions)
failed -> todo / in_progress
```

If the AI tries an invalid transition (e.g., `todo -> done`), `status_agent.py` returns an error. Python enforces the rules, not prompts.

## Project Structure

```
.
|-- README.md
|-- HOW_IT_WORKS.md
|-- SCALING_UP.md
|-- .gitignore
|-- plans.db                 # SQLite database (generated on init)
|-- src/
|   |-- memory.py            # DB connection
|   |-- taskboard.py         # ORM layer: tables, transitions, seed
|   |-- read_agent.py        # Read-only queries
|   |-- workitem_agent.py    # Task CRUD
|   |-- status_agent.py      # State machine validation
|   |-- milestone_agent.py   # Milestone lifecycle
|   `-- db_log.py            # Readable database dump
`-- test-run/
    |-- PLAN.md              # Sample project plan (Twitter Digest)
    `-- DB_LOG.txt           # Sample database log output
```
