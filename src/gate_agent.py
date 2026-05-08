#!/usr/bin/env python3
"""ATM Gate Agent CLI — init-run, import-gates, next, start, run, pass, fail, evidence, status, verify, verdict, export."""

import sys, json, os, argparse
sys.path.insert(0, os.path.dirname(__file__))
from gateboard import *

def main():
    parser = argparse.ArgumentParser(description="ATM Gate Agent — Lightweight Gate Runner")
    parser.add_argument("command", choices=["init-run", "import-gates", "next", "start", "pass", "fail", "block", "run", "evidence", "status", "verify", "verdict", "export"])
    parser.add_argument("--id", help="Run ID")
    parser.add_argument("--profile", default="demo", help="Gate profile (demo, feature, patch, benchmark)")
    parser.add_argument("--contract", help="Path to contract file")
    parser.add_argument("--file", help="Path to gates YAML")
    parser.add_argument("--gate", help="Gate ID")
    parser.add_argument("--reason", help="Reason for fail/block")
    parser.add_argument("--evidence", help="Evidence file path")
    parser.add_argument("--note", help="Evidence note")
    parser.add_argument("--command", help="Command to run (for `run` subcommand)")
    parser.add_argument("--timeout", type=int, default=300, help="Command timeout in seconds")
    parser.add_argument("--out", default=None, help="Output directory for export")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    result = {}

    if args.command == "init-run":
        if not args.id:
            result = {"error": "--id is required"}
        else:
            result = cmd_init_run(args.id, args.profile, args.contract)

    elif args.command == "import-gates":
        result = cmd_import_gates(args.profile, args.file)

    elif args.command == "next":
        result = cmd_next(args.id)

    elif args.command == "start":
        if not args.gate:
            result = {"error": "--gate is required"}
        else:
            result = cmd_start(args.id or _latest_run(), args.gate)

    elif args.command == "pass":
        if not args.gate:
            result = {"error": "--gate is required"}
        else:
            result = cmd_pass(args.id or _latest_run(), args.gate, args.evidence, args.note)

    elif args.command == "fail":
        if not args.gate:
            result = {"error": "--gate is required"}
        else:
            result = cmd_fail(args.id or _latest_run(), args.gate, args.reason)

    elif args.command == "block":
        if not args.gate or not args.reason:
            result = {"error": "--gate and --reason are required"}
        else:
            result = cmd_block(args.id or _latest_run(), args.gate, args.reason)

    elif args.command == "run":
        if not args.gate or not args.command:
            result = {"error": "--gate and --command are required"}
        else:
            result = cmd_run(args.id or _latest_run(), args.gate, args.command, args.timeout)

    elif args.command == "evidence":
        if not args.gate:
            result = {"error": "--gate is required"}
        elif not args.file and not args.note:
            result = {"error": "--file or --note is required"}
        else:
            result = cmd_evidence(args.id or _latest_run(), args.gate, args.file, args.note)

    elif args.command == "status":
        result = cmd_status(args.id)

    elif args.command == "verify":
        result = cmd_verify(args.id)

    elif args.command == "verdict":
        result = cmd_verdict(args.id)

    elif args.command == "export":
        if not args.out:
            result = {"error": "--out is required"}
        else:
            result = cmd_export(args.id or _latest_run(), args.out)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
        if args.command == "verdict":
            print(f"Verdict: {result.get('verdict', '?')}")
            print(f"Reason: {result.get('reason', '?')}")
        elif args.command == "verify":
            if result.get("pass"):
                print("Verify: PASSED")
            else:
                print(f"Verify: FAILED — {len(result.get('issues', []))} issue(s)")
                for i in result.get("issues", []):
                    print(f"  [{i.get('gate', '?')}] {i.get('issue', '?')}")
        elif args.command == "next":
            if "gate_id" in result:
                print(f"Next: {result['gate_id']} ({result.get('severity', '?')})")
                print(f"  Title: {result.get('title', '?')}")
                print(f"  Pass: {result.get('pass_criteria', '?')}")
            else:
                print(json.dumps(result, indent=2))
        elif args.command == "status":
            print(f"Run: {result.get('run_id', '?')}")
            print(f"Profile: {result.get('profile', '?')}")
            print(f"Verdict: {result.get('verdict', '?')}")
            bs = result.get("gates", {}).get("by_status", {})
            print(f"Gates: {result.get('gates', {}).get('total', 0)} total")
            for s, c in sorted(bs.items()):
                print(f"  {s}: {c}")
        else:
            print(json.dumps(result, indent=2))

def _latest_run():
    r = cmd_status()
    return r.get("run_id") if isinstance(r, dict) else None

if __name__ == "__main__":
    main()
