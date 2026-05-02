"""Task management agent. Usage: python3 workitem_agent.py <command> [args]"""

import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taskboard import (upsert_work_item, claim_work_item, list_work_items,
                       update_work_item_status, add_work_item_log)


def cmd_create(args):
    return upsert_work_item(
        key=args.key, title=args.title, description=args.description or "",
        milestone_key=args.milestone, priority=args.priority, risk_level=args.risk)


def cmd_claim(args):
    return claim_work_item(args.id, args.agent)


def cmd_list(args):
    return list_work_items(status=args.status, milestone_key=args.milestone)


def cmd_update_status(args):
    return update_work_item_status(args.id, args.status)


def cmd_log(args):
    return add_work_item_log(args.id, args.type, args.message)


def main():
    parser = argparse.ArgumentParser(description="Task management agent")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="Create a work item")
    p_create.add_argument("--key", type=str, required=True, help="Unique key")
    p_create.add_argument("--title", type=str, required=True, help="Title")
    p_create.add_argument("--description", type=str, default="", help="Description")
    p_create.add_argument("--milestone", type=str, default=None, help="Milestone key")
    p_create.add_argument("--priority", type=int, default=0, help="Priority")
    p_create.add_argument("--risk", type=str, default="low", help="Risk level")

    p_claim = sub.add_parser("claim", help="Claim a work item")
    p_claim.add_argument("id", type=str, help="Work item ID or key")
    p_claim.add_argument("--agent", type=str, default="agent", help="Agent name")

    p_list = sub.add_parser("list", help="List work items")
    p_list.add_argument("--status", type=str, default=None, help="Filter by status")
    p_list.add_argument("--milestone", type=str, default=None, help="Filter by milestone key")

    p_upd = sub.add_parser("update-status", help="Update work item status")
    p_upd.add_argument("id", type=str, help="Work item ID or key")
    p_upd.add_argument("--status", type=str, required=True, help="New status")

    p_log = sub.add_parser("log", help="Add a log entry")
    p_log.add_argument("id", type=str, help="Work item ID or key")
    p_log.add_argument("--type", type=str, default="progress", help="Log type (progress/blocked/error)")
    p_log.add_argument("--message", type=str, required=True, help="Log message")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "create": cmd_create,
        "claim": cmd_claim,
        "list": cmd_list,
        "update-status": cmd_update_status,
        "log": cmd_log,
    }
    result = commands[args.command](args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
