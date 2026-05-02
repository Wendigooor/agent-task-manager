# How the Agent Framework Works

## The Problem

You tell an AI "build feature X". It writes code. Then you tell it "build feature Y". It forgets what it did. Plans get lost. Statuses get mixed up. The AI hallucinates tasks that don't exist.

## The Solution

A **SQLite database** that is the single source of truth for all tasks. The AI doesn't write plans in text files. It queries a database through strict CLI scripts. Each script does exactly one thing.

## Architecture (TL;DR)

```
                  ┌─────────────────────────┐
                  │       README.md          │
                  │  (Constitution: rules,   │
                  │   stack, CLI commands)    │
                  └──────────┬──────────────┘
                             │
                  ┌──────────▼──────────────┐
                  │     AI Agent (LLM)       │
                  │  Reads README, calls CLI │
                  └──────────┬──────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
  ┌──────▼──────┐   ┌───────▼───────┐   ┌───────▼──────┐
  │ read_agent  │   │ status_agent  │   │ workitem_agent│
  │ (read-only) │   │ (transitions) │   │  (CRUD tasks) │
  └──────┬──────┘   └───────┬───────┘   └───────┬──────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                  ┌──────────▼──────────────┐
                  │      taskboard.py        │
                  │    (ORM layer: typed     │
                  │     SQLite helpers)      │
                  └──────────┬──────────────┘
                             │
                  ┌──────────▼──────────────┐
                  │       plans.db           │
                  │   (SQLite database)      │
                  └──────────────────────────┘
```

## How to Use (One Command)

```
"Read README.md. Tell me the project status and what to do next."
```

The AI will:
1. Read README.md to understand the rules
2. Call `python3 src/read_agent.py phases` to see all phases
3. Call `python3 src/read_agent.py next` to get the next task
4. Call `python3 src/read_agent.py context <id>` to load task details
5. Call `python3 src/workitem_agent.py claim <id>` to claim the task
6. Write code
7. Call `python3 src/workitem_agent.py update-status <id> --status done` to complete

## The Key Principle: Determinism Over Prompts

The AI is probabilistic. It hallucinates. You cannot fix this with better prompts.

Instead, you wrap it in **deterministic code**:
- The AI cannot write SQL → it calls typed CLI commands
- The AI cannot jump statuses → `status_agent.py` validates transitions
- The AI cannot delete tasks → no CLI gives that power
- The AI sees only 1 task at a time → context stays clean

## The State Machine

```
todo ──────► in_progress ──────► needs_review ──────► done
  │               │                      │
  └──► blocked ◄──┘                      │
                                         │
                                 failed ◄┘
```

If the AI tries `todo → done` directly, `status_agent.py` returns an error.
Python code enforces the rules. Prompts don't.

## File Summary

| File | Purpose |
|------|---------|
| `README.md` | Constitution: rules, stack, CLI cheat-sheet |
| `src/read_agent.py` | List phases, milestones, tasks, get context |
| `src/workitem_agent.py` | Create, claim, log, update task status |
| `src/status_agent.py` | Validate status transitions |
| `src/milestone_agent.py` | Create, activate, complete milestones |
| `src/taskboard.py` | ORM layer (typed SQLite helpers) |
| `src/memory.py` | DB connection |
| `src/db_log.py` | Readable dump of everything in the database |
| `plans.db` | SQLite database (via scripts only) |
