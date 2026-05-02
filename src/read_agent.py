"""Read-only agent. Usage: python3 read_agent.py <command> [args]"""

import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taskboard import (list_milestones, list_work_items, get_work_item_context,
                       get_next_task, get_phases, get_logs)


def cmd_phases(_args):
    return get_phases()


def cmd_milestones(args):
    return list_milestones(status=args.status)


def cmd_work_items(args):
    return list_work_items(status=args.status, milestone_key=args.milestone)


def cmd_next(_args):
    task = get_next_task()
    if task is None:
        return {"next": None, "message": "No todo items available"}
    return {"next": task}


def cmd_context(args):
    ctx = get_work_item_context(args.id)
    if ctx is None:
        return {"error": f"Work item not found: {args.id}"}
    return ctx


def cmd_logs(args):
    logs = get_logs(args.id)
    if logs is None:
        return {"error": f"Work item not found: {args.id}"}
    return {"logs": logs}


def main():
    parser = argparse.ArgumentParser(description="Read-only agent")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("phases", help="List all phases")

    p_ms = sub.add_parser("milestones", help="List milestones")
    p_ms.add_argument("--status", type=str, default=None, help="Filter by status")

    p_wi = sub.add_parser("work-items", help="List work items")
    p_wi.add_argument("--status", type=str, default=None, help="Filter by status")
    p_wi.add_argument("--milestone", type=str, default=None, help="Filter by milestone key")

    sub.add_parser("next", help="Get next task")

    p_ctx = sub.add_parser("context", help="Get work item context")
    p_ctx.add_argument("id", type=str, help="Work item ID or key")

    p_lg = sub.add_parser("logs", help="Get work item logs")
    p_lg.add_argument("id", type=str, help="Work item ID or key")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "phases": cmd_phases,
        "milestones": cmd_milestones,
        "work-items": cmd_work_items,
        "next": cmd_next,
        "context": cmd_context,
        "logs": cmd_logs,
    }
    result = commands[args.command](args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
