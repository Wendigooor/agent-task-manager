# Agent QuickStart

Read and follow this file literally. Do not improvise.

## Profile Selection (MANDATORY)

Choose the right profile for your task:

| If your task is... | Use profile |
|---|---|
| Visual/user-facing feature (UI changes, screenshots, E2E) | `demo` |
| CLI/backend/report/script (no UI, no screenshots) | `technical-report` |
| Small code patch (single file, minimal scope) | `patch` |
| Legacy mixed task (deprecated, prefer specific profiles) | `technical-demo` |

**If you're unsure, pick `technical-report`.** Using `demo` for a CLI task will
fail audit with `profile_mismatch_possible`.

## 1. Install

```bash
curl -fsSL https://raw.githubusercontent.com/Wendigooor/agent-task-manager/main/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
atm doctor
```

Expected output: `ATM: ok` with no critical issues.

## 2. Init project

```bash
cd /path/to/project
atm init-project
```

This creates `.atm/config.yaml` with reasonable defaults.

## 3. Define feature

```bash
cat > contract.md << 'EOF'
# Feature: <title>

## Mission
<one sentence>

## Acceptance
- <criterion>
- <criterion>

## Scope
- In: <list>
- Out: <list>
EOF
```

## 4. Create run

```bash
atm init-run --id <feature-name> --profile <profile> --contract contract.md
atm import-gates --profile <profile>
```

## 5. Run gates

For each gate returned by `atm next`:

```bash
atm next                         # shows next unblocked gate
atm start --gate <gate-id>       # mark in_progress
atm run --gate <gate-id> -- <command>    # for command gates
atm pass --gate <gate-id> --file <path> --note "<note>"  # for manual gates
```

Do NOT batch-pass gates at the end.
Do NOT skip `start` before `pass`.

## 6. Write reviewer verdict

Create a review verdict file with full provenance metadata:

```bash
cat > agent/atm/runs/<feature-name>/evidence/reviewer-verdict.md << 'EOF'
---
reviewer_name: <reviewer-name>
reviewer_model: <reviewer-model>
reviewer_provider: <reviewer-provider>
review_mode: cross_model | fresh_context_same_model | manual
executor_model: <executor-model>
executor_provider: <executor-provider>
review_type: text
created_at: 2026-05-10T12:00:00Z
---

**Status:** approve
EOF
```

**CRITICAL:** Frontmatter metadata is REQUIRED. Without it:
- `demo` profile → blocked
- `technical-report` / `patch` → `technical_partial` only

## 7. Deliver

```bash
atm deliver --id <feature-name> --profile <profile>
```

Expected outcomes by profile:

| Profile | Success status |
|---|---|
| `demo` | `demo_done` |
| `technical-demo` | `technical_demo_done` |
| `technical-report` | `technical_done` |
| `patch` | `patch_done` |

If `ok=true` → **done**.
If not → read the error, fix, re-run `atm deliver`.

## Anti-Cheat Rules (non-negotiable)

These will be caught by audit and BLOCK delivery:

1. **Never manually edit `.atm/state.db`.** Direct DB mutation is detected and fails audit.
2. **Never manually edit `REVIEW_BUNDLE_MANIFEST.md`.** The manifest is generated, not written.
3. **Never pass screenshot or visual gates without actual artifacts.** `atm pass --note "N/A"` on `screenshot_set` gates will be rejected.
4. **Never call smoke execution as typecheck.** Running `python3 scripts/fetch_*.py` through `gate.typecheck` triggers `typecheck_command_looks_like_smoke`.
5. **Never use `echo`/`true`/`printf` as build pass.** Either use a real build command, create a `build-not-applicable.md` waiver, or use a profile without `build.production`.
6. **Always include reviewer metadata.** `reviewer-verdict.md` without frontmatter blocks `demo_done`.
7. **Evidence files go in `agent/atm/runs/<run-id>/evidence/`, NOT project root.**
8. **`atm deliver` is the ONLY way to reach a done status.** Do NOT write final verdict prose directly.
9. **Do NOT self-review without recording `review_mode: fresh_context_same_model`**. Unknown/unknown models are treated as `unknown_review_provenance` and block delivery.
10. **Use the right profile.** `demo` has visual gates — use `technical-report` for CLI/report tasks.

## Example (technical-report for a script task)

```bash
cd /tmp
mkdir -p jira-report
cat > jira-report/contract.md << 'EOF'
# Feature: jira-fetch-report
Mission: Fetch s8 in-progress tasks and produce a summary report
EOF

cd jira-report
atm init-project
atm init-run --id jira-fetch --profile technical-report --contract contract.md
atm import-gates --profile technical-report

# Gate: discovery
atm start --gate gate.discovery.api
atm pass --gate gate.discovery.api --note "Jira REST API v3 endpoint discovered"

# Gate: implementation
atm start --gate gate.implementation.script_or_change
echo 'print("fetching...")' > fetch.py
atm pass --gate gate.implementation.script_or_change --file fetch.py --note "Script created"

# Gate: smoke
atm start --gate gate.smoke.command
atm run --gate gate.smoke.command -- python3 fetch.py

# Gate: evidence
atm start --gate gate.evidence.package
mkdir -p agent/atm/runs/jira-fetch/evidence
echo "# Summary" > agent/atm/runs/jira-fetch/evidence/summary.md
echo '[]' > agent/atm/runs/jira-fetch/evidence/verdict.json
echo "# Changed" > agent/atm/runs/jira-fetch/evidence/changed-files.md
echo '[]' > agent/atm/runs/jira-fetch/evidence/artifacts.json
atm pass --gate gate.evidence.package --file $(pwd)/agent/atm/runs/jira-fetch/evidence/summary.md

# Gate: review
atm start --gate gate.review.artifact
atm pass --gate gate.review.artifact --note "Review artifact ready"

# Gate: verdict
atm pass --gate gate.verdict.computed --note "Verdict computed"

# Write verdict with metadata
cat > agent/atm/runs/jira-fetch/evidence/reviewer-verdict.md << 'REV'
---
reviewer_name: deepseek
reviewer_model: deepseek-v4-pro
reviewer_provider: opencode-go
review_mode: fresh_context_same_model
executor_model: deepseek-v4-flash
executor_provider: deepseek
review_type: text
created_at: 2026-05-10T12:00:00Z
---

**Status:** approve
REV

# Deliver
atm deliver --id jira-fetch --profile technical-report
# Expected: ok=true, status=technical_done
```

## Berserk mode

Prompt to any agent:

```
Read and follow:
https://github.com/Wendigooor/agent-task-manager/blob/main/AGENT_BERSERK_PROMPT.md

Feature:
<feature description>

Expected result:
Do not stop until atm deliver --mode berserk returns ok=true, or until HARD_BLOCKED.
```
