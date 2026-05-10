#!/usr/bin/env python3
"""ATM Demo — full gate ledger flow end-to-end."""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from gateboard import *

print("=" * 60)
print("ATM — Lightweight Gate Runner Demo")
print("=" * 60)

# 1. Init run
print("\n1. INIT RUN")
import sqlite3, os
_db = os.path.join(os.path.dirname(__file__), "..", ".atm", "state.db")
# Clean previous demo state
if os.path.exists(_db):
    c = sqlite3.connect(_db)
    c.execute("DELETE FROM gates WHERE run_id = 'demo-flow'")
    c.execute("DELETE FROM gate_events WHERE run_id = 'demo-flow'")
    c.execute("DELETE FROM evidence_refs WHERE run_id = 'demo-flow'")
    c.execute("DELETE FROM command_runs WHERE run_id = 'demo-flow'")
    c.execute("DELETE FROM verdicts WHERE run_id = 'demo-flow'")
    c.execute("DELETE FROM runs WHERE id = 'demo-flow'")
    c.commit()
    c.close()
r = cmd_init_run("demo-flow", "demo", "./docs/ATM_LIGHTWEIGHT_GATE_RUNNER_SPEC.md")
print(f"   {r['status']}: {r['run_id']} ({r['profile']})")

# 2. Import gates
print("\n2. IMPORT GATES (demo profile)")
r = cmd_import_gates("demo")
print(f"   {r['status']}: {r['count']} gates")

# 3. Next
print("\n3. NEXT GATE")
r = cmd_next("demo-flow")
print(f"   Gate: {r.get('gate_id', '?')}")
print(f"   Severity: {r.get('severity', '?')}")
print(f"   Title: {r.get('title', '?')}")
print(f"   Pass: {r.get('pass_criteria', '?')}")

# 4. Run build
print("\n4. RUN BUILD (simulated)")
r = cmd_run("demo-flow", "gate.build.production", "echo 'Build OK: 0 errors'")
print(f"   Status: {r['status']} (exit: {r['exit_code']}, {r['duration_ms']}ms)")

# 5. Run typecheck
print("\n5. RUN TYPECHECK (simulated)")
r = cmd_run("demo-flow", "gate.typecheck", "echo 'Typecheck: clean'")
print(f"   Status: {r['status']} (exit: {r['exit_code']})")

# 6. Pass discovery
print("\n6. PASS DISCOVERY GATES")
for g in ["gate.discovery.api", "gate.discovery.routes"]:
    r = cmd_pass("demo-flow", g, note=f"{g}: verified during discovery")
    print(f"   {g}: {r['status']}")

# 7. Pass migration (waived)
print("\n7. PASS MIGRATION (waived)")
r = cmd_pass("demo-flow", "gate.implementation.migration", note="Migration not required: DB schema created via psql")
print(f"   gate.implementation.migration: {r['status']}")

# 8. E2E
print("\n8. RUN E2E (simulated)")
r = cmd_run("demo-flow", "gate.e2e.demo", "echo 'E2E: 7/7 passed, 0 errors'")
print(f"   Status: {r['status']} (exit: {r['exit_code']})")

# 9. Screenshots
print("\n9. EVIDENCE (screenshots)")
r = cmd_evidence("demo-flow", "gate.screenshots.desktop", file_path="src/gateboard.py", note="7 screenshots, all >150KB")
print(f"   {r.get('status', 'passed')}: {r.get('file', '?')}")

# 10. Visual review
print("\n10. VISUAL REVIEW")
r = cmd_pass("demo-flow", "gate.visual.review", note="Screenshots reviewed: hero visible, podium, prize ladder")
print(f"   {r.get('status', 'passed')}")

# 11. Evidence package — create files in project root
print("\n11. EVIDENCE PACKAGE")
# Create dummy evidence files in project root
for f in ["summary.md", "verdict.json", "changed-files.md", "artifacts.json", "demo-narrative.md", "e2e-report.json"]:
    with open(f, "w") as fh: fh.write("placeholder")
r = cmd_pass("demo-flow", "gate.evidence.package", evidence_path="summary.md", note="All evidence files present")
print(f"   {r.get('status', 'passed')}")

# 12. Verify
print("\n12. VERIFY")
r = cmd_verify("demo-flow")
print(f"   {'PASSED' if r.get('pass') else 'FAILED'}")
if not r.get('pass'):
    for i in r.get('issues', []):
        print(f"   [{i['gate']}] {i['issue']}")

# 13. Verdict
print("\n13. VERDICT")
r = cmd_verdict("demo-flow")
print(f"   {'=' * 20}")
print(f"   VERDICT: {r['verdict']}")
print(f"   Reason: {r['reason']}")
print(f"   Summary: {r.get('summary', {})}")
print(f"   {'=' * 20}")

# 14. Export
print("\n14. EXPORT")
r = cmd_export("demo-flow", "/tmp/atm-export")
print(f"   Exported: {r.get('path', '?')}")

# Cleanup evidence files after verify
for f in ["summary.md", "verdict.json", "changed-files.md", "artifacts.json", "demo-narrative.md", "e2e-report.json"]:
    if os.path.exists(f): os.remove(f)

print("\n" + "=" * 60)
print("DEMO COMPLETE")
print("=" * 60)
