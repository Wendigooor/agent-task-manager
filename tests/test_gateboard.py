#!/usr/bin/env python3
"""Tests for ATM Gate Runner — gateboard module."""

import sys, os, json, tempfile, shutil, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Clean DB before importing gateboard
from gateboard import DB_PATH, _ensure_db
if os.path.exists(DB_PATH):
    c = sqlite3.connect(DB_PATH)
    for table in ["gates", "gate_events", "evidence_refs", "command_runs", "verdicts", "runs"]:
        c.execute(f"DELETE FROM {table}")
    c.commit()
    c.close()

# Now import everything
from gateboard import *

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} {detail}")

# ── Setup ──
print("\n=== SETUP ===")
r = cmd_init_run("test-run", "demo", "/tmp/test-contract.md")
test("init-run creates run", r.get("status") == "created")

r = cmd_import_gates("demo")
test("import-gates loads 11 gates", r.get("count") == 11)

# ── Gate State Machine ──
print("\n=== GATE STATE MACHINE ===")
r = cmd_next("test-run")
test("next returns next gate", "gate_id" in r)
first_gate = r.get("gate_id", "")

r = cmd_start("test-run", first_gate)
test("start moves to in_progress", r.get("status") == "in_progress")

r = cmd_fail("test-run", first_gate, "test failure")
test("fail moves to failed", r.get("status") == "failed")

# ── Command Gates ──
print("\n=== COMMAND GATES ===")
r = cmd_run("test-run", "gate.build.production", "echo ok")
test("command run exit 0 passes", r.get("status") == "passed" and r.get("exit_code") == 0)

r = cmd_run("test-run", "gate.typecheck", "echo ok")
test("second command passes", r.get("status") == "passed")

r = cmd_pass("test-run", "gate.build.production", note="override attempt")
test("command gate rejects manual pass", "error" in r)

# ── Evidence ──
print("\n=== EVIDENCE ===")
r = cmd_evidence("test-run", "gate.discovery.api", note="verified via curl")
test("evidence note recorded", r.get("status") == "recorded")

tmpf = "/tmp/test-evidence.txt"
with open(tmpf, "w") as f: f.write("evidence")
r = cmd_evidence("test-run", "gate.screenshots.desktop", file_path=tmpf)
test("evidence file recorded", r.get("status") == "recorded")
os.remove(tmpf)

r = cmd_evidence("test-run", "gate.screenshots.desktop", file_path="/nonexistent.png")
test("missing file returns error", "error" in r)

# ── Manual Gates ──
print("\n=== MANUAL GATES ===")
r = cmd_pass("test-run", "gate.discovery.api", note="API tested")
test("manual gate passes with note", r.get("status") == "passed")

tmpf2 = "/tmp/test-evidence2.txt"
with open(tmpf2, "w") as f: f.write("evidence2")
r = cmd_pass("test-run", "gate.discovery.routes", evidence_path=tmpf2)
test("manual gate passes with file", r.get("status") == "passed")
os.remove(tmpf2)

# ── File Exists ──
print("\n=== FILE EXISTS ===")
for f in ["summary.md", "verdict.json", "changed-files.md", "artifacts.json", "demo-narrative.md", "e2e-report.json"]:
    with open(f, "w") as fh: fh.write("test")
r = cmd_pass("test-run", "gate.evidence.package", evidence_path="summary.md")
test("file_exists passes when files present", r.get("status") == "passed")
for f in ["summary.md", "verdict.json", "changed-files.md", "artifacts.json", "demo-narrative.md", "e2e-report.json"]:
    os.remove(f)

# ── Verify ──
print("\n=== VERIFY ===")
r = cmd_verify("test-run")
test("verify runs without crash", isinstance(r, dict))
verify_passed = r.get("pass", False)
issues = r.get("issues", [])

# ── Verdict ──
print("\n=== VERDICT ===")
r = cmd_verdict("test-run")
test("verdict returns string", isinstance(r.get("verdict"), str))
test("verdict not demo_done (pending gates)", r.get("verdict") != "demo_done")

# ── Export ──
print("\n=== EXPORT ===")
export_dir = "/tmp/atm-test-export"
os.makedirs(export_dir, exist_ok=True)
r = cmd_export("test-run", export_dir)
test("export creates file", os.path.exists(f"{export_dir}/atm-export.json"))
with open(f"{export_dir}/atm-export.json") as f:
    export = json.load(f)
test("export has run", "run" in export and export["run"].get("id") == "test-run")
test("export has gates", len(export.get("gates", [])) > 0)
test("export has events", len(export.get("events", [])) > 0)
test("export has evidence", len(export.get("evidence", [])) > 0)
test("export has commands", len(export.get("commands", [])) > 0)

# ── Idempotency ──
print("\n=== IDEMPOTENCY ===")
r = cmd_init_run("test-run", "demo", "/tmp/test.md")
test("init-run rejects duplicate", "error" in r)

r = cmd_import_gates("demo")
test("import-gates idempotent", r.get("count") == 0)

# ── Block ──
print("\n=== BLOCK ===")
r = cmd_block("test-run", "gate.e2e.demo", "E2E cannot run")
test("block sets blocked", r.get("status") == "blocked")
test("block has reason", r.get("reason") == "E2E cannot run")

# ── Summary ──
print(f"\n{'='*40}")
print(f"RESULTS: {passed} passed, {failed} failed")
print(f"{'='*40}")
sys.exit(0 if failed == 0 else 1)
