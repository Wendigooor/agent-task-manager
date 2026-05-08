#!/usr/bin/env python3
"""ATM Gate Agent CLI — subparsers, stable, production-ready."""

import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(__file__))
from gateboard import *

def _resolve_run_id(args):
    """Resolve run_id: subparser --id, main parser --id, or latest active."""
    sub_id = getattr(args, "id", None)
    global_id = getattr(args, "global_id", None)
    rid = sub_id or global_id
    if rid:
        return rid
    # Fallback: latest active run
    s = cmd_status()
    if isinstance(s, dict) and s.get("run_id"):
        return s["run_id"]
    return None

def _add_json(sp):
    sp.add_argument("--json", action="store_true", help="JSON output")

def _add_id(sp):
    sp.add_argument("--id", help="Run ID (default: latest active)")

def main():
    p = argparse.ArgumentParser(prog="atm", description="Agent Task Manager — Gate Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--id", dest="global_id", metavar="RUN_ID", help="Run ID (global, before command)")
    sub = p.add_subparsers(dest="command", required=True)

    def _sp(name, help_text):
        sp = sub.add_parser(name, help=help_text)
        _add_json(sp); _add_id(sp)
        return sp

    # init-run (own --id, required)
    sp = sub.add_parser("init-run", help="Create new run")
    _add_json(sp); sp.add_argument("--id", required=True)
    sp.add_argument("--profile", default="demo"); sp.add_argument("--contract")

    # import-gates
    sp = _sp("import-gates", "Import gates")
    sp.add_argument("--profile", default="demo"); sp.add_argument("--file")

    for cmd, help_txt, has_gate, has_reason, has_file, has_note in [
        ("next", "Show next gate", False, False, False, False),
        ("start", "Start a gate", True, False, False, False),
        ("pass", "Pass a manual gate", True, False, True, True),
        ("fail", "Fail a gate", True, True, False, False),
        ("block", "Block a gate", True, True, False, False),
    ]:
        sp = _sp(cmd, help_txt)
        if has_gate: sp.add_argument("--gate", required=True)
        if has_reason: sp.add_argument("--reason", required=True)
        if has_file: sp.add_argument("--file")
        if has_note: sp.add_argument("--note")

    # run
    sp = _sp("run", "Run a command gate")
    sp.add_argument("--gate", required=True); sp.add_argument("--timeout", type=int, default=300)
    sp.add_argument("cmd", nargs=argparse.REMAINDER, help="Command (use -- before)")

    # evidence
    sp = _sp("evidence", "Attach evidence")
    sp.add_argument("--gate", required=True); sp.add_argument("--file"); sp.add_argument("--note")

    # status / verify / verify-integrity / verdict / doctor / smoke / export
    for cmd in ("status", "verify", "verify-integrity", "verdict", "audit", "smoke"):
        _sp(cmd, None)

    # export
    sp = _sp("export", "Export run"); sp.add_argument("--out", required=True)

    # doctor (no --id)
    sp = sub.add_parser("doctor", help="Check ATM environment"); _add_json(sp)

    args = p.parse_args()
    rid = _resolve_run_id(args)

    try:
        handlers = {
            "init-run": lambda: cmd_init_run(args.id, args.profile, args.contract),
            "import-gates": lambda: cmd_import_gates(args.profile, args.file, rid),
            "next": lambda: cmd_next(rid),
            "start": lambda: cmd_start(rid, args.gate),
            "pass": lambda: cmd_pass(rid, args.gate, args.file, args.note),
            "fail": lambda: cmd_fail(rid, args.gate, args.reason),
            "block": lambda: cmd_block(rid, args.gate, args.reason),
            "run": lambda: _cmd_run(rid, args),
            "evidence": lambda: cmd_evidence(rid, args.gate, args.file, args.note),
            "status": lambda: cmd_status(rid),
            "verify": lambda: cmd_verify_integrity(rid),
            "verify-integrity": lambda: cmd_verify_integrity(rid),
            "audit": lambda: cmd_audit(rid),
            "verdict": lambda: cmd_verdict(rid),
            "export": lambda: cmd_export(rid, args.out),
            "doctor": cmd_doctor,
            "smoke": lambda: cmd_smoke(rid, args),
        }
        result = handlers.get(args.command, lambda: {"error": f"Unknown: {args.command}"})()
    except Exception as e:
        result = {"error": str(e)}

    json_mode = getattr(args, "json", False) or "ATM_JSON" in os.environ
    if json_mode:
        print(json.dumps(result, indent=2, default=str))
    elif "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)
    else:
        _human(args.command, result)

def _cmd_run(rid, args):
    cmd = " ".join(args.cmd).lstrip("-- ") if args.cmd else ""
    if not cmd:
        return {"error": "No command. Usage: atm run --gate <id> -- <shell cmd>"}
    return cmd_run(rid, args.gate, cmd, args.timeout)

def _human(cmd, r):
    if cmd == "smoke":
        print("SMOKE TEST")
        for ok, name, msg in r.get("steps", []):
            print(f"  {'✅' if ok else '❌'} {name}: {msg}")
        print(f"\nOverall: {'PASS' if r.get('pass') else 'FAIL'}")

    elif cmd == "audit":
        print(f"AUDIT: {r.get('run_id')}")
        print(f"  Verdict: {r.get('verdict')} | Gates: {r.get('passed_gates')}/{r.get('gate_count')} passed")
        print(f"  Issues: {r.get('critical_issues')} critical, {r.get('major_issues')} major")
        for i in r.get("issues", []):
            print(f"  {'🔴' if i.get('severity')=='critical' else '🟡'} [{i.get('severity')}] {i.get('detail')}")
        for w in r.get("warnings", []):
            print(f"  ⓘ {w.get('detail')}")
        print(f"\n  Audit: {'PASS ✅' if r.get('pass') else 'FAIL ❌'}")
    elif cmd == "verdict":
        print(f"Verdict: {r.get('verdict')} — {r.get('reason')}")
        s = r.get("summary", {})
        print(f"  Passed: {s.get('passed', 0)}/{s.get('total', 0)} | Critical: {s.get('critical_failed', 0)} failed, {s.get('critical_pending', 0)} pending")
    elif cmd in ("verify", "verify-integrity"):
        print(f"Verify: {'PASSED' if r.get('pass') else 'FAILED — ' + str(len(r.get('issues', []))) + ' issue(s)'}")
        for i in r.get("issues", []):
            print(f"  [{i.get('gate')}] {i.get('issue')}")
    elif cmd == "next":
        if "gate_id" in r:
            print(f"Next: {r['gate_id']} ({r.get('severity')})")
            print(f"  Title: {r.get('title')}")
            print(f"  Pass: {r.get('pass_criteria')}")
        else:
            print(json.dumps(r, indent=2))
    elif cmd == "status":
        print(f"Run: {r.get('run_id')} | {r.get('profile')} | Verdict: {r.get('verdict') or '—'}")
        bs = r.get("gates", {}).get("by_status", {})
        print(f"Gates: {r.get('gates', {}).get('total', 0)} total")
        for s, c in sorted(bs.items()):
            print(f"  {s}: {c}")
    elif cmd == "doctor":
        print(f"ATM: {r.get('status')}")
        print(f"  DB: {r.get('db_path')} ({r.get('db')})")
        print(f"  bin/atm: {r.get('bin_atm')}")
        if r.get("issues"):
            for i in r["issues"]:
                print(f"  Issue: {i}")
    elif cmd == "export":
        print(f"Exported: {r.get('path')}")
    else:
        print(json.dumps(r, indent=2))

if __name__ == "__main__":
    main()
