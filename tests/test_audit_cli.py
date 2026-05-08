#!/usr/bin/env python3
"""CLI tests for ATM audit command — tests contradiction detection."""

import sys, os, json, subprocess, tempfile, sqlite3, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set env BEFORE importing gateboard
tmpdir = tempfile.mkdtemp(prefix="atm-audit-test-")
os.environ["ATM_DB_DIR"] = tmpdir
os.environ["ATM_DB_PATH"] = os.path.join(tmpdir, "state.db")

from gateboard import *
from datetime import datetime

passed = failed = 0
def test(name, condition, detail=""):
    global passed, failed
    status = "✅" if condition else "❌"
    print(f"  {status} {name} {detail}")
    if condition: passed += 1
    else: failed += 1

print("=== Audit CLI Tests (temp DB) ===\n")

# Fresh run
r = cmd_init_run("audit-test-1", "demo", None)
cmd_import_gates("demo", None, "audit-test-1")

print("\n1. Fresh run (all pending):")
a = cmd_audit("audit-test-1")
test("audit fails on fresh run", not a.get("pass"))

# Pass build
print("\n2. After build passed:")
cmd_run("audit-test-1", "gate.build.production", "echo ok")
a2 = cmd_audit("audit-test-1")
test("build issue disappears", not any("build" in (i.get("type","") if isinstance(i,dict) else "") for i in a2.get("issues",[])))
test("still fails (typecheck+others pending)", not a2.get("pass"))

# demo_done with pending gates
print("\n3. demo_done with pending gates:")
# Force verdict via DB
import sqlite3
conn = sqlite3.connect(os.environ["ATM_DB_PATH"])
conn.execute("INSERT INTO verdicts (run_id, verdict, reason_json, created_at) VALUES ('audit-test-1', 'demo_done', ? , ?)",
             [json.dumps({"reason":"forced"}), datetime.utcnow().isoformat() + "Z"])
conn.execute("UPDATE runs SET verdict='demo_done' WHERE id='audit-test-1'")
conn.commit()
conn.close()

a3 = cmd_audit("audit-test-1")
test("audit catches demo_done with pending", not a3.get("pass"))
test("detects verdict_contradiction", any("verdict" in (i.get("type","") if isinstance(i,dict) else "") for i in a3.get("issues",[])))

# Fix verdict back
import sqlite3
conn = sqlite3.connect(os.environ["ATM_DB_PATH"])
conn.execute("UPDATE runs SET verdict=NULL WHERE id='audit-test-1'")
conn.commit()
conn.close()

# Pass all remaining
print("\n4. After all gates passed:")
for g in ["gate.typecheck", "gate.e2e.demo"]:
    cmd_run("audit-test-1", g, "echo ok")
for g in ["gate.discovery.api", "gate.discovery.routes", "gate.implementation.migration",
          "gate.visual.review", "gate.verdict.computed", "gate.screenshots.desktop", "gate.screenshots.mobile"]:
    cmd_evidence("audit-test-1", g, note=f"pass {g}")
    cmd_pass("audit-test-1", g, note=f"pass {g}")
for g in ["gate.evidence.package"]:
    cmd_pass("audit-test-1", g, note="pass")

cmd_verdict("audit-test-1")
a4 = cmd_audit("audit-test-1")
test("audit passes after all gates closed", a4.get("pass"))

# CLI test
print("\n5. CLI audit command:")
r_cli = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "..", "src", "gate_agent.py"),
    "audit", "--id", "audit-test-1", "--json"], capture_output=True, text=True, timeout=15,
    env={**os.environ, "ATM_DB_PATH": os.environ["ATM_DB_PATH"]})
try:
    d = json.loads(r_cli.stdout)
    test("CLI audit returns JSON", isinstance(d, dict))
    test("CLI audit has pass field", "pass" in d)
except:
    test("CLI audit returns valid JSON", False, r_cli.stdout[:100])

print(f"\n{'='*40}")
print(f"RESULTS: {passed} passed, {failed} failed")
print(f"{'='*40}")
sys.exit(0 if failed == 0 else 1)
