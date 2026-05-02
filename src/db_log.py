"""Readable dump of everything in plans.db. Usage: python3 src/db_log.py"""
import sqlite3, os, sys, json
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plans.db")

def log():
    if not os.path.exists(DB_PATH):
        print("No database found. Run: python3 src/taskboard.py")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=" * 60)
    print("  AGENT TASK MANAGER — Database Log")
    print("=" * 60)

    # Milestones
    ms = conn.execute("SELECT * FROM milestones ORDER BY priority DESC").fetchall()
    print(f"\n📦 MILESTONES ({len(ms)})")
    for m in ms:
        icon = {"active": "🟡", "done": "✅", "planned": "⏳", "cancelled": "❌"}.get(m["status"], "  ")
        print(f"  {icon} [{m['status']:10s}] {m['key']:20s} phase={m['phase']} | {m['title']}")

    # Work items grouped by milestone
    print(f"\n📋 WORK ITEMS ({conn.execute('SELECT COUNT(*) FROM work_items').fetchone()[0]})")
    for m in ms:
        items = conn.execute(
            "SELECT * FROM work_items WHERE milestone_key=? ORDER BY priority DESC", [m["key"]]
        ).fetchall()
        if not items: continue
        print(f"\n  ▸ {m['key']} ({m['status']})")
        for item in items:
            icon = {"done": "✅", "in_progress": "🔧", "blocked": "🚫", "todo": "⬜", "needs_review": "👀", "failed": "💥", "cancelled": "❌"}.get(item["status"], "  ")
            claim = f" [@{item['claimed_by']}]" if item["claimed_by"] else ""
            print(f"    {icon} #{item['id']} {item['key']:10s} [{item['status']:12s}] {item['title']}{claim}")
            # Logs for this item
            logs = conn.execute(
                "SELECT * FROM work_item_logs WHERE work_item_id=? ORDER BY created_at", [item["id"]]
            ).fetchall()
            for log_entry in logs:
                print(f"       └ {log_entry['created_at'][:16]} [{log_entry['log_type']}] {log_entry['message']}")

    # Summary
    counts = {}
    for row in conn.execute("SELECT status, COUNT(*) as c FROM work_items GROUP BY status").fetchall():
        counts[row["status"]] = row["c"]
    print(f"\n📊 SUMMARY: ", end="")
    parts = [f"{v} {k}" for k, v in counts.items()]
    print(", ".join(parts))

    # Phases
    phases = conn.execute("SELECT DISTINCT phase FROM milestones ORDER BY phase").fetchall()
    print(f"   Phases: {', '.join(r['phase'] for r in phases)}")

    conn.close()

if __name__ == "__main__":
    log()
