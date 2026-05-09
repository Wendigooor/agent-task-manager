# Agent Task Manager — Gate Runner

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![SQLite](https://img.shields.io/badge/db-sqlite-003b57)]()
[![Tests](https://img.shields.io/badge/tests-54%2F54-green)]()

## What is ATM in one sentence?

**ATM prevents AI agents from claiming "done" when they aren't.**

It's a gate runner: a CLI that enforces build, typecheck, E2E, screenshots, and evidence checks through deterministic Python, not agent promises. If a gate fails, ATM refuses `done`. The agent cannot override it.

---

### The Problem It Solves

Autonomous agents (Hermes, Codex, Claude Code, OpenCode) are great at writing code but terrible at being their own auditor. They repeatedly say `done` when:
- Build/typecheck failed silently
- Evidence files are absent
- E2E used soft assertions or API shortcuts
- Screenshots exist but were never visually reviewed
- Final reports contradict repo state

This is not a prompting problem. It's a **runtime** problem. ATM is the **objective auditor** that sits between the agent and the `done` declaration.

---

### How It Fits In

```
PUFF (control plane)
  ↓ launches
Agent (Hermes/Codex/OpenCode)
  ↓ orchestrates
ATM (gate runner)   ← YOU ARE HERE
  ↓ enforces
Gold Standard (constitution — internal convention, 57KB, 405 steps)
```

ATM enforces an internal autonomous delivery convention (the Gold Standard — 57KB, 405 mandatory steps). See [`GOLD_STANDARD.md`](GOLD_STANDARD.md) for the full map.

---

### Why SQLite?

Every gate transition, evidence attachment, and command run is stored in an append-only event log. Verdicts are **computed from gate state**, not written by the agent. If the agent says `done` but a critical gate is still `pending`, ATM's verdict wins over the agent's prose.

---

### Quick Start

```bash
# 1. Full demo (5 seconds)
python3 src/demo_flow.py

# 2. Real use
atm init-run --id my-feature --profile demo --contract ORIGINAL_CONTRACT.md
atm import-gates --profile demo
atm next                    # → "build.production"
atm run --gate build.production --command 'npm run build'
atm pass --gate e2e.passed --evidence screenshots/01.png
atm verify
atm verdict
atm prepare-review --id my-feature
atm complete-review --id my-feature
```

---

## Why

In autonomous feature experiments, agents repeatedly said `done` while:
- Build/typecheck failed
- Evidence files were absent
- E2E used soft assertions or API shortcuts
- Screenshots existed but weren't visually reviewed
- Final reports contradicted repo state

This is not a prompting problem. It's a **runtime** problem. Agents are good at implementation. They are bad at being their own auditor.

**ATM is the auditor.**

## Architecture

```
src/
├── gateboard.py        # Gate ORM, CLI logic, SQLite schema (6 tables)
├── gate_agent.py       # CLI entry point
├── demo_flow.py        # End-to-end demo
├── taskboard.py        # (existing) Task state machine
├── read_agent.py       # (existing)
├── workitem_agent.py   # (existing)
└── status_agent.py     # (existing)
.atm/state.db           # SQLite database (auto-created)
.atm/logs/<run-id>/     # Command run logs
tests/test_gateboard.py   # 32 unit tests
tests/test_cli.py          # 14 CLI command tests
tests/test_audit_cli.py    # 8 audit contradiction tests
Total: 54 tests, 0 failures expected.
bin/atm                 # CLI wrapper
```

## SQLite Schema

6 tables, append-only where it matters:

### `runs`
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | Run identifier |
| profile | TEXT | Gate profile (demo / feature / patch / benchmark) |
| contract_path | TEXT | Path to feature contract |
| status | TEXT | active / completed |
| verdict | TEXT | Computed by `atm verdict` |
| created_at | TEXT | ISO timestamp |
| updated_at | TEXT | ISO timestamp |

### `gates`
| Column | Type | Description |
|--------|------|-------------|
| run_id + id | TEXT PK | Composite key |
| title | TEXT | Human-readable name |
| severity | TEXT | critical / major / minor |
| kind | TEXT | command / manual / file_exists / screenshot_set / composite |
| status | TEXT | pending / in_progress / passed / failed / blocked |
| spec_json | TEXT | JSON with command, paths, thresholds |
| created_at / updated_at | TEXT | Timestamps |

### `gate_events` (append-only)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | Event ID |
| run_id | TEXT | Run |
| gate_id | TEXT | Gate |
| event_type | TEXT | started / passed / failed / blocked / run_started |
| payload_json | TEXT | JSON with reason, exit_code, etc. |
| created_at | TEXT | Timestamp |

### `evidence_refs`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | Evidence ID |
| run_id | TEXT | Run |
| gate_id | TEXT | Gate |
| evidence_type | TEXT | file / note |
| path | TEXT | Path to evidence file |
| sha256 | TEXT | File hash |
| note | TEXT | Human note |
| created_at | TEXT | Timestamp |

### `command_runs`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | Run ID |
| run_id | TEXT | Run |
| gate_id | TEXT | Gate |
| command | TEXT | Shell command |
| exit_code | INTEGER | 0 = pass |
| stdout_path | TEXT | Log file path |
| stderr_path | TEXT | Log file path |
| duration_ms | INTEGER | Execution time |
| created_at | TEXT | Timestamp |

### `verdicts`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | Verdict ID |
| run_id | TEXT | Run |
| verdict | TEXT | demo_done / reviewable_partial / technical_partial / failed / invalid |
| reason_json | TEXT | JSON reason |
| created_at | TEXT | Timestamp |

## Gate State Machine

```
pending -> in_progress -> passed
pending -> in_progress -> failed
pending -> blocked
blocked -> pending
failed -> in_progress
passed -> failed       (only by verify when contradiction found)
```

**Forbidden transitions:**
- `pending -> passed` for command gates
- `pending -> passed` without evidence for manual gates
- `failed -> passed` without a new event
- Any `demo_done` verdict with critical gates not passed

## Gate Types

| Type | Kind | Pass condition | Can agent override? |
|------|------|---------------|---------------------|
| Command | `command` | Exit code 0 | ❌ No — only `atm run` |
| Manual | `manual` | Evidence or note | ✅ Yes |
| File exists | `file_exists` | Files on disk | ✅ Yes (with evidence) |
| Screenshot set | `screenshot_set` | Min count + min size | ✅ Yes (with evidence) |
| Composite | `composite` | Computed by ATM | ❌ No |
| Forbidden pattern | `grep_forbidden` | No matches found | ❌ No |

## CLI Commands

```
atm init-run --id <run> --profile demo --contract <path>
    Create a new run. Refuses duplicate --id unless --resume.

atm import-gates --profile demo
    Import gates from built-in profile. Idempotent.

atm next
    Return next unblocked critical gate. Agent should not decide what to do from memory.

atm start --gate <id>
    Mark gate as in_progress.

atm run --gate <id> --command '<shell command>'
    Execute command. Captures stdout/stderr/duration. Pass only on exit 0.
    Agent cannot manually pass command gates.

atm pass --gate <id> --evidence <path> --note '<note>'
    Pass manual gate with evidence file or note.

atm fail --gate <id> --reason '<reason>'
    Fail a gate.

atm block --gate <id> --reason '<reason>'
    Block a gate. Requires reason.

atm evidence --gate <id> --file <path> --note '<note>'
    Attach evidence without changing gate status.

atm status
    Run overview: gates by status, verdict.

atm verify
    Check for contradictions: passed without evidence, missing files, verdict vs gate state.

atm verdict
    Compute final status. Agent may quote the verdict but may not invent it.

atm export --out <dir>
    Export run state as JSON for audit.

atm prepare-review --id <run>
    Export + audit + bundle generator + validate manifest.
    First step of review lifecycle. Required before complete-review.

atm review-status --id <run>
    Check all review artifacts: bundle completeness, text review, vision review,
    fix-response, audit status. Parses latest reviewer verdict (by mtime,
    supports -2, -3, -final suffixes).

atm complete-review --id <run>
    Anti-false-done lock. Validates prepare-review + review-status + re-audit.
    Critical rule: fix-response is NOT approval. DONE requires latest reviewer
    verdict to be approve, not just a fix-response.
    Verdicts: review_passed, ready_for_re_review, review_rejected, review_incomplete.
```

## Verdict Logic

```
if critical gate failed:
    verdict = failed
elif critical gate pending:
    verdict = technical_partial
elif all gates passed:
    verdict = demo_done
elif major gate failed:
    verdict = reviewable_partial
elif verify found contradiction:
    verdict = invalid
else:
    verdict = technical_partial
```

## Profiles

### `patch` — for small bugfixes
- Scope understood
- Relevant tests pass
- Build/typecheck if touched
- Changed files summarized

### `feature` — for normal features
- Discovery completed
- Data model/API contract verified
- Implementation complete
- Build passes
- Typecheck passes
- Happy path test passes
- Evidence summary exists

### `demo` — for stakeholder demos (current built-in)
- All `feature` gates
- Product experience contract
- Demo via UI, no API shortcuts
- Screenshots desktop + mobile
- Visual review
- E2E with hard assertions
- No console/page errors
- Evidence package complete

### `benchmark` — for comparing models
- All `demo` gates
- Fixed timebox + contract
- Scoring rubric
- Reproduction commands

## Demo

```bash
# Full end-to-end demo
python3 src/demo_flow.py

# Expected output:
#   1. INIT RUN -> created
#   2. IMPORT GATES -> 11 gates
#   3. NEXT GATE -> gate.build.production
#   4. RUN BUILD -> passed (exit 0)
#   5. RUN TYPECHECK -> passed
#   6-11. PASS DISCOVERY, MIGRATION, VISUAL, EVIDENCE
#   12. VERIFY -> PASSED
#   13. VERDICT -> technical_partial (gates remain pending)
#   14. EXPORT -> atm-export.json
```

## Tests

```bash
python3 tests/test_gateboard.py
python3 tests/test_cli.py
python3 tests/test_audit_cli.py
# 54 tests, 0 failures
```

Covers:
- Run lifecycle (init, import, next, start, fail, block)
- Command gates (run, exit-code pass/fail, cannot manually pass)
- Evidence (notes, files, missing files)
- Manual gates (with note, with file)
- File exists gates
- Verify (contradiction detection)
- Verdict (all statuses)
- Export (all sections)
- Idempotency (duplicate run, import)
- Block (status + reason)

## Future Plans

### v0.5 — E2E Guards
Planned but not implemented (current E2E scripts already use hard assertions):
- `grep_forbidden` gate kind — scan for `.catch(() => {})` and `|| true`
- JSON report assertion — validate E2E report fields
- Page/console error conventions
- Mobile overflow assertion template

### v0.6 — Evidence Export Enhancement
- `gate-ledger-summary.md` auto-generation from export JSON
- Reproduction command list in export

### v0.7 — Review Lifecycle (Done)
- `atm prepare-review` — export + audit + bundle generator + validate manifest
- `atm review-status` — check all review artifacts, parse latest verdict
- `atm complete-review` — anti-false-done lock: fix-response ≠ approval
- Key rule: reject + fix-response = ready_for_re_review, not DONE
- Latest verdict wins (supports -2, -3, -final version suffixes)
- Bundle generator includes `reviewer-outputs/` for re-review context

### v0.8 — Optional Nice-To-Have
(Only if v0.1-v0.6 are stable)
- Tiny HTML report with gate status table
- MCP wrapper for agent integration
- Screenshot thumbnails in report

### Non-Goals (will not be built)
- Web UI
- Multi-user permissions
- Cloud service
- Workflow designer
- Markdown parser
- Visual AI judge
- Full PUFF replacement
- Enterprise project management

## How It Integrates With The Gold Standard

Once ATM is active, the Gold Standard markdown should shrink:

**Move into ATM:**
- 400+ checkboxes → gate profiles
- Evidence file lists → `file_exists` gates
- Build/typecheck/E2E → `command` gates
- Gate status tracking → SQLite
- Verdict → computed by ATM

**Keep in markdown:**
- Product bar and taste guidance
- Demo story and narrative
- Failure taxonomy
- Escalation rules
- Examples of good/bad evidence

The standard becomes a **constitution**. ATM becomes the **court**.

## Files

| File | Purpose |
|------|---------|
| `src/gateboard.py` | Gate ORM, CLI logic, schema (20KB) |
| `src/gate_agent.py` | CLI entry point (5KB) |
| `src/demo_flow.py` | End-to-end demo (3.5KB) |
| `tests/test_gateboard.py` | 32 unit tests (7KB) | |
|---|---|---|---|
| `tests/test_cli.py` | 14 CLI command tests (3KB) | |
| `tests/test_audit_cli.py` | 8 audit contradiction tests (3KB) | |
| `bin/atm` | Shell wrapper |
| `.atm/state.db` | SQLite database (auto) |
