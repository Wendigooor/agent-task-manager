#!/usr/bin/env python3
"""CLI integration tests for ATM — tests the actual CLI, not just functions."""

import sys, os, json, tempfile, subprocess

ATM = os.path.join(os.path.dirname(__file__), "..", "src", "gate_agent.py")
passed = failed = 0

def run(args, expect_success=True):
    global passed, failed
    cmd = [sys.executable, ATM] + args.split()
    env = {**os.environ, "ATM_JSON": "1"}
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
    try:
        data = json.loads(r.stdout) if r.stdout else {}
    except json.JSONDecodeError:
        print(f"  ❌ JSON parse error: {r.stdout[:200]}")
        failed += 1
        return {}
    
    if expect_success and "error" in data:
        print(f"  ❌ UNEXPECTED ERROR: {data['error']}")
        failed += 1
    elif not expect_success and "error" not in data:
        print(f"  ❌ EXPECTED ERROR but got success")
        failed += 1
    else:
        passed += 1
        print(f"  ✅ ({data.get('status', data.get('verdict', 'ok'))})")
    return data

tests = [
    ("doctor", "doctor"),

    # Run A
    ("init-run --id run-a", "init-run --id run-a"),
    ("import-gates --id run-a", "import-gates --id run-a"),
    ("run --id run-a --gate gate.build.production -- echo a_ok", "run --id run-a --gate gate.build.production -- echo a_ok"),
    ("status --id run-a", "status --id run-a"),

    # Run B
    ("init-run --id run-b", "init-run --id run-b"),
    ("import-gates --id run-b", "import-gates --id run-b"),
    ("status --id run-b", "status --id run-b"),
    ("run --gate gate.build.production -- echo b_ok", "run --gate gate.build.production -- echo b_ok"),
    ("status --id run-b", "status --id run-b"),

    # Cross-check: both runs exist
    ("status --id run-a", "status --id run-a"),
    ("status --id run-b", "status --id run-b"),

    # export
    ("export --id run-a --out /tmp/atm-cli-test-a", "export --id run-a --out /tmp/atm-cli-test-a"),
    ("export --id run-b --out /tmp/atm-cli-test-b", "export --id run-b --out /tmp/atm-cli-test-b"),
]

# Use temp DB
tmpdir = tempfile.mkdtemp(prefix="atm-cli-test-")
os.environ["ATM_DB_DIR"] = tmpdir
os.environ["ATM_DB_PATH"] = os.path.join(tmpdir, "state.db")

print(f"=== CLI Integration Tests (temp DB: {tmpdir}) ===")
print()

for name, cmd in tests:
    print(f"  {name}", end="")
    run(cmd)

print(f"\n{'='*40}")
print(f"RESULTS: {passed} passed, {failed} failed")
print(f"{'='*40}")
sys.exit(0 if failed == 0 else 1)
