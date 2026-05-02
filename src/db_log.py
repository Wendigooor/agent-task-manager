"""Readable dump of everything in plans.db. Usage: python3 src/db_log.py"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plans.db")

STATUS_ICONS = {"active": "[>]", "done": "[x]", "planned": "[ ]", "cancelled": "[-]"}
ITEM_ICONS = {"done": "[x]", "in_progress": "[>]", "blocked": "[!]", "todo": "[ ]", "needs_review": "[?]", "failed": "[X]", "cancelled": "[-]"}

def log():
    if not os.path.exists(DB_PATH):
        print("No database found. Run: python3 src/taskboard.py")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=" * 60)
    print("  AGENT TASK MANAGER -- Database Log")
    print("=" * 60)

    ms = conn.execute("SELECT * FROM milestones ORDER BY priority DESC").fetchall()
    print("\nMILESTONES (%d)" % len(ms))
    for m in ms:
        icon = STATUS_ICONS.get(m["status"], "   ")
        print("  %s [%-10s] %-20s phase=%-8s | %s" % (icon, m["status"], m["key"], m["phase"], m["title"]))

    print("\nWORK ITEMS (%d)" % conn.execute("SELECT COUNT(*) FROM work_items").fetchone()[0])
    for m in ms:
        items = conn.execute("SELECT * FROM work_items WHERE milestone_key=? ORDER BY priority DESC", [m["key"]]).fetchall()
        if not items: continue
        print("\n  -- %s (%s)" % (m["key"], m["status"]))
        for item in items:
            icon = ITEM_ICONS.get(item["status"], "   ")
            claim = " [@%s]" % item["claimed_by"] if item["claimed_by"] else ""
            print("    %s #%d %-10s [%-12s] %s%s" % (icon, item["id"], item["key"], item["status"], item["title"], claim))
            logs = conn.execute("SELECT * FROM work_item_logs WHERE work_item_id=? ORDER BY created_at", [item["id"]]).fetchall()
            for lg in logs:
                print("       | %s [%s] %s" % (lg["created_at"][:16], lg["log_type"], lg["message"]))

    counts = {}
    for row in conn.execute("SELECT status, COUNT(*) AS c FROM work_items GROUP BY status"):
        counts[row["status"]] = row["c"]
    parts = ["%d %s" % (v, k) for k, v in counts.items()]
    print("\nSUMMARY: %s" % ", ".join(parts))

    phases = conn.execute("SELECT DISTINCT phase FROM milestones ORDER BY phase").fetchall()
    print("Phases: %s" % ", ".join(r["phase"] for r in phases))

    conn.close()

if __name__ == "__main__":
    log()
