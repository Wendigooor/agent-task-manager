import uuid, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory import get_conn, now, DB_PATH

STATUS_TRANSITIONS = {
    "todo":          ["in_progress", "blocked", "cancelled"],
    "in_progress":   ["blocked", "needs_review", "done", "failed", "cancelled"],
    "blocked":       ["todo", "in_progress", "cancelled"],
    "needs_review":  ["in_progress", "done", "cancelled"],
    "done":          [],
    "failed":        ["todo", "in_progress", "cancelled"],
    "cancelled":     [],
}

MILESTONE_TRANSITIONS = {
    "planned":   ["active", "cancelled"],
    "active":    ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}


def _row_to_dict(row):
    return dict(row) if row else None


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            phase TEXT NOT NULL DEFAULT 'default',
            priority INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS work_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            milestone_key TEXT,
            priority INTEGER NOT NULL DEFAULT 0,
            risk_level TEXT NOT NULL DEFAULT 'low',
            status TEXT NOT NULL DEFAULT 'todo',
            claimed_by TEXT,
            claim_token TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (milestone_key) REFERENCES milestones(key)
        );
        CREATE TABLE IF NOT EXISTS work_item_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_item_id INTEGER NOT NULL,
            log_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (work_item_id) REFERENCES work_items(id)
        );
        CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
        CREATE INDEX IF NOT EXISTS idx_milestones_status ON milestones(status);
    """)
    conn.commit()

    existing = conn.execute("SELECT COUNT(*) as c FROM milestones").fetchone()["c"]
    if existing == 0:
        _seed(conn)
    conn.close()


def _seed(conn):
    ts = now()
    conn.execute(
        "INSERT INTO milestones (key, title, phase, priority, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        ("init", "Project Initialization", "setup", 100, "active", ts, ts))
    conn.execute(
        "INSERT INTO work_items (key, title, description, milestone_key, priority, risk_level, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("setup-repo", "Initialize repository structure", "Create base directory layout and config files", "init", 10, "low", "todo", ts, ts))
    conn.execute(
        "INSERT INTO work_items (key, title, description, milestone_key, priority, risk_level, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("setup-ci", "Configure CI pipeline", "Set up linting, testing, and build checks", "init", 8, "medium", "todo", ts, ts))
    conn.commit()


def upsert_milestone(key, title, phase="default", priority=0):
    conn = get_conn()
    ts = now()
    existing = conn.execute("SELECT id FROM milestones WHERE key=?", (key,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE milestones SET title=?, phase=?, priority=?, updated_at=? WHERE key=?",
            (title, phase, priority, ts, key))
    else:
        conn.execute(
            "INSERT INTO milestones (key, title, phase, priority, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (key, title, phase, priority, "planned", ts, ts))
    conn.commit()
    conn.close()
    return {"ok": True, "key": key}


def activate_milestone(key):
    conn = get_conn()
    row = conn.execute("SELECT status FROM milestones WHERE key=?", (key,)).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": f"Milestone not found: {key}"}
    if row["status"] not in ("planned", "cancelled"):
        conn.close()
        return {"ok": False, "error": f"Cannot activate milestone with status={row['status']}"}
    ts = now()
    conn.execute("UPDATE milestones SET status='active', updated_at=? WHERE key=?", (ts, key))
    conn.commit()
    conn.close()
    return {"ok": True, "key": key}


def complete_milestone(key):
    conn = get_conn()
    row = conn.execute("SELECT status FROM milestones WHERE key=?", (key,)).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": f"Milestone not found: {key}"}
    if row["status"] != "active":
        conn.close()
        return {"ok": False, "error": f"Cannot complete milestone with status={row['status']}"}
    ts = now()
    conn.execute("UPDATE milestones SET status='completed', updated_at=? WHERE key=?", (ts, key))
    conn.commit()
    conn.close()
    return {"ok": True, "key": key}


def list_milestones(status=None):
    conn = get_conn()
    if status:
        rows = conn.execute("SELECT * FROM milestones WHERE status=? ORDER BY priority DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM milestones ORDER BY priority DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def upsert_work_item(key, title, description="", milestone_key=None, priority=0, risk_level="low"):
    conn = get_conn()
    ts = now()
    existing = conn.execute("SELECT id FROM work_items WHERE key=?", (key,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE work_items SET title=?, description=?, milestone_key=?, priority=?, risk_level=?, updated_at=? WHERE key=?",
            (title, description, milestone_key, priority, risk_level, ts, key))
    else:
        conn.execute(
            "INSERT INTO work_items (key, title, description, milestone_key, priority, risk_level, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (key, title, description, milestone_key, priority, risk_level, "todo", ts, ts))
    conn.commit()
    conn.close()
    return {"ok": True, "key": key}


def list_work_items(status=None, milestone_key=None):
    conn = get_conn()
    query = "SELECT * FROM work_items WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if milestone_key:
        query += " AND milestone_key=?"
        params.append(milestone_key)
    query += " ORDER BY priority DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_work_item(id_or_key):
    conn = get_conn()
    try:
        int_val = int(id_or_key)
        row = conn.execute("SELECT * FROM work_items WHERE id=?", (int_val,)).fetchone()
    except ValueError:
        row = conn.execute("SELECT * FROM work_items WHERE key=?", (id_or_key,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def claim_work_item(id_or_key, agent_name):
    item = get_work_item(id_or_key)
    if item is None:
        return {"ok": False, "error": "Work item not found"}
    if item["status"] != "todo":
        return {"ok": False, "error": f"Cannot claim item with status={item['status']}"}
    conn = get_conn()
    ts = now()
    token = str(uuid.uuid4())[:8]
    conn.execute(
        "UPDATE work_items SET status='in_progress', claimed_by=?, claim_token=?, updated_at=? WHERE id=?",
        (agent_name, token, ts, item["id"]))
    conn.commit()
    conn.close()
    return {"ok": True, "id": item["id"], "key": item["key"], "claim_token": token}


def update_work_item_status(id_or_key, new_status):
    item = get_work_item(id_or_key)
    if item is None:
        return {"ok": False, "error": "Work item not found"}
    current = item["status"]
    allowed = STATUS_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        return {"ok": False, "error": f"Invalid transition: {current} -> {new_status}. Allowed: {allowed}"}
    conn = get_conn()
    ts = now()
    conn.execute("UPDATE work_items SET status=?, updated_at=? WHERE id=?", (new_status, ts, item["id"]))
    conn.commit()
    conn.close()
    return {"ok": True, "id": item["id"], "key": item["key"], "old_status": current, "new_status": new_status}


def get_work_item_context(id_or_key):
    item = get_work_item(id_or_key)
    if item is None:
        return None
    conn = get_conn()
    milestone = None
    if item.get("milestone_key"):
        ms_row = conn.execute("SELECT * FROM milestones WHERE key=?", (item["milestone_key"],)).fetchone()
        milestone = _row_to_dict(ms_row)
    logs = conn.execute(
        "SELECT * FROM work_item_logs WHERE work_item_id=? ORDER BY created_at DESC LIMIT 20",
        (item["id"],)).fetchall()
    conn.close()
    return {
        "item": item,
        "milestone": milestone,
        "logs": [_row_to_dict(r) for r in logs],
    }


def add_work_item_log(id_or_key, log_type, message):
    item = get_work_item(id_or_key)
    if item is None:
        return {"ok": False, "error": "Work item not found"}
    if log_type not in ("progress", "blocked", "error"):
        return {"ok": False, "error": f"Invalid log_type: {log_type}. Use progress/blocked/error"}
    conn = get_conn()
    ts = now()
    conn.execute(
        "INSERT INTO work_item_logs (work_item_id, log_type, message, created_at) VALUES (?,?,?,?)",
        (item["id"], log_type, message, ts))
    conn.commit()
    conn.close()
    return {"ok": True, "work_item_id": item["id"], "log_type": log_type}


def get_next_task():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM work_items WHERE status='todo' ORDER BY priority DESC, id ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_phases():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT phase FROM milestones ORDER BY phase").fetchall()
    conn.close()
    return [r["phase"] for r in rows]


def get_logs(id_or_key):
    item = get_work_item(id_or_key)
    if item is None:
        return None
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM work_item_logs WHERE work_item_id=? ORDER BY created_at DESC",
        (item["id"],)).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(json.dumps({"init": "ok", "db": DB_PATH}))
