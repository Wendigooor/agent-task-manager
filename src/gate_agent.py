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

def main():
    p = argparse.ArgumentParser(prog="atm", description="Agent Task Manager — Gate Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--id", metavar="RUN_ID", help="Run ID (default: latest active)")
    sub = p.add_subparsers(dest="command", required=True)

    # init-run
    sp = sub.add_parser("init-run", help="Create new run"); _add_json(sp)
    sp.add_argument("--id", required=True); sp.add_argument("--profile", default="demo")
    sp.add_argument("--contract")

    # import-gates
    sp = sub.add_parser("import-gates", help="Import gates from profile"); _add_json(sp)
    sp.add_argument("--profile", default="demo"); sp.add_argument("--file")

    # next
    sp = sub.add_parser("next", help="Show next unblocked gate"); _add_json(sp)

    # start
    sp = sub.add_parser("start", help="Start a gate"); _add_json(sp)
    sp.add_argument("--gate", required=True)

    # pass
    sp = sub.add_parser("pass", help="Pass a manual gate"); _add_json(sp)
    sp.add_argument("--gate", required=True); sp.add_argument("--file"); sp.add_argument("--note")

    # fail
    sp = sub.add_parser("fail", help="Fail a gate"); _add_json(sp)
    sp.add_argument("--gate", required=True); sp.add_argument("--reason", required=True)

    # block
    sp = sub.add_parser("block", help="Block a gate"); _add_json(sp)
    sp.add_argument("--gate", required=True); sp.add_argument("--reason", required=True)

    # run
    sp = sub.add_parser("run", help="Run a command gate"); _add_json(sp)
    sp.add_argument("--gate", required=True); sp.add_argument("--timeout", type=int, default=300)
    sp.add_argument("cmd", nargs=argparse.REMAINDER, help="Command (use -- before)")

    # evidence
    sp = sub.add_parser("evidence", help="Attach evidence"); _add_json(sp)
    sp.add_argument("--gate", required=True); sp.add_argument("--file"); sp.add_argument("--note")

    # status
    sp = sub.add_parser("status", help="Run overview"); _add_json(sp)

    # verify
    sp = sub.add_parser("verify", help="Check for contradictions"); _add_json(sp)

    # verify-integrity
    sp = sub.add_parser("verify-integrity", help="Check integrity (alias)"); _add_json(sp)

    # verdict
    sp = sub.add_parser("verdict", help="Compute final status"); _add_json(sp)

    # export
    sp = sub.add_parser("export", help="Export run as JSON"); _add_json(sp)
    sp.add_argument("--out", required=True)

    # doctor
    sp = sub.add_parser("doctor", help="Check ATM environment"); _add_json(sp)

    args = p.parse_args()
    rid = _run_id(args)

    try:
        if args.command == "init-run":
            result = cmd_init_run(args.id, args.profile, args.contract)
        elif args.command == "import-gates":
            result = cmd_import_gates(args.profile, args.file)
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
    if cmd == "verdict":
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
