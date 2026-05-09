"""Gateboard — Gate state machine, evidence tracking, and verdict computation for ATM."""

from __future__ import annotations
import sqlite3, json, os, hashlib, time, subprocess, sys
from typing import Optional
from datetime import datetime

DB_DIR = os.environ.get("ATM_DB_DIR", os.path.join(os.path.dirname(__file__), "..", ".atm"))
DB_PATH = os.environ.get("ATM_DB_PATH", os.path.join(DB_DIR, "state.db"))
PROJECT_ROOT = os.environ.get("ATM_PROJECT_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DB_DIR = os.environ.get("ATM_DB_DIR", os.path.join(PROJECT_ROOT, ".atm"))
DB_PATH = os.environ.get("ATM_DB_PATH", os.path.join(_DB_DIR, "state.db"))
DB_DIR = _DB_DIR

def _ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            contract_path TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            verdict TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gates (
            id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            title TEXT NOT NULL,
            severity TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            spec_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_id, id)
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gate_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            gate_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT,
            created_at TEXT NOT NULL
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            gate_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            path TEXT,
            note TEXT,
            sha256 TEXT,
            created_at TEXT NOT NULL
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS command_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            gate_id TEXT NOT NULL,
            command TEXT NOT NULL,
            exit_code INTEGER NOT NULL,
            stdout_path TEXT,
            stderr_path TEXT,
            duration_ms INTEGER,
            created_at TEXT NOT NULL
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verdicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            verdict TEXT NOT NULL,
            reason_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
    conn.commit()
    return conn

def now():
    return datetime.utcnow().isoformat() + "Z"

def _event(conn, run_id, gate_id, event_type, payload=None):
    conn.execute(
        "INSERT INTO gate_events (run_id, gate_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
        [run_id, gate_id, event_type, json.dumps(payload) if payload else None, now()]
    )
    conn.commit()


def _subst(s, run_id):
    """Replace <run-id> with actual run_id in paths."""
    if not s or "<run-id>" not in str(s):
        return s
    if isinstance(s, str):
        return s.replace("<run-id>", run_id)
    if isinstance(s, list):
        return [item.replace("<run-id>", run_id) for item in s]
    return s

def _subst_spec(spec, run_id):
    """Apply template substitution to spec fields."""
    if not spec:
        return spec
    for key in ("paths", "command"):
        if key in spec and isinstance(spec[key], str) and "<run-id>" in spec[key]:
            spec[key] = spec[key].replace("<run-id>", run_id)
        if key in spec and isinstance(spec[key], list):
            spec[key] = [item.replace("<run-id>", run_id) for item in spec[key]]
    return spec

def _sha256(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except:
        return None

# ── CLI Commands ──────────────────────────────────────────

def cmd_init_run(run_id, profile, contract_path=None):
    conn = _ensure_db()
    existing = conn.execute("SELECT id FROM runs WHERE id = ?", [run_id]).fetchone()
    if existing:
        return {"error": f"Run '{run_id}' already exists. Use --resume to continue."}
    
    conn.execute(
        "INSERT INTO runs (id, profile, contract_path, status, created_at, updated_at) VALUES (?, ?, ?, 'active', ?, ?)",
        [run_id, profile, contract_path, now(), now()]
    )
    conn.commit()
    return {"status": "created", "run_id": run_id, "profile": profile}

def cmd_import_gates(profile=None, file_path=None, run_id=None):
    conn = _ensure_db()
    if not run_id:
        runs = conn.execute("SELECT id FROM runs WHERE status = 'active' ORDER BY created_at DESC LIMIT 1").fetchall()
        if not runs:
            return {"error": "No active run. Run init-run first."}
        run_id = runs[0][0]

    default_demo = {
        "gates": [
            {"id": "gate.discovery.api", "title": "API and data contract probed before implementation", "severity": "critical", "kind": "manual"},
            {"id": "gate.discovery.routes", "title": "Routes and navigation checked", "severity": "major", "kind": "manual"},
            {"id": "gate.implementation.migration", "title": "Required migrations exist or schema change is not needed", "severity": "critical", "kind": "file_exists_or_note"},
            {"id": "gate.build.production", "title": "Production build passes", "severity": "critical", "kind": "command", "command": "npm run build"},
            {"id": "gate.typecheck", "title": "Typecheck passes", "severity": "critical", "kind": "command", "command": "npm run typecheck"},
            {"id": "gate.e2e.demo", "title": "Demo E2E passes without swallowed failures", "severity": "critical", "kind": "command", "command": "npm run e2e"},
            {"id": "gate.screenshots.desktop", "title": "Desktop screenshots exist and are non-empty", "severity": "critical", "kind": "screenshot_set", "min_count": 4, "min_size_kb": 80},
            {"id": "gate.screenshots.mobile", "title": "Mobile screenshot exists", "severity": "critical", "kind": "screenshot_set", "min_count": 1, "min_size_kb": 60},
            {"id": "gate.visual.review", "title": "Screenshots were opened and reviewed", "severity": "critical", "kind": "manual"},
            {"id": "gate.evidence.package", "title": "Evidence package has required files", "severity": "critical", "kind": "file_exists", "paths": ["summary.md", "verdict.json", "changed-files.md", "artifacts.json", "demo-narrative.md", "e2e-report.json"]},
            {"id": "gate.verdict.computed", "title": "Final verdict is computed by ATM", "severity": "critical", "kind": "composite"},
        ]
    }

    gates = default_demo["gates"] if not file_path else _load_yaml_gates(file_path)
    imported = 0
    for g in gates:
        existing = conn.execute("SELECT id FROM gates WHERE run_id = ? AND id = ?", [run_id, g["id"]]).fetchone()
        if not existing:
            spec = {k: v for k, v in g.items() if k not in ("id", "title", "severity", "kind")}
            conn.execute(
                "INSERT INTO gates (run_id, id, title, severity, kind, status, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
                [run_id, g["id"], g["title"], g.get("severity", "major"), g["kind"], json.dumps(spec), now(), now()]
            )
            imported += 1
    conn.commit()
    return {"status": "imported", "count": imported, "run_id": run_id}

def _load_yaml_gates(path):
    import yaml
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("gates", [])

def cmd_next(run_id=None):
    conn = _ensure_db()
    if not run_id:
        r = conn.execute("SELECT id FROM runs WHERE status = 'active' ORDER BY created_at DESC LIMIT 1").fetchone()
        if not r:
            return {"error": "No active run"}
        run_id = r[0]

    # Find next unblocked critical gate
    gate = conn.execute(
        "SELECT id, title, severity, kind, spec_json FROM gates WHERE run_id = ? AND status = 'pending' ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'major' THEN 1 ELSE 2 END, id LIMIT 1",
        [run_id]
    ).fetchone()
    if not gate:
        return {"status": "all_gates_complete", "run_id": run_id}

    spec = json.loads(gate[4]) if gate[4] else {}
    return {
        "run_id": run_id,
        "gate_id": gate[0],
        "title": gate[1],
        "severity": gate[2],
        "kind": gate[3],
        "spec": spec,
        "pass_criteria": f"Run `atm run {gate[0]} -- {' '.join(spec.get('command', ' <command>').split())}`" if gate[3] == "command" else f"Run `atm pass {gate[0]} --evidence <path>`"
    }

def cmd_start(run_id, gate_id):
    conn = _ensure_db()
    g = conn.execute("SELECT status FROM gates WHERE run_id = ? AND id = ?", [run_id, gate_id]).fetchone()
    if not g:
        return {"error": f"Gate '{gate_id}' not found"}
    if g[0] not in ("pending", "blocked"):
        return {"error": f"Gate is {g[0]}, cannot start"}
    conn.execute("UPDATE gates SET status = 'in_progress', updated_at = ? WHERE run_id = ? AND id = ?", [now(), run_id, gate_id])
    _event(conn, run_id, gate_id, "started")
    return {"status": "in_progress", "gate_id": gate_id}

def cmd_fail(run_id, gate_id, reason=None):
    conn = _ensure_db()
    conn.execute("UPDATE gates SET status = 'failed', updated_at = ? WHERE run_id = ? AND id = ?", [now(), run_id, gate_id])
    _event(conn, run_id, gate_id, "failed", {"reason": reason})
    return {"status": "failed", "gate_id": gate_id, "reason": reason}

def cmd_block(run_id, gate_id, reason):
    conn = _ensure_db()
    conn.execute("UPDATE gates SET status = 'blocked', updated_at = ? WHERE run_id = ? AND id = ?", [now(), run_id, gate_id])
    _event(conn, run_id, gate_id, "blocked", {"reason": reason})
    return {"status": "blocked", "gate_id": gate_id, "reason": reason}

def cmd_pass(run_id, gate_id, evidence_path=None, note=None):
    conn = _ensure_db()
    g = conn.execute("SELECT kind, spec_json FROM gates WHERE run_id = ? AND id = ?", [run_id, gate_id]).fetchone()
    if not g:
        return {"error": f"Gate '{gate_id}' not found"}
    kind = g[0]
    spec = json.loads(g[1]) if g[1] else {}

    if kind == "command":
        return {"error": f"Gate '{gate_id}' is a command gate. Use `atm run` instead of `atm pass`."}

    if kind in ("file_exists", "file_exists_or_note"):
        paths = spec.get("paths", [])
        for p in paths:
            if not os.path.exists(p):
                if kind == "file_exists":
                    return {"error": f"Required file '{p}' not found"}
        if kind == "file_exists" and paths and not evidence_path:
            return {"error": "File evidence required for this gate"}

    if evidence_path and not os.path.exists(evidence_path):
        return {"error": f"Evidence file '{evidence_path}' not found"}

    # Visual review gate requires file evidence, not just a note
    if gate_id and "visual" in gate_id and not evidence_path and kind == "manual":
        return {"error": f"Gate '{gate_id}' requires file evidence (screenshot or visual-review.md). Notes alone are not sufficient."}

    sha = _sha256(evidence_path) if evidence_path else None
    conn.execute("UPDATE gates SET status = 'passed', updated_at = ? WHERE run_id = ? AND id = ?", [now(), run_id, gate_id])
    _event(conn, run_id, gate_id, "passed", {"evidence": evidence_path, "note": note})

    if evidence_path:
        conn.execute(
            "INSERT INTO evidence_refs (run_id, gate_id, evidence_type, path, sha256, created_at) VALUES (?, ?, 'file', ?, ?, ?)",
            [run_id, gate_id, evidence_path, sha, now()]
        )
    if note:
        conn.execute(
            "INSERT INTO evidence_refs (run_id, gate_id, evidence_type, note, created_at) VALUES (?, ?, 'note', ?, ?)",
            [run_id, gate_id, note, now()]
        )
    conn.commit()
    return {"status": "passed", "gate_id": gate_id, "evidence": evidence_path}

def cmd_evidence(run_id, gate_id, file_path=None, note=None):
    conn = _ensure_db()
    sha = _sha256(file_path) if file_path else None
    if file_path and not os.path.exists(file_path):
        return {"error": f"File '{file_path}' not found"}
    conn.execute(
        "INSERT INTO evidence_refs (run_id, gate_id, evidence_type, path, sha256, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [run_id, gate_id, "file" if file_path else "note", file_path, sha, note, now()]
    )
    conn.commit()
    return {"status": "recorded", "gate_id": gate_id, "file": file_path}

def cmd_run(run_id, gate_id, command, timeout=300):
    conn = _ensure_db()
    g = conn.execute("SELECT kind FROM gates WHERE run_id = ? AND id = ?", [run_id, gate_id]).fetchone()
    if not g:
        return {"error": f"Gate '{gate_id}' not found"}
    if g[0] != "command":
        return {"error": f"Gate '{gate_id}' is not a command gate"}

    conn.execute("UPDATE gates SET status = 'in_progress', updated_at = ? WHERE run_id = ? AND id = ?", [now(), run_id, gate_id])
    _event(conn, run_id, gate_id, "run_started", {"command": command})
    start = time.time()

    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
    duration_ms = int((time.time() - start) * 1000)
    exit_code = result.returncode

    # Save logs
    log_dir = os.path.join(DB_DIR, "logs", run_id)
    os.makedirs(log_dir, exist_ok=True)
    stdout_path = os.path.join(log_dir, f"{gate_id}.stdout.log")
    stderr_path = os.path.join(log_dir, f"{gate_id}.stderr.log")
    with open(stdout_path, "w") as f: f.write(result.stdout)
    with open(stderr_path, "w") as f: f.write(result.stderr)

    conn.execute(
        "INSERT INTO command_runs (run_id, gate_id, command, exit_code, stdout_path, stderr_path, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [run_id, gate_id, command, exit_code, stdout_path, stderr_path, duration_ms, now()]
    )

    new_status = "passed" if exit_code == 0 else "failed"
    conn.execute("UPDATE gates SET status = ?, updated_at = ? WHERE run_id = ? AND id = ?", [new_status, now(), run_id, gate_id])
    _event(conn, run_id, gate_id, new_status, {"exit_code": exit_code, "duration_ms": duration_ms})

    return {"gate_id": gate_id, "status": new_status, "exit_code": exit_code, "duration_ms": duration_ms, "stdout": result.stdout[:500], "stderr": result.stderr[:500]}

def cmd_status(run_id=None):
    conn = _ensure_db()
    if not run_id:
        r = conn.execute("SELECT id FROM runs WHERE status = 'active' ORDER BY created_at DESC LIMIT 1").fetchone()
        if not r:
            return {"error": "No active run"}
        run_id = r[0]

    run = conn.execute("SELECT * FROM runs WHERE id = ?", [run_id]).fetchone()
    gates = conn.execute("SELECT id, title, severity, kind, status FROM gates WHERE run_id = ? ORDER BY severity, id", [run_id]).fetchall()
    by_status = {}
    for g in gates:
        by_status.setdefault(g[4], []).append({"id": g[0], "title": g[1], "severity": g[2], "kind": g[3]})

    return {
        "run_id": run_id,
        "profile": run[1],
        "status": run[3],
        "verdict": run[6] if len(run) > 6 else None,
        "gates": {"total": len(gates), "by_status": {k: len(v) for k, v in by_status.items()}},
        "gates_list": {k: v for k, v in by_status.items()}
    }

def cmd_verify_integrity(run_id=None):
    """Check for contradictions in the gate ledger. Returns PASS/FAIL."""
    conn = _ensure_db()
    if not run_id:
        r = conn.execute("SELECT id FROM runs WHERE status = 'active' ORDER BY created_at DESC LIMIT 1").fetchone()
        if not r:
            return {"error": "No active run"}
        run_id = r[0]

    issues = []
    gates = conn.execute("SELECT id, status, kind, spec_json FROM gates WHERE run_id = ?", [run_id]).fetchall()
    export_path = os.path.join(DB_DIR, "..", "evidence", run_id, "atm-export.json")

    for gid, status, kind, spec_json in gates:
        spec = _subst_spec(json.loads(spec_json) if spec_json else {}, run_id)
        ev = conn.execute("SELECT COUNT(*) FROM evidence_refs WHERE run_id = ? AND gate_id = ?", [run_id, gid]).fetchone()[0]

        if status == "passed" and ev == 0 and kind not in ("command", "composite"):
            issues.append({"gate": gid, "issue": "passed_without_evidence"})

        if status == "passed" and kind == "command":
            cr = conn.execute("SELECT COUNT(*) FROM command_runs WHERE run_id = ? AND gate_id = ? AND exit_code = 0", [run_id, gid]).fetchone()[0]
            if cr == 0:
                issues.append({"gate": gid, "issue": "command_passed_without_successful_run"})

        if kind in ("file_exists", "file_exists_or_note") and status == "passed":
            for p in spec.get("paths", []):
                if not os.path.exists(p):
                    issues.append({"gate": gid, "issue": f"required_file_missing: {p}"})

        # Check attached evidence files exist
        ev_files = conn.execute("SELECT path FROM evidence_refs WHERE run_id = ? AND gate_id = ? AND evidence_type = 'file' AND path IS NOT NULL", [run_id, gid]).fetchall()
        for (ev_path,) in ev_files:
            if not os.path.exists(ev_path):
                issues.append({"gate": gid, "issue": f"evidence_file_missing: {ev_path}"})

    run = conn.execute("SELECT verdict FROM runs WHERE id = ?", [run_id]).fetchone()
    if run and run[0] in ("demo_done",):
        critical_pending = conn.execute("SELECT COUNT(*) FROM gates WHERE run_id = ? AND severity = 'critical' AND status != 'passed'", [run_id]).fetchone()[0]
        if critical_pending > 0:
            issues.append({"gate": "run", "issue": f"verdict_demo_done_but_{critical_pending}_critical_gates_not_passed"})

    return {"run_id": run_id, "issues": issues, "pass": len(issues) == 0}

# Keep cmd_verify as alias for backward compatibility
cmd_verify = cmd_verify_integrity

def cmd_verdict(run_id=None):
    conn = _ensure_db()
    if not run_id:
        r = conn.execute("SELECT id FROM runs WHERE status = 'active' ORDER BY created_at DESC LIMIT 1").fetchone()
        if not r:
            return {"error": "No active run"}
        run_id = r[0]

    # First verify
    verify = cmd_verify(run_id)
    if verify.get("issues"):
        return {"verdict": "invalid", "run_id": run_id, "issues": verify["issues"], "reason": "Verification found contradictions"}

    gates = conn.execute("SELECT severity, kind, status FROM gates WHERE run_id = ?", [run_id]).fetchall()
    critical_failed = sum(1 for g in gates if g[0] == "critical" and g[2] == "failed")
    critical_pending = sum(1 for g in gates if g[0] == "critical" and g[2] in ("pending", "blocked"))
    major_failed = sum(1 for g in gates if g[0] == "major" and g[2] == "failed")
    all_passed = sum(1 for g in gates if g[2] == "passed")
    total = len(gates)

    if critical_failed > 0:
        verdict = "failed"
        reason = f"{critical_failed} critical gate(s) failed"
    elif critical_pending > 0:
        verdict = "technical_partial"
        reason = f"{critical_pending} critical gate(s) still pending"
    elif all_passed == total:
        verdict = "demo_done"
        reason = "All gates passed, no contradictions"
    elif major_failed > 0:
        verdict = "reviewable_partial"
        reason = f"All critical passed, {major_failed} major gate(s) failed"
    else:
        verdict = "technical_partial"
        reason = f"{total - all_passed} gate(s) pending"

    conn.execute(
        "INSERT INTO verdicts (run_id, verdict, reason_json, created_at) VALUES (?, ?, ?, ?)",
        [run_id, verdict, json.dumps({"reason": reason, "critical_failed": critical_failed, "critical_pending": critical_pending, "major_failed": major_failed, "all_passed": all_passed, "total": total}), now()]
    )
    conn.execute("UPDATE runs SET verdict = ?, updated_at = ? WHERE id = ?", [verdict, now(), run_id])
    conn.commit()

    return {"verdict": verdict, "run_id": run_id, "reason": reason, "summary": {"critical_failed": critical_failed, "critical_pending": critical_pending, "major_failed": major_failed, "passed": all_passed, "total": total}}


def cmd_doctor():
    """Check ATM environment health."""
    issues = []
    # Check bin/atm relative to project root
    bin_path = os.path.join(PROJECT_ROOT, "bin", "atm")
    # In project-wrapper mode, ATM source is external — don't require bin/atm in project
    is_wrapper = "ATM_PROJECT_ROOT" in os.environ and os.environ.get("ATM_PROJECT_ROOT") != os.path.dirname(PROJECT_ROOT)
    if os.path.exists(bin_path):
        bin_status = "exists"
    elif is_wrapper:
        bin_status = "external (scripts/atm)"
    else:
        bin_status = "missing"
        issues.append(f"bin/atm not found at {bin_path}")
    
    # Check DB writable
    try:
        conn = _ensure_db()
        conn.execute("SELECT 1 FROM runs LIMIT 1")
        conn.close()
    except Exception as e:
        issues.append(f"DB not accessible: {e}")
    
    # Check profiles dir
    profiles_dir = os.path.join(os.path.dirname(DB_DIR), "profiles")
    if os.path.exists(profiles_dir):
        profiles = [f for f in os.listdir(profiles_dir) if f.endswith(".yaml") or f.endswith(".yml")]
    else:
        profiles = ["built-in (demo)"]
    
    return {
        "status": "healthy" if not issues else "issues_found",
        "bin_atm": bin_status,
        "db": "writable" if os.access(DB_DIR, os.W_OK) else "readonly",
        "db_path": DB_PATH,
        "profiles": profiles,
        "issues": issues
    }


def cmd_smoke(run_id, args=None):
    """Quick smoke test: doctor → init → import → run → verify → verdict."""
    import tempfile, os, json
    results = []

    # Use temp DB
    tmpdir = tempfile.mkdtemp(prefix="atm-smoke-")
    old_db = os.environ.get("ATM_DB_PATH")
    old_dir = os.environ.get("ATM_DB_DIR")
    os.environ["ATM_DB_PATH"] = os.path.join(tmpdir, "state.db")
    os.environ["ATM_DB_DIR"] = tmpdir

    try:
        # Redo imports with new env
        import importlib
        import gateboard
        importlib.reload(gateboard)
        from gateboard import cmd_init_run, cmd_import_gates, cmd_run, cmd_verify_integrity, cmd_verdict, cmd_doctor, cmd_export

        # Step 1: doctor
        try:
            dr = cmd_doctor()
            results.append((dr.get("status") == "healthy", "doctor", dr.get("status", "?")))
        except Exception as e:
            results.append((False, "doctor", str(e)))

        # Step 2: init-run
        rid = run_id or "smoke-test"
        try:
            ir = cmd_init_run(rid, "demo", None)
            results.append((ir.get("status") == "created", "init-run", ir.get("status", "?")))
        except Exception as e:
            results.append((False, "init-run", str(e)))

        # Step 3: import-gates
        try:
            ig = cmd_import_gates("demo", None)
            results.append((ig.get("count", 0) > 0, "import-gates", f"{ig.get('count', 0)} gates"))
        except Exception as e:
            results.append((False, "import-gates", str(e)))

        # Step 4: run build
        try:
            ru = cmd_run(rid, "gate.build.production", "echo build ok", 30)
            results.append((ru.get("exit_code") == 0, "run build", f"exit {ru.get('exit_code')}"))
        except Exception as e:
            results.append((False, "run build", str(e)))

        # Step 5: verify
        try:
            ve = cmd_verify_integrity(rid)
            results.append((ve.get("pass", False), "verify", "no contradictions" if ve.get("pass") else f"{len(ve.get('issues', []))} issues"))
        except Exception as e:
            results.append((False, "verify", str(e)))

        # Step 6: verdict
        try:
            vd = cmd_verdict(rid)
            results.append((vd.get("verdict") == "technical_partial", "verdict", vd.get("verdict", "?")))
        except Exception as e:
            results.append((False, "verdict", str(e)))

        # Step 7: export
        try:
            ex = cmd_export(rid, tmpdir)
            results.append((ex.get("exported"), "export", ex.get("path", "?")))
        except Exception as e:
            results.append((False, "export", str(e)))

        all_pass = all(r[0] for r in results)
        return {"pass": all_pass, "steps": results, "tmpdir": tmpdir, "run_id": rid}

    finally:
        # Restore env
        if old_db: os.environ["ATM_DB_PATH"] = old_db
        else: os.environ.pop("ATM_DB_PATH", None)
        if old_dir: os.environ["ATM_DB_DIR"] = old_dir
        else: os.environ.pop("ATM_DB_DIR", None)



def cmd_audit(run_id=None, summary_path=None):
    """Contradiction detector: checks summary.md claims against ATM state and evidence files."""
    conn = _ensure_db()
    if not run_id:
        r = conn.execute("SELECT id FROM runs WHERE status = 'active' ORDER BY created_at DESC LIMIT 1").fetchone()
        if not r: return {"error": "No active run"}
        run_id = r[0]

    issues = []
    details = []

    # Load gates with severity from column
    gates = {g[0]: {"status": g[1], "kind": g[2], "severity": g[3], "spec": json.loads(g[4]) if g[4] else {}}
             for g in conn.execute("SELECT id, status, kind, severity, spec_json FROM gates WHERE run_id = ?", [run_id]).fetchall()}
    verdict_data = conn.execute("SELECT verdict, reason_json FROM verdicts WHERE run_id = ? ORDER BY id DESC LIMIT 1", [run_id]).fetchone()
    verdict = verdict_data[0] if verdict_data else None
    prev_verdict = verdict

    # 1. Verdict contradiction: done but gates still pending
    # 1. Verdict contradiction: done but critical gates still pending
    critical_pending = sum(1 for g, info in gates.items() if info["status"] in ("pending", "blocked") and info.get("severity") == "critical")
    if critical_pending > 0:
        issues.append({"type": "verdict_contradiction", "detail": f"{critical_pending} critical gate(s) pending/blocked", "severity": "critical"})
    if verdict in ("demo_done",):
        if critical_pending > 0:
            issues.append({"type": "verdict_demo_done_with_pending", "detail": f"verdict=demo_done but {critical_pending} critical gate(s) pending", "severity": "critical"})

    # 2. Verdict done but total=0
    if verdict_data and not gates:
        issues.append({"type": "empty_run", "detail": "verdict exists but 0 gates", "severity": "critical"})

    # 3. Build gate pending/failed but summary claims build passed
    build_gate = gates.get("gate.build.production", {})
    if build_gate:
        if build_gate.get("status") in ("pending", "failed"):
            details.append({"type": "build_not_passed", "detail": f"build gate is {build_gate.get('status')}", "severity": "major"})

    # 4. Typecheck pending
    type_gate = gates.get("gate.typecheck", {})
    if type_gate and type_gate.get("status") in ("pending",):
        details.append({"type": "typecheck_pending", "detail": "typecheck gate not passed", "severity": "major"})

    # 5. Evidence: file_exists gates with missing files
    for gid, info in gates.items():
        spec = info.get("spec", {})
        if info["status"] == "passed" and info["kind"] in ("file_exists", "file_exists_or_note"):
            for p in spec.get("paths", []):
                # Resolve <run-id> and prepend PROJECT_ROOT
                p_resolved = p.replace("<run-id>", run_id) if "<run-id>" in p else p
                full_path = os.path.join(PROJECT_ROOT, p_resolved) if not os.path.isabs(p_resolved) else p_resolved
                if not os.path.exists(full_path):
                    issues.append({"type": "evidence_file_missing", "detail": f"gate {gid}: required file {full_path} not found", "severity": "critical", "gate": gid})

    # 6. Evidence refs: attached files that don't exist
    ev_files = conn.execute("SELECT gate_id, path FROM evidence_refs WHERE run_id = ? AND evidence_type = 'file' AND path IS NOT NULL", [run_id]).fetchall()
    for gate_id, path in ev_files:
        if path and not os.path.exists(path) and path != "/dev/null":
            issues.append({"type": "evidence_file_missing", "detail": f"gate {gate_id}: evidence file {path} not found", "severity": "critical", "gate": gate_id})

    # 7. Command-backed evidence: smoke passed but no command_run
    smoke_gate = gates.get("gate.tests.smoke", {})
    if smoke_gate and smoke_gate.get("status") == "passed":
        cr = conn.execute("SELECT COUNT(*) FROM command_runs WHERE run_id = ? AND gate_id = 'gate.tests.smoke' AND exit_code = 0", [run_id]).fetchone()[0]
        if cr == 0:
            issues.append({"type": "smoke_not_run_through_atm", "detail": "smoke gate passed but no successful command_run recorded", "severity": "critical"})
        report_files = conn.execute("SELECT path FROM evidence_refs WHERE run_id = ? AND gate_id = 'gate.evidence.report' AND evidence_type = 'file'", [run_id]).fetchall()
        if not report_files:
            details.append({"type": "smoke_report_missing", "detail": "smoke passed but no evidence report attached", "severity": "major"})

    # 8. Compare live DB vs atm-export.json
    for export_dir in [
        os.path.join(PROJECT_ROOT, "agent", "atm", "runs", run_id, "evidence"),
        os.path.join(os.path.dirname(DB_DIR), "evidence", run_id, "atm-export"),
    ]:
        export_path = os.path.join(export_dir, "atm-export.json")
        if os.path.exists(export_path):
            try:
                with open(export_path) as f:
                    export_data = json.load(f)
                export_gates = export_data.get("gates", [])
                if len(export_gates) != len(gates):
                    details.append({"type": "export_mismatch", "detail": f"export has {len(export_gates)} gates, live DB has {len(gates)}", "severity": "major"})
                else:
                    for eg in export_gates:
                        lg = gates.get(eg.get("id", ""), {})
                        if lg and lg.get("status") != eg.get("status"):
                            details.append({"type": "export_status_mismatch", "detail": f"gate {eg.get('id')}: export={eg.get('status')}, live={lg.get('status')}", "severity": "major"})
                # Check verdict
                export_v = export_data.get("verdict", {}).get("verdict") if isinstance(export_data.get("verdict"), dict) else None
                if export_v and export_v != (verdict or prev_verdict):
                    details.append({"type": "export_verdict_mismatch", "detail": f"export says {export_v}, live says {verdict or 'none'}", "severity": "major"})
            except Exception as e:
                details.append({"type": "export_parse_error", "detail": str(e)[:100], "severity": "minor"})
            break

    # 9. Check report semantics if report exists
    report_path = None
    for p in [os.path.join(PROJECT_ROOT, "agent", "atm", "runs", run_id, "evidence", "reconciliation-report.json"),
              os.path.join(os.path.dirname(DB_DIR), "evidence", "wallet-ledger-reconciliation", "reconciliation-report.json")]:
        if os.path.exists(p):
            report_path = p
            break
    if report_path:
        try:
            with open(report_path) as f:
                report_data = json.load(f)
            hs = report_data.get("healthyScenario", {})
            if hs.get("passed") and hs.get("status") and hs["status"] != "balanced":
                details.append({"type": "healthy_not_balanced", "detail": f"healthyScenario passed but status={hs['status']}", "severity": "info"})
        except:
            pass

    # 10. Summary file exists
    if summary_path and not os.path.exists(summary_path):
        issues.append({"type": "summary_missing", "detail": f"summary.md not found at {summary_path}", "severity": "critical"})

    # 10. Service/route files
    service_files = ["product/apps/api/src/services/reconciliation.ts", "product/apps/api/src/routes/reconciliation-routes.ts"]
    for sf in service_files:
        p = os.path.join(PROJECT_ROOT if "PROJECT_ROOT" in dir() else os.path.dirname(DB_DIR), sf)
        if os.path.exists(p):
            details.append({"type": "service_file_exists", "detail": f"{sf} exists", "severity": "info"})

    # Collect status
    critical_issues = [i for i in issues if i.get("severity") == "critical"]
    major_issues = [i for i in issues if i.get("severity") == "major"] + [i for i in details if i.get("severity") == "major"]

    return {
        "run_id": run_id,
        "verdict": verdict,
        "gate_count": len(gates),
        "passed_gates": sum(1 for g in gates.values() if g["status"] == "passed"),
        "critical_issues": len(critical_issues),
        "major_issues": len(major_issues),
        "pass": len(critical_issues) == 0 and len(major_issues) == 0,
        "issues": issues + [d for d in details if d.get("severity") in ("critical", "major")],
        "warnings": [d for d in details if d.get("severity") in ("minor", "info")],
    }


def cmd_export(run_id, output_dir):
    conn = _ensure_db()
    os.makedirs(output_dir, exist_ok=True)

    run = conn.execute("SELECT * FROM runs WHERE id = ?", [run_id]).fetchone()
    gates = conn.execute("SELECT * FROM gates WHERE run_id = ? ORDER BY id", [run_id]).fetchall()
    events = conn.execute("SELECT * FROM gate_events WHERE run_id = ? ORDER BY id", [run_id]).fetchall()
    evidence = conn.execute("SELECT * FROM evidence_refs WHERE run_id = ? ORDER BY id", [run_id]).fetchall()
    commands = conn.execute("SELECT * FROM command_runs WHERE run_id = ? ORDER BY id", [run_id]).fetchall()
    verdicts = conn.execute("SELECT * FROM verdicts WHERE run_id = ? ORDER BY id DESC LIMIT 1", [run_id]).fetchall()

    export = {
        "run": {"id": run[0], "profile": run[1], "contract": run[2], "status": run[3], "verdict": run[6] if len(run) > 6 else None},
        "gates": [{"id": g[0], "title": g[2], "severity": g[3], "kind": g[4], "status": g[5]} for g in gates],
        "events": [{"id": e[0], "gate_id": e[2], "type": e[3], "payload": json.loads(e[4]) if e[4] else None, "at": e[5]} for e in events],
        "evidence": [{"gate_id": e[2], "type": e[3], "path": e[4], "sha256": e[6]} for e in evidence if e[2]],
        "commands": [{"gate_id": c[2], "command": c[3], "exit_code": c[4], "duration_ms": c[7]} for c in commands],
        "verdict": {"verdict": verdicts[0][2], "reason": json.loads(verdicts[0][3]) if verdicts else None} if verdicts else None,
    }

    path = os.path.join(output_dir, "atm-export.json")
    with open(path, "w") as f:
        json.dump(export, f, indent=2)
    return {"exported": True, "path": path}


# ── Review Lifecycle Commands (ATM v0.7.0) ──────────────────────────────

def _review_bundle_path(run_id):
    """Resolve review-bundle directory for a run."""
    return os.path.join(PROJECT_ROOT, "agent", "atm", "runs", run_id, "review-bundle")


def _evidence_path(run_id):
    return os.path.join(PROJECT_ROOT, "agent", "atm", "runs", run_id, "evidence")


def _run_review_bundle_generator(run_id):
    """Attempt to run review-bundle-generator. Not required — bundle may already exist."""
    for candidate in (
        os.path.expanduser("~/.hermes/skills/dogfood/puff-hermes/scripts/review-bundle-generator.py"),
        os.path.join(PROJECT_ROOT, "scripts", "review-bundle-generator.py"),
        os.path.join(os.path.dirname(PROJECT_ROOT), "puff-hermes", "scripts", "review-bundle-generator.py"),
    ):
        if os.path.exists(candidate):
            try:
                result = subprocess.run(
                    [sys.executable, candidate, "--id", run_id, "--project-root", PROJECT_ROOT],
                    capture_output=True, text=True, timeout=30
                )
                return {"ran": True, "path": candidate, "output": result.stdout.strip(), "error": result.stderr.strip() if result.returncode != 0 else None}
            except Exception as e:
                return {"ran": False, "error": str(e)}
    return {"ran": False, "reason": "no review-bundle-generator found"}


def cmd_prepare_review(run_id):
    """Prepare review: export + audit + generate bundle + validate manifest.

    This is NOT optional prose. A run must prepare-review before complete-review.
    """
    steps = []

    # Step 1: Export
    ev_path = _evidence_path(run_id)
    exp = cmd_export(run_id, ev_path)
    steps.append({"step": "export", "ok": exp.get("exported"), "detail": exp.get("path", "")})

    # Step 2: Audit
    audit = cmd_audit(run_id)
    steps.append({"step": "audit", "ok": audit.get("pass"), "detail": f"{audit.get('passed_gates', 0)}/{audit.get('gate_count', 0)} passed, {audit.get('critical_issues', 0)} critical"})

    # Step 3: Review bundle generator
    bg = _run_review_bundle_generator(run_id)
    steps.append({"step": "bundle-generator", "ok": bg.get("ran"), "detail": bg.get("output") or bg.get("reason") or bg.get("error", "unknown")})

    # Step 4: Validate bundle manifest
    bundle_path = _review_bundle_path(run_id)
    manifest_path = os.path.join(bundle_path, "REVIEW_BUNDLE_MANIFEST.md")
    errors = []
    if not os.path.exists(bundle_path):
        errors.append("review-bundle directory not found")
    if not os.path.exists(manifest_path):
        errors.append("REVIEW_BUNDLE_MANIFEST.md not found")
    else:
        # Check for missing (❌) files in manifest
        with open(manifest_path) as f:
            content = f.read()
        missing_lines = [l.strip() for l in content.split("\n") if "❌" in l]
        if missing_lines:
            for ml in missing_lines:
                errors.append(f"missing in bundle: {ml}")
    steps.append({"step": "validate-manifest", "ok": len(errors) == 0, "detail": "; ".join(errors) if errors else "all files present"})

    ok = all(s["ok"] for s in steps)
    return {
        "run_id": run_id,
        "pass": ok,
        "steps": steps,
        "audit": audit,
        "bundle_path": str(bundle_path),
    }


def cmd_review_status(run_id):
    """Check what review artifacts exist and their status.

    Does not make assumptions about which reviewer produced them.
    Validates only that required artifacts exist by convention.
    """
    ev = _evidence_path(run_id)
    bundle = _review_bundle_path(run_id)

    artifacts = {}

    # Bundle
    artifacts["review-bundle"] = os.path.exists(os.path.join(bundle, "REVIEW_BUNDLE_MANIFEST.md"))

    # Find the LATEST text review verdict file
    # Supports version-suffixed files: codex-reviewer-verdict.md, -2.md, -3.md, -final.md
    text_review_paths = []
    base_names = ["codex-reviewer-verdict", "reviewer-verdict"]
    for base in base_names:
        for version in ("", "-2", "-3", "-final", "-re-review"):
            p = os.path.join(ev, f"{base}{version}.md")
            if os.path.exists(p):
                text_review_paths.append(p)

    text_review = None
    # Pick the LAST one (highest version suffix, or latest timestamp if same name)
    if text_review_paths:
        # Sort by file modification time, newest first
        text_review_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        text_review = text_review_paths[0]
    artifacts["text-review"] = text_review
    artifacts["text-review-all"] = text_review_paths

    # Parse verdict from the LATEST text review
    # Look for the final **Status:** line for accurate parsing
    verdict = None
    if text_review:
        with open(text_review) as f:
            content = f.read()
        content_lower = content.lower()
        # First try to find the explicit **Status:** line
        for line in content.split("\n"):
            if "**status" in line.lower() or "## status" in line.lower():
                line_lower = line.lower()
                if "reject" in line_lower:
                    verdict = "reject"
                    break
                elif "requires_fix" in line_lower:
                    verdict = "requires_fix"
                    break
                elif "approve" in line_lower:
                    verdict = "approve"
                    break
        # Fallback: substring match (more prone to false positives)
        if verdict is None:
            if "reject" in content_lower:
                verdict = "reject"
            elif "requires_fix" in content_lower:
                verdict = "requires_fix"
            elif "approve" in content_lower:
                verdict = "approve"

    # Vision review
    vision_review_paths = [
        os.path.join(ev, "codex-vision-review.md"),
        os.path.join(ev, "vision-review.md"),
    ]
    vision_review = None
    vision_skipped = False
    for p in vision_review_paths:
        if os.path.exists(p):
            with open(p) as f:
                c = f.read().lower()
            if "skipped" in c:
                vision_skipped = True
            vision_review = p
            break
    artifacts["vision-review"] = vision_review
    artifacts["vision-review-skipped"] = vision_skipped

    # Fix response
    fix_responses = [
        os.path.join(ev, "codex-reviewer-fix-response.md"),
        os.path.join(ev, "reviewer-fix-response.md"),
    ]
    fix_response = None
    for p in fix_responses:
        if os.path.exists(p):
            fix_response = p
            break
    artifacts["fix-response"] = fix_response

    # Screenshots
    screenshots_dir = os.path.join(ev, "screenshots")
    screenshots = []
    if os.path.exists(screenshots_dir):
        screenshots = sorted([f for f in os.listdir(screenshots_dir) if f.endswith(".png")])
    artifacts["screenshots"] = screenshots
    artifacts["screenshot_count"] = len(screenshots)

    # ATM audit
    audit = cmd_audit(run_id)
    artifacts["audit-pass"] = audit.get("pass")

    # Bundle manifest status
    manifest_path = os.path.join(bundle, "REVIEW_BUNDLE_MANIFEST.md")
    bundle_ok = False
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            content = f.read()
        bundle_ok = "❌" not in content
    artifacts["bundle-complete"] = bundle_ok

    # Auto-assess completeness
    blocking = []
    notes = []

    if not artifacts["review-bundle"]:
        blocking.append("review-bundle not generated")
    if not bundle_ok:
        blocking.append("review-bundle has missing files")
    if not text_review:
        blocking.append("text review not found")

    # Verdict-based assessment
    if verdict in ("reject", "requires_fix"):
        if fix_response:
            notes.append(f"latest verdict is {verdict}, fix-response exists — ready for re-review")
            # Still blocking: fix-response is executor's claim, not approval
            blocking.append(f"latest reviewer verdict is '{verdict}' — needs re-review approval")
        else:
            blocking.append(f"latest reviewer verdict is '{verdict}' and no fix-response")
    elif verdict == "approve":
        notes.append("latest reviewer verdict is approve")
    elif verdict is None and text_review:
        notes.append("could not parse verdict from text review")

    if screenshots and not vision_review:
        blocking.append("screenshots exist but vision review not found")
    if not audit.get("pass"):
        blocking.append("ATM audit does not pass")
    if not artifacts["review-bundle"]:
        blocking.append("review bundle not generated")

    ready_for_complete = (
        verdict == "approve"
        and bundle_ok
        and audit.get("pass")
        and (not screenshots or vision_review)
    )

    return {
        "run_id": run_id,
        "artifacts": artifacts,
        "verdict": verdict,
        "blocking": blocking,
        "notes": notes,
        "pass": len(blocking) == 0,
        "ready_for_complete": ready_for_complete,
    }


def cmd_complete_review(run_id, vision_required=True):
    """Complete review: validate all artifacts, re-audit, and return final status.

    If complete-review fails, final status CANNOT be done/pass.
    This is the anti-false-done lock.

    Critical rule: fix-response is executor's claim, NOT approval.
    Only re-approval by reviewer unlocks DONE.
    """
    # Step 1: Ensure prepare-review was done
    prepare = cmd_prepare_review(run_id)
    if not prepare.get("pass"):
        return {
            "run_id": run_id,
            "pass": False,
            "verdict": "prepare_failed",
            "prepare": prepare,
            "errors": ["prepare-review failed — review lifecycle incomplete"],
        }

    # Step 2: Review status — infrastructure checks only
    # (verdict logic is determined independently below)
    status = cmd_review_status(run_id)
    errors = []
    infra_blockers = ["review-bundle not generated", "review-bundle has missing files",
                      "text review not found", "screenshots exist but vision review not found",
                      "ATM audit does not pass"]
    for b in status.get("blocking", []):
        for ib in infra_blockers:
            if ib in b:
                errors.append(b)
                break

    # Step 3: Re-audit after review
    audit = cmd_audit(run_id)

    # Step 4: Parse reviewer verdict from LATEST review
    verdict = status.get("verdict", "unknown")
    has_fix_response = status["artifacts"].get("fix-response") is not None
    text_review = status["artifacts"].get("text-review")

    # Step 5: Determine final verdict

    # No text review at all → incomplete
    if not text_review:
        final_verdict = "review_incomplete"
        errors.append("no text review found — cannot complete review")

    # Latest reviewer says approve → DONE path
    elif verdict == "approve":
        final_verdict = "review_passed"

    # Latest reviewer says reject/requires_fix → BLOCKED
    # fix-response alone is not enough — needs re-review
    elif verdict == "reject":
        if has_fix_response:
            final_verdict = "ready_for_re_review"
            errors.append("latest reviewer verdict is 'reject' — fix-response written but needs re-review approval")
        else:
            final_verdict = "review_rejected"
            errors.append("reviewer rejected and no fix-response")

    elif verdict == "requires_fix":
        if has_fix_response:
            final_verdict = "ready_for_re_review"
            errors.append("reviewer requires fix — fix-response written but needs re-review approval")
        else:
            final_verdict = "fix_required"
            errors.append("reviewer requires fix and no fix-response")

    else:
        final_verdict = "review_partial"
        if text_review:
            errors.append(f"could not parse reviewer verdict from {text_review}")

    # Check screenshots + vision (only if vision_required)
    if vision_required and status["artifacts"].get("screenshot_count", 0) > 0 and not status["artifacts"].get("vision-review"):
        e = "screenshots exist but vision review not found"
        if e not in errors:
            errors.append(e)

    # Check audit
    if not audit.get("pass"):
        errors.append("final audit fails")
        if final_verdict not in ("review_incomplete",):
            final_verdict = "audit_failed"

    ok = len(errors) == 0

    # Recommendation
    if ok:
        rec = "DONE"
    elif final_verdict == "ready_for_re_review":
        rec = f"RE-REVIEW REQUIRED: {verdict} → fix-response → run reviewer again"
    else:
        rec = f"BLOCKED: {'; '.join(errors)}"

    return {
        "run_id": run_id,
        "pass": ok,
        "verdict": final_verdict,
        "review_verdict": verdict,
        "has_fix_response": has_fix_response,
        "audit_pass": audit.get("pass"),
        "errors": errors,
        "status": status,
        "recommendation": rec,
    }


# ── Deliver — Runtime-Owned Review Lifecycle ────────────────────────────────

DELIVER_FAIL_REASONS = {
    "audit_failed": "ATM audit did not pass",
    "review_bundle_incomplete": "Review bundle is incomplete or missing",
    "review_artifact_missing": "No review artifact found",
    "review_missing": "No reviewer configured and no artifact exists",
    "reviewer_script_failed": "Reviewer script exited with non-zero or was not found",
    "review_rejected": "Latest reviewer verdict is reject/requires_fix",
    "re_review_required": "Fix-response exists but no newer approve re-review",
    "same_session_self_review": "Review was written by executor as self-report in same session",
    "complete_review_failed": "Complete-review did not pass",
    "deliver_not_run": "Deliver was not executed",
}


def _parse_frontmatter_field(content: str, field: str) -> str | None:
    """Parse a YAML frontmatter field from a markdown file.
    
    Looks for lines like:
        field_name: value
    in the frontmatter block (between --- markers).
    Falls back to scanning the whole document.
    """
    field_lower = field.lower()
    lines = content.split("\n")

    # Check for YAML frontmatter (between --- markers)
    if lines and lines[0].strip() == "---":
        in_frontmatter = False
        for line in lines[1:]:
            if line.strip() == "---":
                break
            in_frontmatter = True
            if ":" in line:
                key = line.split(":", 1)[0].strip().lower()
                if key == field_lower:
                    val = line.split(":", 1)[1].strip()
                    return val.strip('"').strip("'")

    # Fallback: scan entire document for field: value
    for line in lines:
        if ":" in line:
            key = line.split(":", 1)[0].strip().lower()
            if key == field_lower:
                val = line.split(":", 1)[1].strip()
                return val.strip('"').strip("'")
    return None


def _parse_review_verdict_extended(verdict_path: str | None) -> dict:
    """Parse a review artifact file and return structured metadata.

    Supports these Status formats:
      Status: approve
      **Status:** approve
      ## Status
      approve

    (multi-line: Status on one line, value on the next)
    """
    if not verdict_path or not os.path.exists(verdict_path):
        return {"found": False, "status": None, "review_mode": None,
                "reviewer_name": None, "reviewer_model": None,
                "executor_model": None, "path": None, "frontmatter": {}}

    with open(verdict_path) as f:
        content = f.read()

    # Parse frontmatter
    frontmatter = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            for line in fm_text.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    frontmatter[k.strip().lower()] = v.strip().strip('"').strip("'")

    # Parse Status — support multiple formats
    status = None
    lines = content.split("\n")
    for i, line in enumerate(lines):
        sl = line.strip()

        # Format 1: "Status: value" or "**Status:** value" or "## Status value"
        if ":" in sl:
            before_colon = sl.split(":", 1)[0].strip().lower().strip("*").strip()
            if before_colon in ("status", "**status", "## status", "final status"):
                val = sl.split(":", 1)[1].strip().strip("*").strip().lower().rstrip(".")
                status = _normalize_status(val)
                if status:
                    break

        # Format 2: "## Status" on one line, "approve" on the next
        if sl.lower().startswith("## status") or sl.lower().startswith("**status**"):
            # Check if the status value is on the same line after the heading
            rest = sl[len("## status"):].strip() if sl.lower().startswith("## status") else sl[len("**status**"):].strip()
            if rest:
                status = _normalize_status(rest.lower().rstrip("."))
                if status:
                    break
            # Or on the next line
            if i + 1 < len(lines):
                next_val = lines[i + 1].strip().lower().rstrip(".")
                status = _normalize_status(next_val)
                if status:
                    break

    return {
        "found": True,
        "status": status or frontmatter.get("status"),
        "review_mode": frontmatter.get("review_mode") or frontmatter.get("review-mode"),
        "reviewer_name": frontmatter.get("reviewer_name") or frontmatter.get("reviewer"),
        "reviewer_model": frontmatter.get("reviewer_model") or frontmatter.get("model"),
        "reviewer_provider": frontmatter.get("reviewer_provider") or frontmatter.get("provider"),
        "executor_model": frontmatter.get("executor_model"),
        "executor_provider": frontmatter.get("executor_provider"),
        "path": verdict_path,
        "frontmatter": frontmatter,
    }


def _normalize_status(val: str) -> str | None:
    """Normalize a status string to a canonical value."""
    val = val.strip().lower().rstrip(".")
    if val in ("approve_technical_done", "approve_demo_done", "approved", "pass", "approve"):
        return "approve"
    if val == "reject":
        return "reject"
    if val == "requires_fix":
        return "requires_fix"
    if val == "partial":
        return "partial"
    if val == "skipped":
        return "skipped"
    if val == "failed":
        return "reject"
    return None


def _classify_review_mode(parsed: dict) -> str:
    """Classify review quality from artifact metadata.

    Returns one of: cross_model, fresh_context_same_model, same_session_self_review,
                    manual, skipped, unknown
    """
    if not parsed.get("found"):
        return "missing"

    # If explicitly declared, trust it
    explicit = parsed.get("review_mode")
    if explicit and explicit in ("cross_model", "fresh_context_same_model",
                                  "same_session_self_review", "manual", "skipped"):
        return explicit

    # Infer from models
    executor = parsed.get("executor_model", "unknown")
    reviewer = parsed.get("reviewer_model", "unknown")

    if executor == "unknown" or reviewer == "unknown":
        return "manual"  # Can't verify → treat as manual

    # same model → fresh_context (not same_session unless explicitly declared)
    if executor == reviewer:
        return "fresh_context_same_model"
    if executor.split("/")[-1] == reviewer.split("/")[-1]:
        return "fresh_context_same_model"

    return "cross_model"


def _get_latest_review_artifact(run_id: str) -> dict:
    """Find the latest review artifact by mtime.

    Searches evidence/ and review-bundle/ for any markdown file matching
    patterns: *verdict*.md, *review*.md, *result*.md
    Excludes REVIEW_BUNDLE_MANIFEST.md (it's a manifest, not a verdict).
    """
    ev = _evidence_path(run_id)
    bundle = _review_bundle_path(run_id)
    paths = []

    for search_dir in [ev, bundle]:
        if not os.path.exists(search_dir):
            continue
        try:
            for f in os.listdir(search_dir):
                if f == "REVIEW_BUNDLE_MANIFEST.md":
                    continue
                if f.endswith(".md") and any(kw in f.lower() for kw in
                    ["verdict", "review", "result"]):
                    full = os.path.join(search_dir, f)
                    if os.path.isfile(full):
                        paths.append(full)
        except:
            pass

    if not paths:
        return {"found": False, "status": None, "review_mode": None,
                "reviewer_name": None, "reviewer_model": None,
                "executor_model": None, "path": None, "frontmatter": {}}

    # Latest by mtime
    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return _parse_review_verdict_extended(paths[0])


def _run_reviewer_script(script_path: str, run_id: str, project_root: str) -> dict:
    """Run an external reviewer script."""
    if not script_path or not os.path.exists(script_path):
        return {"ok": False, "error": "script_not_found", "detail": f"Reviewer script not found: {script_path}"}
    try:
        env = os.environ.copy()
        env["ATM_PROJECT_ROOT"] = project_root
        env["ATM_RUN_ID"] = run_id
        result = subprocess.run(
            ["bash", script_path, run_id, project_root],
            capture_output=True, text=True, timeout=300,
            env=env,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-300:] if result.stdout else "",
            "stderr": result.stderr[-300:] if result.stderr else "",
            "detail": f"Script exited {result.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "script_timeout", "detail": "Reviewer script timed out after 300s"}
    except Exception as e:
        return {"ok": False, "error": "script_error", "detail": str(e)}


def _has_screenshots(run_id: str) -> bool:
    ev = _evidence_path(run_id)
    ss_dir = os.path.join(ev, "screenshots")
    if not os.path.exists(ss_dir):
        return False
    try:
        files = os.listdir(ss_dir)
    except:
        return False
    return any(f.endswith(".png") or f.endswith(".jpg") for f in files)


def _check_fix_response_valid(run_id: str) -> tuple[bool, str]:
    """Check fix-response consistency.
    
    Returns (pass, reason).
    """
    ev = _evidence_path(run_id)
    fix_responses = [
        os.path.join(ev, "reviewer-fix-response.md"),
        os.path.join(ev, "codex-reviewer-fix-response.md"),
    ]
    fix_response = None
    for p in fix_responses:
        if os.path.exists(p):
            fix_response = p
            break
    if not fix_response:
        return True, "no fix-response needed"

    # Find latest approve verdict by mtime
    paths = []
    for base in ["reviewer-verdict", "codex-reviewer-verdict"]:
        for version in ("", "-2", "-3", "-final", "-re-review"):
            p = os.path.join(ev, f"{base}{version}.md")
            if os.path.exists(p):
                parsed = _parse_review_verdict_extended(p)
                if parsed.get("status") == "approve":
                    paths.append((p, os.path.getmtime(p)))

    if not paths:
        return False, "fix-response exists but no approve verdict found — still blocked"

    paths.sort(key=lambda x: x[1], reverse=True)
    latest_approve_path, latest_approve_mtime = paths[0]
    fix_mtime = os.path.getmtime(fix_response)

    if fix_mtime > latest_approve_mtime:
        return False, f"fix-response is newer than latest approve verdict ({os.path.basename(latest_approve_path)}) — needs re-review"
    return True, "fix-response timestamp is valid (older than latest approve)"


def cmd_deliver(run_id: str, profile: str = "demo", reviewer_script: str | None = None,
                skip_review: bool = False, skip_review_reason: str | None = None):
    """Full runtime-owned review lifecycle.

    Vendor-agnostic — does not hardcode Codex, OpenAI, or any model.
    Accepts any reviewer that writes a markdown file with:
      - YAML frontmatter (review_mode, reviewer_model, etc.)
      - Status: approve/reject/requires_fix line

    If --reviewer-script is provided, runs it.
    If --skip-review is set, produces partial outcome.
    If no artifact exists, fails with clear next action.
    """
    steps = {}
    errors = []
    warnings = []

    # ── Build policy for downstream calls ───────────┘
    policy = {
        "vision_required": "if_configured",  # deliver v2: warning, not failure
        "review_skipped": skip_review,
        "parser": "extended",
    }

    # ── Step 1: Audit ────────────────────────────────────────────────────
    audit = cmd_audit(run_id)
    audit_ok = audit.get("pass", False)
    steps["audit"] = {"status": "pass" if audit_ok else "fail"}
    if not audit_ok:
        errors.append("audit_failed")

    # ── Step 2: Prepare Review ────────────────────────────────────────────
    prepare = cmd_prepare_review(run_id)
    bundle_ok = prepare.get("pass", False)
    steps["prepare_review"] = {"status": "pass" if bundle_ok else "fail",
                                "detail": str(prepare.get("steps", []))}
    if not bundle_ok:
        errors.append("review_bundle_incomplete")

    # ── Step 3: Run external reviewer script (if provided) ───────────────
    if reviewer_script:
        script_result = _run_reviewer_script(reviewer_script, run_id, PROJECT_ROOT)
        script_ok = script_result.get("ok", False)
        steps["reviewer_script"] = {
            "status": "pass" if script_ok else "fail",
            "detail": script_result.get("detail", ""),
        }
        if not script_ok:
            errors.append("reviewer_script_failed")

    # ── Step 4: Find and parse review artifact ───────────────────────────
    review = _get_latest_review_artifact(run_id)
    artifact_found = review.get("found", False)
    review_status = review.get("status")
    review_mode = _classify_review_mode(review)

    steps["review_artifact"] = {
        "status": "pass" if artifact_found else "fail",
        "path": review.get("path"),
        "status_parsed": review_status,
        "review_mode": review_mode,
        "reviewer": review.get("reviewer_name") or review.get("reviewer_model") or "unknown",
    }

    if skip_review:
        # Explicit skip — bail to partial outcome
        if not skip_review_reason:
            warnings.append("review skipped without explicit reason — accepted")
        else:
            steps["review_artifact"]["detail"] = skip_review_reason
            warnings.append(f"review skipped: {skip_review_reason}")
        # Partial outcome: skip all remaining review steps
        partial_outcome = True
    else:
        partial_outcome = False
        if not artifact_found:
            errors.append("review_artifact_missing")
        elif review_status in ("reject", "requires_fix"):
            errors.append("review_rejected")
        elif review_status == "skipped":
            errors.append("review_rejected")
        elif review_status == "partial" and profile == "demo":
            if skip_review_reason:
                warnings.append(f"review partial with accepted risk: {skip_review_reason}")
            else:
                errors.append("review_rejected")
        elif review_status is None:
            errors.append("review_rejected")

    # ── Step 5: Review mode classification ───────────────────────────────
    steps["review_quality"] = {
        "status": "info",
        "mode": review_mode,
        "reviewer": review.get("reviewer_name") or "unknown",
        "reviewer_model": review.get("reviewer_model") or "unknown",
        "reviewer_provider": review.get("reviewer_provider") or "unknown",
        "executor_model": review.get("executor_model") or "unknown",
    }

    if partial_outcome:
        # Skip quality check for explicit skip
        steps["review_quality"]["status"] = "skipped"
    elif review_mode == "same_session_self_review":
        errors.append("same_session_self_review")
        steps["review_quality"]["status"] = "fail"
    elif review_mode == "fresh_context_same_model":
        warnings.append("same_model_review_used: executor and reviewer are same model family — acceptable for demo_done with warning")
        steps["review_quality"]["status"] = "warn"
    elif review_mode == "manual":
        warnings.append("manual review recorded — accepted")
        steps["review_quality"]["status"] = "warn"
    elif review_mode == "cross_model":
        steps["review_quality"]["status"] = "pass"
    elif review_mode == "skipped":
        steps["review_quality"]["status"] = "skipped"

    # ── Step 6: Fix-response timestamp check ─────────────────────────────
    if partial_outcome:
        steps["fix_response_check"] = {"status": "skipped", "detail": "review was skipped"}
    else:
        fix_ok, fix_reason = _check_fix_response_valid(run_id)
        steps["fix_response_check"] = {"status": "pass" if fix_ok else "fail", "detail": fix_reason}
        if not fix_ok:
            errors.append("re_review_required")

    # ── Step 7: Vision review check (profile-driven) ─────────────────────
    has_ss = _has_screenshots(run_id)
    vision_status = "skipped"
    if has_ss:
        ev = _evidence_path(run_id)
        vision_paths = [
            os.path.join(ev, "vision-review.md"),
            os.path.join(ev, "reviewer-vision-review.md"),
            os.path.join(ev, "codex-vision-review.md"),
        ]
        vision_found = any(os.path.exists(p) for p in vision_paths)
        if vision_found:
            vision_status = "pass"
        else:
            vision_status = "unavailable"
            if not partial_outcome:
                warnings.append("vision_review_unavailable: screenshots exist but no vision review configured — allowed for demo_done")
    steps["vision_review"] = {"status": vision_status, "screenshots": has_ss}

    # ── Step 8-9: Old locks (only if NOT partial_outcome) ────────────────
    if not partial_outcome:
        review_status_result = cmd_review_status(run_id)
        review_ready = review_status_result.get("pass", False)
        steps["review_status"] = {"status": "pass" if review_ready else "fail"}
        if not review_ready and not any(e in errors for e in ["review_artifact_missing", "review_rejected"]):
            errors.append("complete_review_failed")

        complete = cmd_complete_review(run_id)
        complete_ok = complete.get("pass", False)
        steps["complete_review"] = {"status": "pass" if complete_ok else "fail",
                                     "verdict": complete.get("verdict", "unknown")}
        if not complete_ok and "complete_review_failed" not in errors:
            errors.append("complete_review_failed")
    else:
        steps["review_status"] = {"status": "skipped", "detail": "review was explicitly skipped"}
        steps["complete_review"] = {"status": "skipped", "detail": "review was explicitly skipped"}

    # ── Graded outcome ───────────────────────────────────────────────────
    ok = len(errors) == 0

    if partial_outcome:
        final_verdict = "technical_partial"
        recommendation = f"PARTIAL — review skipped: {skip_review_reason or 'no reason given'}"
    elif ok:
        if review_mode == "cross_model":
            final_verdict = "demo_done"
            recommendation = "DONE — cross-model review passed"
        elif review_mode == "fresh_context_same_model":
            final_verdict = "demo_done"
            recommendation = "DONE — same-model fresh-context review (consider cross-model for stronger claims)"
        elif review_mode == "manual":
            final_verdict = "demo_done"
            recommendation = "DONE — manual review"
        else:
            final_verdict = "demo_done"
            recommendation = "DONE"
    elif errors:
        final_verdict = errors[0]
        rec_map = {
            "audit_failed": "BLOCKED: audit failed — fix gate issues, re-run deliver",
            "review_bundle_incomplete": "BLOCKED: review bundle incomplete — run prepare-review first",
            "review_artifact_missing": "REVIEW MISSING: run a reviewer, then re-run atm deliver",
            "reviewer_script_failed": "BLOCKED: reviewer script failed — check script and re-run deliver",
            "review_rejected": "BLOCKED: review rejected — fix findings, write fix-response, re-run deliver",
            "re_review_required": "RE-REVIEW REQUIRED: fix-response exists but needs newer approve re-review",
            "same_session_self_review": "BLOCKED: same-session self-review detected — use fresh-context or different model",
            "complete_review_failed": "BLOCKED: complete-review did not pass",
        }
        recommendation = rec_map.get(final_verdict, f"BLOCKED: {'; '.join(errors)}")

    return {
        "ok": ok,
        "run_id": run_id,
        "profile": profile,
        "status": final_verdict,
        "steps": steps,
        "errors": errors,
        "warnings": warnings,
        "review": review,
        "recommendation": recommendation,
    }


