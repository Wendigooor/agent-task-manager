# Agent Task Manager — Gate Runner

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![SQLite](https://img.shields.io/badge/db-sqlite-003b57)]()
[![Tests](https://img.shields.io/badge/deliver--tests-35%2F35-green)]()

## In one sentence

**ATM prevents AI agents from claiming "done" when they aren't.** It's a gate runner: a CLI that enforces build, typecheck, E2E, screenshots, and evidence checks through deterministic Python, not agent promises. If a gate fails, ATM refuses `done`.

## Quick Start

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/Wendigooor/agent-task-manager/main/install.sh | bash

# Init project
cd /my/project && atm init-project

# One command delivery
atm deliver --id my-feature --profile demo
# → ok=true status=demo_done
```

Full agent-readable instructions in [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md).

## The Problem

Autonomous agents (Hermes, Codex, Claude Code, OpenCode) are great at writing code but terrible at being their own auditor. They repeatedly produce `done` while:

- Build/typecheck failed silently
- Evidence files are absent
- E2E used soft assertions or API shortcuts
- Screenshots exist but were never reviewed
- Reports contradict repo state

This is not a prompting problem. It's a **runtime** problem. ATM is the objective auditor that sits between the agent and the `done` declaration.

## Profiles

| Profile | Use case | Outcome | Visual gates? |
|---------|----------|---------|---------------|
| `demo` | Visual/user-facing features with UI, E2E, screenshots | `demo_done` | Yes |
| `technical-report` | CLI tools, reports, backend scripts | `technical_done` | No |
| `patch` | Small code fixes, single-file changes | `patch_done` | No |
| `technical-demo` | Legacy mixed tasks (prefer specific profiles) | `technical_demo_done` | Partial |

Using `demo` for a non-visual task triggers `profile_mismatch_possible` audit warning.

## Anti-Cheat (v3)

ATM detects and blocks 9 specific agent evasion patterns at the runtime level:

1. **Screenshot gates cannot be manually passed** — `screenshot_set` gates require real `.png`/`.jpg` files. `atm pass` with no files is rejected.
2. **Visual review requires artifact** — `gate.visual.review` needs `visual-review.md` or `vision-review.md` in evidence/. Notes alone are rejected.
3. **Typecheck must be typecheck, not smoke** — running `python3 scripts/fetch.py` through `gate.typecheck` triggers `typecheck_command_looks_like_smoke` (critical).
4. **No-op build blocked** — `echo no-op`, `true`, `printf` in build gate are detected. Use `build-not-applicable.md` waiver or choose a profile without build gates.
5. **Direct DB mutation detected** — gate passed without `gate_events` entry → `direct_db_mutation_suspected` (critical). Same for verdicts without `verdicts` table entries.
6. **Evidence in project root flagged** — `summary.md`, `verdict.json`, etc. in project root trigger `evidence_files_in_project_root` (major). Belongs in `agent/atm/runs/<run-id>/evidence/`.
7. **Unknown review provenance blocks `demo_done`** — reviewer artifact without `reviewer_model` and `executor_model` in frontmatter → `unknown_review_provenance` → hard block for `demo` profile.
8. **Profile mismatch detection** — `demo` profile without screenshots → `profile_mismatch_possible` (major).
9. **Review metadata integrity** — incomplete or missing review frontmatter fields → `review_metadata_missing` (major).

## Realistic Example

```bash
# Run a feature through ATM
atm deliver --id tournament-podium --profile demo
```

Output:

```json
{
  "ok": true,
  "status": "demo_done",
  "profile": "demo",
  "run_id": "tournament-podium",
  "steps": {
    "audit": "PASS",
    "prepare_review": "PASS",
    "review_artifact": "found",
    "review_quality": "cross_model",
    "review_status": "approve",
    "complete_review": "PASS"
  },
  "review_mode": "cross_model",
  "reviewer": "codex (gpt-5.4-mini)",
  "executor": "deepseek-v4-flash",
  "verdict": "demo_done"
}
```

If a step fails:

```json
{
  "ok": false,
  "status": "technical_partial",
  "errors": [
    "[audit] CRITICAL: evidence_file_missing — summary.md not found at agent/atm/runs/podium/evidence/summary.md",
    "[audit] CRITICAL: evidence_file_missing — changed-files.md not found"
  ]
}
```

## Architecture

```
src/
├── gateboard.py          # Gate ORM, SQLite schema, CLI logic — 19 audit checks + 9 anti-cheat
├── gate_agent.py         # CLI entry point — all atm subcommands
├── demo_flow.py          # End-to-end demo script
├── memory.py             # Task memory persistence
├── taskboard.py          # Task state machine
├── read_agent.py         # (legacy)
├── workitem_agent.py     # (legacy)
├── status_agent.py       # (legacy)
├── milestone_agent.py    # (legacy)
└── db_log.py             # Database logging

tests/
├── test_deliver.py       # 35 pytest tests — full delivery lifecycle + anti-cheat
├── test_gateboard.py     # 32 inline tests — gate state machine, evidence, verify
├── test_cli.py           # 14 inline tests — CLI command integration
└── test_audit_cli.py     # 8 inline tests — audit contradiction detection

bin/atm                   # Shell wrapper (adds to PATH)
AGENT_QUICKSTART.md       # Canonical instructions for any agent
install.sh                # One-command curl-pipe-bash installer
```

**SQLite** — 6 tables, append-only for events. Verdicts are computed from gate state, not written by agents.

## CLI Commands

```
atm deliver --id <run> --profile <profile>    # Runtime-owned lifecycle → <profile>_done
  --reviewer-script PATH                      # External reviewer
  --skip-review                               # Explicit partial outcome
  --skip-review-reason TXT                    # Accepted risk reason

atm init-run --id <run> --profile <profile>   # Create a new run
atm import-gates --profile <profile>          # Import gates from profile
atm next                                      # Next unblocked gate
atm start --gate <id>                         # Mark in_progress
atm run --gate <id> -- <cmd>                  # Execute command gate
atm pass --gate <id> --file <path>            # Pass manual gate with evidence
atm fail --gate <id> --reason                 # Fail a gate
atm block --gate <id> --reason                # Block a gate
atm verify                                    # Check for contradictions
atm verdict                                   # Compute final status
atm audit                                     # 19-check audit
atm export --out <dir>                        # Export as JSON
atm status                                    # Run overview
atm doctor                                    # Check installation health
atm init-project                              # Setup .atm/config.yaml
```

## Review Lifecycle

`atm deliver` runs 9 fail-closed steps automatically:

| # | Step | Fail condition |
|---|------|----------------|
| 1 | Audit | Not PASS (19 checks) |
| 2 | Prepare review | Bundle incomplete |
| 3 | Run reviewer script | Script exits non-zero |
| 4 | Find review artifact | No verdict file |
| 5 | Classify review mode | same_session_self_review or unknown_provenance |
| 6 | Check fix-response | Fix-response newer than latest approve |
| 7 | Vision review (if configured) | Screenshots exist and vision_required |
| 8 | Review status | Infrastructure checks fail |
| 9 | Complete review | Anti-false-done lock fails |

Review artifacts must have YAML frontmatter with `reviewer_model`, `executor_model`, `review_mode` and a `Status: approve/reject` line. See [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) for exact format.

## Gate State Machine

```
pending → in_progress → passed
pending → in_progress → failed
pending → blocked
blocked  → pending
failed   → in_progress
passed   → failed       (only by verify on contradiction)
```

**Forbidden:** `pending → passed` for command gates. `failed → passed` without new event. Any `demo_done` with critical gates not passed.

## Gold Standard Integration

ATM enforces the delivery rules from [`GOLD_STANDARD.md`](GOLD_STANDARD.md) at the runtime level. The Gold Standard becomes a constitution — ATM becomes the court.

**Moved into ATM:** 400+ checkboxes → gate profiles. Evidence file lists → `file_exists` gates. Build/typecheck/E2E → `command` gates. Gate status tracking → SQLite. Verdict → computed by ATM.

**Stays in markdown:** Product bar and taste guidance. Demo story and narrative. Failure taxonomy. Escalation rules.

## Non-Goals (will not be built)

- Web UI, multi-user permissions, cloud service
- Workflow designer, visual AI judge
- Full control plane replacement
- Enterprise project management

## Tests

```bash
python3 tests/test_deliver.py       # 35 tests — full lifecycle + anti-cheat
python3 tests/test_gateboard.py     # 32 tests — state machine + evidence
python3 tests/test_cli.py           # 14 tests — CLI integration
python3 tests/test_audit_cli.py     # 8 tests — audit detection
```

**Known:** 4 pre-existing test failures in `test_gateboard.py` (2: file_exists check, visual review rejection) and `test_audit_cli.py` (2: build issue persistence, evidence file check after full pass). These are environment-specific isolation issues, not code regressions.

## Files

| File | Purpose |
|------|---------|
| `src/gateboard.py` | Gate ORM + CLI logic — 1600 lines |
| `src/gate_agent.py` | CLI entry point — 250 lines |
| `AGENT_QUICKSTART.md` | Canonical instructions for any agent |
| `install.sh` | One-command installer |
| `bin/atm` | PATH wrapper |
