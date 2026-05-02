# Agent Task Manager

## Rules (Invariants)

- All task state is in `plans.db` (SQLite). Never write plans in Markdown.
- Use CLI scripts for all database operations. Never write raw SQL.
- One task at a time. Claim → work → verify → done.
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

# ... write code ...

# Mark complete
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
| `src/db_log.py` | Readable dump of everything in the DB | Read |

## State Machine

```
todo → in_progress → needs_review → done
  ↓        ↓             ↓          ↑
blocked ←──┘             └──────────┘
  ↓
todo / in_progress

done / cancelled → (locked, no further transitions)
failed → todo / in_progress
```

If the AI tries an invalid transition (e.g. `todo → done`), `status_agent.py` returns an error. Python enforces the rules, not prompts.
