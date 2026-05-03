# Agent Task Manager

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![SQLite](https://img.shields.io/badge/db-sqlite-003b57)]()
[![Lines](https://img.shields.io/badge/total-730%20lines-lightgrey)]()

A SQLite-backed task management framework for AI agents.

**No markdown plans. No raw SQL. No hallucinated states.**
Agents call typed CLI scripts. Python enforces the rules.

---

## Why?

AI agents cannot reliably manage their own state. They forget, hallucinate
statuses, and produce inconsistent outputs. Text files (PLAN.md with checkboxes)
are not state management — they're chaos.

The solution: a **deterministic shell** around the probabilistic LLM. The agent
becomes a "brain" that invokes CLI commands. The Python framework enforces
valid transitions, prevents data corruption, and keeps the context window clean.

---

## How It Works

```
                  README.md (constitution)
                       │
                  AI Agent (LLM)
                       │
      ┌────────────────┼────────────────┐
      ▼                ▼                ▼
  read_agent     workitem_agent    status_agent
  (read-only)     (task CRUD)      (state machine)
      │                │                │
      └────────────────┼────────────────┘
                       ▼
                  taskboard.py  (ORM)
                       │
                  plans.db  (SQLite)
```

The agent receives one instruction: *"Read README.md. Tell me the project status
and what to do next."* It calls CLI scripts to query the database, claim tasks,
update statuses. The state machine prevents invalid transitions. The ORM hides
raw SQL. One task at a time — no context bloat.

---

## Quick Start

```bash
python3 src/taskboard.py           # Initialize database
python3 src/db_log.py              # View everything in the DB
python3 src/read_agent.py phases   # Project status
python3 src/read_agent.py next     # Next task to work on
```

Full workflow:

```bash
python3 src/read_agent.py next                    # 1. Find task
python3 src/read_agent.py context <id>            # 2. Load details
python3 src/workitem_agent.py claim <id>          # 3. Claim it
# ... write code ...
python3 src/workitem_agent.py update-status <id> --status done  # 4. Complete
```

---

## State Machine

```
todo ──→ in_progress ──→ needs_review ──→ done
  │          │                │
  └──→ blocked ←──┘            │
                               │
                        failed ←┘
```

If the agent tries `todo → done` directly, `status_agent.py` returns an error.
Python enforces the rules. Prompts don't.

---

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/memory.py` | 13 | DB connection |
| `src/taskboard.py` | 292 | ORM: tables, transitions, seed data |
| `src/read_agent.py` | 82 | Read-only queries |
| `src/workitem_agent.py` | 78 | Task CRUD |
| `src/status_agent.py` | 82 | State machine validation |
| `src/milestone_agent.py` | 62 | Milestone lifecycle |
| `src/db_log.py` | 59 | Human-readable DB dump |
| `README.md` | — | Constitution + CLI reference |
| `HOW_IT_WORKS.md` | — | Architecture schematic |
| `SCALING_UP.md` | — | Multi-service, MCP, inbox v2 design |

Total: ~730 lines of Python.

---

## Real Example: Twitter Digest Project

`test-run/PLAN.md` and `test-run/DB_LOG.txt` show the framework managing a
real project plan: 3 milestones (Core Engine, Delivery, Output), 6 tasks
(TW-001 through TW-006), with progress logs and status transitions.

---

## License

MIT
