"""Status validation agent. Usage: python3 status_agent.py <command> [args]"""

import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taskboard import (update_work_item_status, get_work_item, get_work_item_context,
                       MILESTONE_TRANSITIONS, STATUS_TRANSITIONS,
                       activate_milestone, complete_milestone)


def cmd_item_status(args):
    return update_work_item_status(args.id, args.new_status)


def cmd_milestone_status(args):
    valid_ops = {
        "activate": activate_milestone,
        "complete": complete_milestone,
    }
    if args.new_status not in valid_ops:
        print(json.dumps({"ok": False, "error": f"Invalid milestone action: {args.new_status}. Use activate or complete"}))
        sys.exit(1)
    return valid_ops[args.new_status](args.key)


def cmd_verify(args):
    item = get_work_item(args.id)
    if item is None:
        print(json.dumps({"error": f"Work item not found: {args.id}"}))
        sys.exit(1)
    current = item["status"]
    allowed = STATUS_TRANSITIONS.get(current, [])
    return {
        "id": item["id"],
        "key": item["key"],
        "current_status": current,
        "allowed_transitions": allowed,
        "is_terminal": len(allowed) == 0,
    }


def cmd_transitions(_args):
    return {
        "work_item_transitions": STATUS_TRANSITIONS,
        "milestone_transitions": MILESTONE_TRANSITIONS,
    }


def main():
    parser = argparse.ArgumentParser(description="Status validation agent")
    sub = parser.add_subparsers(dest="command")

    p_is = sub.add_parser("item-status", help="Update work item status")
    p_is.add_argument("id", type=str, help="Work item ID or key")
    p_is.add_argument("new_status", type=str, help="New status")

    p_ms = sub.add_parser("milestone-status", help="Update milestone status")
    p_ms.add_argument("key", type=str, help="Milestone key")
    p_ms.add_argument("new_status", type=str, help="New status (activate or complete)")

    p_v = sub.add_parser("verify", help="Verify current status and allowed transitions")
    p_v.add_argument("id", type=str, help="Work item ID or key")

    sub.add_parser("transitions", help="Show all allowed transitions")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "item-status": cmd_item_status,
        "milestone-status": cmd_milestone_status,
        "verify": cmd_verify,
        "transitions": cmd_transitions,
    }
    result = commands[args.command](args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
