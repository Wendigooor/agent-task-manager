#!/usr/bin/env python3
"""ATM Gate Agent CLI — subparsers, documented, stable."""

import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(__file__))
from gateboard import *

def _run_id(args):
    if args.id:
        return args.id
    r = cmd_status()
    return r.get("run_id") if isinstance(r, dict) else None

def _add_json(p):
    p.add_argument("--json", action="store_true", help="JSON output")

def _add_id(p):
    p.add_argument("--id", help="Run ID (default: latest active)")

def main():
    p = argparse.ArgumentParser(prog="atm", description="Agent Task Manager — Gate Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--id", metavar="RUN_ID", help="Run ID (global, put before command)")
    sub = p.add_subparsers(dest="command", required=True)

    def _sp(name, help_text):
        sp = sub.add_parser(name, help=help_text)
        _add_json(sp)
        _add_id(sp)
        return sp

    # init-run (no --id from _sp, uses its own required --id)
    sp = sub.add_parser("init-run", help="Create new run")
    _add_json(sp); sp.add_argument("--id", required=True)
    sp.add_argument("--profile", default="demo"); sp.add_argument("--contract")

    # import-gates
    sp = _sp("import-gates", "Import gates"); sp.add_argument("--profile", default="demo"); sp.add_argument("--file")

    # next / start / pass / fail / block
    for cmd in ("next",):
        _sp(cmd, f"Show next unblocked gate")
    for cmd in ("start", "pass", "fail", "block"):
        sp = _sp(cmd, None)
        sp.add_argument("--gate", required=True)
        if cmd in ("fail", "block"):
            sp.add_argument("--reason", required=True)
        if cmd == "pass":
            sp.add_argument("--file"); sp.add_argument("--note")

    # run
    sp = _sp("run", "Run a command gate")
    sp.add_argument("--gate", required=True); sp.add_argument("--timeout", type=int, default=300)
    sp.add_argument("cmd", nargs=argparse.REMAINDER, help="Command (use -- before)")

    # evidence
    sp = _sp("evidence", "Attach evidence"); sp.add_argument("--gate", required=True)
    sp.add_argument("--file"); sp.add_argument("--note")

    # status / verify / verify-integrity / verdict / doctor
    for cmd in ("status", "verify", "verify-integrity", "verdict"):
        _sp(cmd, None)

    # export
    sp = _sp("export", "Export run as JSON"); sp.add_argument("--out", required=True)

    # doctor (no --id needed)
    sp = sub.add_parser("doctor", help="Check ATM environment")
    _add_json(sp)

    # smoke
    sp = sub.add_parser("smoke", help="Quick smoke test: init → import → run → verdict")
    _add_json(sp)

    args = p.parse_args()
    rid = _run_id(args)

    try:
        if args.command == "init-run":
            result = cmd_init_run(args.id, args.profile, args.contract)
        elif args.command == "import-gates":
            result = cmd_import_gates(args.profile, args.file, rid)
        elif args.command == "next":
            result = cmd_next(rid)
        elif args.command == "start":
            result = cmd_start(rid, args.gate)
        elif args.command == "pass":
            result = cmd_pass(rid, args.gate, args.file, args.note)
        elif args.command == "fail":
            result = cmd_fail(rid, args.gate, args.reason)
        elif args.command == "block":
            result = cmd_block(rid, args.gate, args.reason)
        elif args.command == "run":
            cmd = " ".join(args.cmd).lstrip("-- ") if args.cmd else ""
            if not cmd:
                result = {"error": "No command. Usage: atm run --gate <id> -- <shell cmd>"}
            else:
                result = cmd_run(rid, args.gate, cmd, args.timeout)
        elif args.command == "evidence":
            result = cmd_evidence(rid, args.gate, args.file, args.note)
        elif args.command == "status":
            result = cmd_status(rid)
        elif args.command in ("verify", "verify-integrity"):
            result = cmd_verify_integrity(rid)
        elif args.command == "verdict":
            result = cmd_verdict(rid)
        elif args.command == "export":
            result = cmd_export(rid, args.out)
        elif args.command == "doctor":
            result = cmd_doctor()
        elif args.command == "smoke":
            result = _cmd_smoke(rid, args)
        else:
            result = {"error": f"Unknown: {args.command}"}
    except Exception as e:
        result = {"error": str(e)}

    json_mode = getattr(args, "json", False) or "ATM_JSON" in os.environ
    if json_mode:
        print(json.dumps(result, indent=2, default=str))
    else:
        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
        _human(args.command, result)

def _human(cmd, r):
    if cmd == "smoke":
        print("SMOKE TEST")
        for step in r.get("steps", []):
            status = "✅" if step[0] else "❌"
            print(f"  {status} {step[1]}: {step[2]}")
        print(f"\nOverall: {'PASS' if r.get('pass') else 'FAIL'}")

    elif cmd == "verdict":
        print(f"Verdict: {r.get('verdict')} — {r.get('reason')}")
        s = r.get("summary", {})
        print(f"  Passed: {s.get('passed', 0)}/{s.get('total', 0)} | Critical: {s.get('critical_failed', 0)} failed, {s.get('critical_pending', 0)} pending")
    elif cmd in ("verify", "verify-integrity"):
        if r.get("pass"):
            print("Verify: PASSED")
        else:
            print(f"Verify: FAILED — {len(r.get('issues', []))} issue(s)")
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
        print(f"  DB: {r.get('db_path')}")
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
