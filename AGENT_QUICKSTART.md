# Agent QuickStart

Read and follow this file literally. Do not improvise.

## 1. Install

```bash
curl -fsSL https://raw.githubusercontent.com/Wendigooor/agent-task-manager/main/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
atm doctor
```

Expected output: `ATM: ok` with no critical issues.

## 2. Init project

```bash
cd /path/to/project   # or create a new directory
atm init-project
```

This creates `.atm/config.yaml` with reasonable defaults.
Edit if needed (contract paths, reviewer script, etc).

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
atm init-run --id <feature-name> --profile technical-demo --contract contract.md
atm import-gates --profile technical-demo
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

## 6. Deliver

After all gates pass:

```bash
atm audit                        # confirm 0 critical issues
```

Write a review verdict:

```bash
cat > agent/atm/runs/<feature-name>/evidence/reviewer-verdict.md << 'EOF'
---
reviewer_model: <your-model>
review_mode: cross_model
executor_model: <executor-model>
---
**Status:** approve
EOF
```

Then:

```bash
atm deliver --id <feature-name> --profile technical-demo
```

If `ok=true status=demo_done` → **done**.
If not → read the error, fix, re-run `atm deliver`.

## Rules (non-negotiable)

- `atm deliver` is the ONLY way to reach `demo_done`.
- Do NOT write final verdict prose. ATM computes it.
- Do NOT self-review without recording `review_mode: fresh_context_same_model`.
- Do NOT skip `start` before `pass`/`run`.
- Do NOT batch-pass gates at the end.
- Every manual gate needs either `--file` or `--note`.
- `--skip-review` produces `technical_partial`, not `done`.

## Example

```bash
cd /tmp
mkdir -p my-app/src
cat > my-app/contract.md << 'EOF'
# Feature: hello-cli
Mission: Print "hello {name}" from CLI
EOF

cd my-app
atm init-project
atm init-run --id hello-cli --profile technical-demo --contract contract.md
atm import-gates --profile technical-demo

# Gate: build
atm start --gate gate.build.production
echo 'print("hello world")' > src/main.py
atm run --gate gate.build.production -- python3 -m py_compile src/main.py

# Gate: e2e
atm start --gate gate.e2e.demo
atm run --gate gate.e2e.demo -- python3 src/main.py

# More gates...
# (pass screenshots, discovery, migration with --note "N/A" if not applicable)

# Deliver
mkdir -p agent/atm/runs/hello-cli/evidence
cat > agent/atm/runs/hello-cli/evidence/reviewer-verdict.md << 'REV'
---
reviewer_model: gpt-4
review_mode: cross_model
executor_model: deepseek-v4
---
**Status:** approve
REV

atm deliver --id hello-cli --profile technical-demo
```
