# ATM Deliver v2 — Vendor-Agnostic Review Lifecycle

## Mission

Refactor `atm deliver` from a Codex-hardcoded lifecycle to a vendor-agnostic,
graded-outcome review lifecycle that any reviewer can satisfy by writing a
markdown artifact with YAML frontmatter.

## Background

v1 had hardcoded Codex invocation, hardcoded model diversity failure, and
hardcoded vision requirements. v2 makes all of these pluggable.

## Scope

- `src/gateboard.py` — `cmd_deliver` rewrite, new parser, classifier, artifact discovery
- `src/gate_agent.py` — `deliver` subparser with --reviewer-script, --skip-review
- `tests/test_deliver.py` — 11 tests

## Key Changes

1. Review artifact contract: YAML frontmatter + Status: line (any naming convention)
2. Graded outcomes: demo_done with mode info, same-model=warning, cross-model=pass
3. --skip-review: produces technical_partial
4. --reviewer-script: pluggable external reviewer
5. same_session_self_review: hard fail if explicitly declared
6. Vision review: if_configured (warning, not failure)

## Verification

- `python3.11 -m pytest tests/test_deliver.py -v` → 11 pass
- `atm deliver --id <run> --profile demo` → lifecycle runs without Codex dependency
