"""Milestone management agent. Usage: python3 milestone_agent.py <command> [args]"""

import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taskboard import (upsert_milestone, activate_milestone, complete_milestone,
                       list_milestones)


def cmd_create(args):
    return upsert_milestone(
        key=args.key, title=args.title, phase=args.phase, priority=args.priority)


def cmd_activate(args):
    return activate_milestone(args.key)


def cmd_complete(args):
    return complete_milestone(args.key)


def cmd_list(args):
    return list_milestones(status=args.status)


def main():
    parser = argparse.ArgumentParser(description="Milestone management agent")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="Create a milestone")
    p_create.add_argument("key", type=str, help="Unique key")
    p_create.add_argument("--title", type=str, required=True, help="Title")
    p_create.add_argument("--phase", type=str, default="default", help="Phase name")
    p_create.add_argument("--priority", type=int, default=0, help="Priority")

    p_act = sub.add_parser("activate", help="Activate a milestone")
    p_act.add_argument("key", type=str, help="Milestone key")

    p_cmp = sub.add_parser("complete", help="Complete a milestone")
    p_cmp.add_argument("key", type=str, help="Milestone key")

    p_list = sub.add_parser("list", help="List milestones")
    p_list.add_argument("--status", type=str, default=None, help="Filter by status")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "create": cmd_create,
        "activate": cmd_activate,
        "complete": cmd_complete,
        "list": cmd_list,
    }
    result = commands[args.command](args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
