# Gold Standard — ATM Reference

## What This Is

A map of the relationship between **Agent Task Manager (ATM)** and the **Autonomous Delivery Gold Standard** (57KB, 405 mandatory steps, PvP Arena Season 1).

The Gold Standard is the "constitution" of autonomous delivery. ATM is the "court" that enforces it.

```
Gold Standard (constitution)
    ↓ defines
ATM gates (laws)
    ↓ executes
gate_agent.py (judge)
    ↓ produces
Verdict (sentence)
```

## Source

The Gold Standard lives in the **PUFF** repository ([github.com/Wendigooor/puff](https://github.com/Wendigooor/puff)) — a collection of autonomous feature delivery experiments where ATM was battle-tested. PUFF is not a dependency or required runtime; it's the upstream research project that produced the standard ATM enforces.

Original: [AUTONOMOUS_DELIVERY_GOLD_STANDARD.md](https://github.com/Wendigooor/puff/blob/main/evidence/pvp-arena-season-1/AUTONOMOUS_DELIVERY_GOLD_STANDARD.md)

## How ATM Implements the Gold Standard

### ATM Execution Layer (Gold Standard section)

Gold Standard requires:
```
If atm is available, agent must use it.
If atm is unavailable or unused, max verdict = partial.
Manual demo_done is invalid.
```

ATM covers this through:
- `bin/atm` — CLI entry point
- `gate_agent.py` — gate runner engine
- `gateboard.py` — ORM + SQLite schema + CLI logic
- `.atm/state.db` — SQLite database (auto-created)
- `.atm/logs/<run-id>/` — command run logs

### Gate Ledger Rule

Gold Standard requires:
- Gate ledger is created BEFORE implementation
- Each gate has id, severity, status, owner, notes, evidence refs
- Gates start as `pending`
- Gates are updated during the run, not only at the end
- Final verdict is computed from gate statuses

ATM covers through:
- `atm init-run --id <run> --profile demo --contract <path>` — creates a run
- `atm import-gates --profile demo` — imports gates from built-in profile
- `6 tables` in SQLite: runs, gates, gate_events (append-only), evidence_refs, command_runs, verdicts
- Statuses: pending → in_progress → passed/failed/blocked
- Forbidden transitions (e.g. `pending → passed` for command gates)

### Operating Modes

Gold Standard defines 4 modes (Patch/Feature/Demo/Benchmark). ATM covers them through 4 built-in profiles:

| Profile | Matches | Gates |
|---------|---------|-------|
| `patch` | Mode A: Patch | Basic checks (build/typecheck) |
| `feature` | Mode B: Feature | Discovery + implementation + evidence |
| `demo` | Mode C: Demo | All of feature + UI/E2E/visuals |
| `benchmark` | Mode D: Benchmark | All of demo + timebox + rubric |

### Verdict Logic

Gold Standard requires:
```
if critical gate failed → verdict = failed/partial
if major gate failed → verdict = partial
if all passed → verdict = demo_done
```

ATM implements through `atm verdict`:
```python
if critical gate failed:       verdict = failed
elif critical gate pending:    verdict = technical_partial
elif all gates passed:         verdict = demo_done
elif major gate failed:        verdict = reviewable_partial
elif verify found contradiction: verdict = invalid
else:                          verdict = technical_partial
```

### Anti-False-Done Lock

Gold Standard includes the Readiness Assertion And Honesty Gate section. ATM implements through the review lifecycle:
- `atm prepare-review` — export + audit + bundle
- `atm review-status` — check artifacts + parse verdict
- `atm complete-review` — anti-false-done: fix-response ≠ approval

Critical rule from Gold Standard:
```
If ATM verdict and prose summary disagree, the stricter status wins.
Manual demo_done is invalid.
```

ATM enforces through:
- `atm verify` — checks for contradictions
- `atm verdict` — computes status from gate state, not from prose
- `atm complete-review` — blocks `demo_done` if review hasn't passed

### Anti-Pattern Checklist (Gold Standard)

Out of 18 anti-patterns, ATM directly prevents:

| Anti-pattern | How ATM prevents it |
|--------------|---------------------|
| Gate archive theater | `init-run` requires id, `import-gates` creates gates before code |
| ATM bypass | `atm verify` checks that gates exist |
| Verdict forgery | `atm verdict` computed from gate state |
| Thin evidence | `pass` requires evidence path or note |
| Premature done | `complete-review` won't pass without approve |

## How To Use

```bash
# 1. Read the Gold Standard
open https://github.com/Wendigooor/puff/blob/main/evidence/pvp-arena-season-1/AUTONOMOUS_DELIVERY_GOLD_STANDARD.md

# 2. Create a run via ATM
atm init-run --id my-feature --profile demo --contract ORIGINAL_CONTRACT.md

# 3. Import gates
atm import-gates --profile demo

# 4. Work through gates
atm next           # → next gate
atm start --gate X # → start it
atm run --gate X --command 'npm run build'  # → execute
atm pass --gate X --evidence screenshots/01.png  # → confirm

# 5. Finalize
atm verify
atm verdict
atm export --out evidence/my-feature/
atm prepare-review --id my-feature
atm complete-review --id my-feature  # → anti-false-done
```

## Chain of Custody

```
PUFF (control plane)
  ↓ invokes
Hermes/Codex/OpenCode (agent)
  ↓ uses
ATM (gate runner)
  ↓ enforces
Gold Standard (constitution)
```

ATM is the only layer where "law" meets "enforcement". Without ATM, the Gold Standard is just text. Without the Gold Standard, ATM is just a CLI with SQLite.
