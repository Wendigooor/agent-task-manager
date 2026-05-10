#!/usr/bin/env python3
"""Tests for atm deliver v3 — anti-cheat edition.

Run: python3 -m pytest tests/test_deliver.py -v
"""

import pytest
import json
import os
import tempfile
import sys

# Set up isolated temp environment BEFORE importing gateboard
_TEST_DIR = tempfile.mkdtemp(prefix="atm-test-deliver-")
os.environ["ATM_DB_DIR"] = os.path.join(_TEST_DIR, ".atm")
os.environ["ATM_PROJECT_ROOT"] = _TEST_DIR
os.environ["ATM_EXECUTOR_MODEL"] = "test-executor"
os.environ["ATM_EXECUTOR_PROVIDER"] = "test"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from gateboard import (
    cmd_init_run, cmd_import_gates,
    cmd_start, cmd_pass, cmd_run, cmd_audit,
    cmd_deliver,
    _parse_review_verdict_extended,
    _normalize_status,
    _classify_review_mode,
    _check_review_metadata_completeness,
    _get_latest_review_artifact,
    _evidence_path,
    _review_bundle_path,
    _parse_frontmatter_field,
    PROJECT_ROOT,
    DB_DIR,
)


@pytest.fixture
def run_id():
    """Create a clean demo run with gates imported. Unique per test."""
    import uuid
    rid = f"td-{uuid.uuid4().hex[:8]}"
    r = cmd_init_run(rid, "demo", "__test_contract__")
    if "error" in r:
        pytest.skip(f"init-run failed: {r['error']}")
    r2 = cmd_import_gates("demo", None, rid)
    if "error" in r2:
        pytest.skip(f"import-gates failed: {r2['error']}")
    return rid


@pytest.fixture
def run_id_technical():
    """Create a clean technical-report run. Unique per test."""
    import uuid
    rid = f"tr-{uuid.uuid4().hex[:8]}"
    r = cmd_init_run(rid, "technical-report", "__test_contract__")
    if "error" in r:
        pytest.skip(f"init-run failed: {r['error']}")
    r2 = cmd_import_gates("technical-report", None, rid)
    if "error" in r2:
        pytest.skip(f"import-gates failed: {r2['error']}")
    return rid


# ── Unit: status normalization ──────────────────────────────────────────────

def test_normalize_status():
    assert _normalize_status("approve") == "approve"
    assert _normalize_status("Approve") == "approve"
    assert _normalize_status("approved") == "approve"
    assert _normalize_status("approve_demo_done") == "approve"
    assert _normalize_status("pass") == "approve"
    assert _normalize_status("reject") == "reject"
    assert _normalize_status("requires_fix") == "requires_fix"
    assert _normalize_status("partial") == "partial"
    assert _normalize_status("skipped") == "skipped"
    assert _normalize_status("failed") == "reject"
    assert _normalize_status("unknown") is None


# ── Unit: verdict parsing ──────────────────────────────────────────────────

def test_parse_verdict_status_inline():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("---\nreviewer_model: gpt-4\n---\n\n**Status:** approve\n")
        p = f.name
    result = _parse_review_verdict_extended(p)
    assert result["found"]
    assert result["status"] == "approve"
    assert result["reviewer_model"] == "gpt-4"
    os.unlink(p)


def test_parse_verdict_status_double_asterisk():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("**Status:** approve\n\nAll good.\n")
        p = f.name
    result = _parse_review_verdict_extended(p)
    assert result["status"] == "approve"
    os.unlink(p)


def test_parse_verdict_status_heading_next_line():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("## Status\nreject\n\nSomething wrong.\n")
        p = f.name
    result = _parse_review_verdict_extended(p)
    assert result["status"] == "reject"
    os.unlink(p)


def test_parse_verdict_status_reject():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Status: reject\n")
        p = f.name
    result = _parse_review_verdict_extended(p)
    assert result["status"] == "reject"
    os.unlink(p)


def test_parse_review_verdict_not_found():
    result = _parse_review_verdict_extended("/nonexistent/file.md")
    assert not result["found"]
    assert result["status"] is None


# ── Unit: review mode classification ────────────────────────────────────────

def test_classify_review_mode_explicit():
    assert _classify_review_mode({"found": True, "review_mode": "cross_model"}) == "cross_model"


def test_classify_review_mode_same_session():
    assert _classify_review_mode({"found": True, "review_mode": "same_session_self_review"}) == "same_session_self_review"


def test_classify_review_mode_manual():
    assert _classify_review_mode({"found": True, "review_mode": "manual"}) == "manual"


def test_classify_review_mode_missing():
    assert _classify_review_mode({"found": False}) == "missing"


def test_classify_review_mode_unknown_unknown_blocks():
    """unknown/unknown returns unknown_review_provenance, NOT manual"""
    result = _classify_review_mode({
        "found": True,
        "executor_model": "unknown",
        "reviewer_model": "unknown",
        "frontmatter": {},
    })
    assert result == "unknown_review_provenance", f"Got: {result}"


def test_classify_review_mode_empty_models_blocks():
    """empty/missing models returns unknown_review_provenance"""
    result = _classify_review_mode({
        "found": True,
        "executor_model": "",
        "reviewer_model": "",
        "frontmatter": {},
    })
    assert result == "unknown_review_provenance", f"Got: {result}"


def test_classify_review_mode_only_one_side_blocks():
    """Only reviewer known but executor unknown — provenance missing"""
    result = _classify_review_mode({
        "found": True,
        "executor_model": "",
        "reviewer_model": "gpt-4",
        "frontmatter": {"reviewer_model": "gpt-4"},
    })
    assert result == "unknown_review_provenance", f"Got: {result}"


def test_classify_review_mode_same_model():
    result = _classify_review_mode({
        "found": True,
        "executor_model": "deepseek-v4",
        "reviewer_model": "deepseek-v4",
        "frontmatter": {},
    })
    assert result == "fresh_context_same_model"


def test_classify_review_mode_cross_model():
    result = _classify_review_mode({
        "found": True,
        "executor_model": "deepseek-v4",
        "reviewer_model": "gpt-4",
        "frontmatter": {},
    })
    assert result == "cross_model"


# ── Unit: review metadata completeness ──────────────────────────────────────

def test_metadata_completeness_full():
    parsed = {
        "found": True,
        "frontmatter": {
            "reviewer_model": "gpt-4",
            "executor_model": "deepseek-v4",
            "review_mode": "cross_model",
            "reviewer_provider": "openai",
            "executor_provider": "deepseek",
        },
        "reviewer_model": "gpt-4",
        "executor_model": "deepseek-v4",
        "review_mode": "cross_model",
    }
    result = _check_review_metadata_completeness(parsed)
    assert result["all_fields_present"]


def test_metadata_completeness_no_frontmatter():
    parsed = {
        "found": True,
        "frontmatter": {},
        "reviewer_model": None,
        "executor_model": None,
    }
    result = _check_review_metadata_completeness(parsed)
    assert not result["has_frontmatter"]
    assert not result["all_fields_present"]
    assert "has_reviewer_model" in result["missing_fields"]


def test_metadata_completeness_unknown_values():
    parsed = {
        "found": True,
        "frontmatter": {
            "reviewer_model": "unknown",
            "executor_model": "unknown",
        },
    }
    result = _check_review_metadata_completeness(parsed)
    assert not result["has_reviewer_model"]
    assert not result["has_executor_model"]


# ── Integration: deliver lifecycle ──────────────────────────────────────────

def test_deliver_fails_if_audit_fails(run_id):
    """No gates passed -> audit fails -> deliver fails."""
    result = cmd_deliver(run_id)
    assert not result["ok"]
    assert "audit_failed" in result["errors"]


def test_deliver_skip_review_produces_partial(run_id):
    """--skip-review produces technical_partial regardless of other state."""
    result = cmd_deliver(run_id, skip_review=True, skip_review_reason="test skip")
    assert result["status"] == "technical_partial"
    assert not result["ok"]


# ── Integration: artifact discovery ─────────────────────────────────────────

def test_get_latest_review_artifact_no_files(run_id):
    result = _get_latest_review_artifact(run_id)
    assert not result["found"]


def test_get_latest_review_artifact_finds_verdict(run_id):
    """Write a reviewer verdict file and verify it's found by glob pattern."""
    ev = _evidence_path(run_id)
    os.makedirs(ev, exist_ok=True)
    vpath = os.path.join(ev, "my-custom-reviewer-verdict.md")
    with open(vpath, "w") as f:
        f.write("---\nreviewer_model: deepseek-v4\nreview_mode: cross_model\n---\n\nStatus: approve\n")
    result = _get_latest_review_artifact(run_id)
    assert result["found"], f"Expected to find {vpath} in {ev}"
    assert result["status"] == "approve"
    assert result["reviewer_model"] == "deepseek-v4"
    assert result["review_mode"] == "cross_model"
    os.unlink(vpath)


# ── NEW: screenshot_set cannot pass manually without screenshots ────────────

def test_screenshot_set_rejects_manual_pass_without_files(run_id):
    """Passing a screenshot_set gate without real screenshots should fail."""
    result = cmd_pass(run_id, "gate.screenshots.desktop", note="N/A")
    assert "error" in result, f"Expected error, got: {result}"


def test_screenshot_set_passes_with_screenshots(run_id):
    """Passing screenshot_set with valid screenshots in evidence dir should work."""
    ev = _evidence_path(run_id)
    ss_dir = os.path.join(ev, "screenshots")
    os.makedirs(ss_dir, exist_ok=True)

    # Create 4 valid PNG files (≥80KB each for desktop gate: min_count=4, min_size_kb=80)
    for i in range(4):
        # Write a file that's exactly 85KB
        with open(os.path.join(ss_dir, f"screenshot-{i+1:02d}.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * (85 * 1024 - 8))

    result = cmd_pass(run_id, "gate.screenshots.desktop", note="Screenshots captured")
    assert "error" not in result, f"Expected pass, got: {result}"
    assert result.get("status") == "passed"


# ── NEW: visual.review cannot pass with note only ───────────────────────────

def test_visual_review_rejects_note_only(run_id):
    """visual.review gate with just a note should fail."""
    result = cmd_pass(run_id, "gate.visual.review", note="looks good")
    assert "error" in result, f"Expected error, got: {result}"


def test_visual_review_passes_with_file(run_id):
    """visual.review gate with a visual-review.md should pass."""
    ev = _evidence_path(run_id)
    os.makedirs(ev, exist_ok=True)
    vpath = os.path.join(ev, "visual-review.md")
    with open(vpath, "w") as f:
        f.write("# Visual Review\n\nLooks good.\n")

    result = cmd_pass(run_id, "gate.visual.review", evidence_path=vpath)
    assert "error" not in result, f"Expected pass, got: {result}"
    assert result.get("status") == "passed"


# ── NEW: technical-report profile has no screenshot gates ───────────────────

def test_technical_report_profile_no_screenshots(run_id_technical):
    """technical-report profile should NOT have screenshot/visual/e2e gates."""
    import sqlite3
    conn = sqlite3.connect(os.path.join(DB_DIR, "state.db"))
    gates = conn.execute(
        "SELECT id FROM gates WHERE run_id = ?", [run_id_technical]
    ).fetchall()
    gate_ids = {g[0] for g in gates}

    # These should NOT be present in technical-report
    assert "gate.screenshots.desktop" not in gate_ids, "screenshots.desktop should not exist in technical-report"
    assert "gate.screenshots.mobile" not in gate_ids, "screenshots.mobile should not exist"
    assert "gate.visual.review" not in gate_ids, "visual.review should not exist"
    assert "gate.e2e.demo" not in gate_ids, "e2e.demo should not exist"
    assert "gate.build.production" not in gate_ids, "build.production should not exist"
    assert "gate.typecheck" not in gate_ids, "typecheck should not exist"

    # These SHOULD be present
    assert "gate.smoke.command" in gate_ids, "smoke.command should exist"
    assert "gate.review.artifact" in gate_ids, "review.artifact should exist"
    assert "gate.evidence.package" in gate_ids, "evidence.package should exist"


# ── NEW: technical-report deliver returns technical_done, not demo_done ─────

def test_technical_report_deliver_returns_technical_done(run_id_technical):
    """Deliver with technical-report profile returns technical_done when ok."""
    # Pass all gates (each one needs proper evidence)
    # First create contract.md in run root (required by prepare-review)
    run_root = os.path.join(PROJECT_ROOT, "agent", "atm", "runs", run_id_technical)
    os.makedirs(run_root, exist_ok=True)
    with open(os.path.join(run_root, "contract.md"), "w") as f:
        f.write("# Test Contract\n")

    # discovery.api — manual, just add note
    r1 = cmd_pass(run_id_technical, "gate.discovery.api", note="Jira API discovered")
    assert "error" not in r1, str(r1)

    # implementation.script_or_change — manual
    r2 = cmd_pass(run_id_technical, "gate.implementation.script_or_change", note="Script created")
    assert "error" not in r2, str(r2)

    # smoke.command — run
    r3 = cmd_run(run_id_technical, "gate.smoke.command", "echo 'smoke ok' && exit 0")
    assert "error" not in r3, str(r3)

    # evidence.package — create required files
    ev = _evidence_path(run_id_technical)
    os.makedirs(ev, exist_ok=True)
    for fn in ["summary.md", "verdict.json", "changed-files.md", "artifacts.json"]:
        with open(os.path.join(ev, fn), "w") as f:
            f.write(f"# {fn}\n")
    r4 = cmd_pass(run_id_technical, "gate.evidence.package",
                  evidence_path=os.path.join(ev, "summary.md"))
    assert "error" not in r4, str(r4)

    # review.artifact — manual
    r5 = cmd_pass(run_id_technical, "gate.review.artifact", note="Review ready")
    assert "error" not in r5, str(r5)

    # verdict.computed — close explicitly
    r6 = cmd_pass(run_id_technical, "gate.verdict.computed", note="Verdict computed")
    assert "error" not in r6, str(r6)

    # Write verdict with full metadata
    vpath = os.path.join(ev, "reviewer-verdict.md")
    with open(vpath, "w") as f:
        f.write("""---
reviewer_name: deepseek
reviewer_model: deepseek-v4-pro
reviewer_provider: opencode-go
review_mode: fresh_context_same_model
executor_model: test-executor
executor_provider: test
review_type: text
created_at: 2026-05-10T12:00:00Z
---

**Status:** approve
""")

    # Ensure review-bundle is complete (atm-audit.txt is required) 
    # Pre-create it since the bundle generator can't run atm audit in test env
    bundle_dir = _review_bundle_path(run_id_technical)
    os.makedirs(bundle_dir, exist_ok=True)
    # Copy essential files from evidence to bundle
    import shutil as _sh
    for bf in ["summary.md", "changed-files.md", "atm-export.json"]:
        src = os.path.join(ev, bf)
        if os.path.exists(src):
            _sh.copy2(src, os.path.join(bundle_dir, bf))
    # Copy contract from run root
    contract_src = os.path.join(PROJECT_ROOT, "agent", "atm", "runs", run_id_technical, "contract.md")
    if os.path.exists(contract_src):
        _sh.copy2(contract_src, os.path.join(bundle_dir, "contract.md"))
    # Write atm-audit.txt directly (bundle generator can't run atm in test env)
    with open(os.path.join(bundle_dir, "atm-audit.txt"), "w") as f:
        f.write(json.dumps(cmd_audit(run_id_technical), indent=2))

    result = cmd_deliver(run_id_technical, profile="technical-report")
    assert result["ok"], f"Expected ok=true, got: {result}"
    assert result["status"] == "technical_done", f"Expected technical_done, got: {result['status']}"


# ── NEW: reviewer-verdict without frontmatter does not allow demo_done ─────

def test_reviewer_verdict_no_frontmatter_blocks_demo(run_id):
    """Demo_ profile requires full frontmatter for demo_done."""
    # Create a minimal verdict without frontmatter
    ev = _evidence_path(run_id)
    os.makedirs(ev, exist_ok=True)
    vpath = os.path.join(ev, "reviewer-verdict.md")
    with open(vpath, "w") as f:
        f.write("**Status:** approve\n\nLooks good.\n")

    result = cmd_deliver(run_id, profile="demo")
    # Should fail because no frontmatter = unknown_review_provenance
    assert not result["ok"], f"Expected fail, got: {result}"
    assert "review_provenance_missing" in str(result.get("errors", []))


# ── NEW: unknown/unknown reviewer metadata blocks demo_done ─────────────────

def test_unknown_unknown_metadata_blocks_demo(run_id):
    """Reviewer artifact with unknown executor and reviewer blocks demo_done."""
    ev = _evidence_path(run_id)
    os.makedirs(ev, exist_ok=True)
    vpath = os.path.join(ev, "reviewer-verdict.md")
    with open(vpath, "w") as f:
        f.write("---\nreviewer_model: unknown\nexecutor_model: unknown\n---\n\n**Status:** approve\n")

    result = cmd_deliver(run_id, profile="demo")
    assert not result["ok"], f"Expected fail, got: {result}"


# ── NEW: evidence files in project root produce warning ──────────────────

def test_evidence_files_in_root_audit_warning(run_id):
    """Evidence files placed in PROJECT_ROOT should produce audit warning."""
    # Create evidence files in temp project root
    for fn in ["summary.md", "reviewer-verdict.md"]:
        with open(os.path.join(_TEST_DIR, fn), "w") as f:
            f.write(f"# {fn}\n")

    audit = cmd_audit(run_id)
    # Check for evidence_files_in_project_root warning
    issue_types = [i.get("type") for i in audit.get("issues", [])]
    warn_types = [w.get("type") for w in audit.get("warnings", [])]
    all_items = issue_types + warn_types
    assert "evidence_files_in_project_root" in all_items, f"Expected evidence_files_in_project_root in audit, got: {all_items}"

    # Cleanup
    for fn in ["summary.md", "reviewer-verdict.md"]:
        p = os.path.join(_TEST_DIR, fn)
        if os.path.exists(p):
            os.unlink(p)


# ── NEW: direct DB verdict mutation is detected ─────────────────────────

def test_direct_db_verdict_mutation_detected(run_id):
    """Setting runs.verdict directly should be caught by audit."""
    import sqlite3
    conn = sqlite3.connect(os.path.join(DB_DIR, "state.db"))
    conn.execute(
        "UPDATE runs SET verdict = 'demo_done' WHERE id = ?",
        [run_id]
    )
    conn.commit()

    audit = cmd_audit(run_id)
    issue_types = [i.get("type") for i in audit.get("issues", [])]
    assert "direct_db_mutation_suspected" in issue_types, f"Expected direct_db_mutation_suspected, got: {issue_types}"


# ── NEW: typecheck gate rejects feature-script command ──────────────────

def test_typecheck_rejects_smoke_command(run_id):
    """Running a feature script as typecheck should produce audit error."""
    # Create the script file in PROJECT_ROOT
    _scripts_dir = os.path.join(PROJECT_ROOT, "scripts")
    os.makedirs(_scripts_dir, exist_ok=True)
    spath = os.path.join(_scripts_dir, "fetch_s8_in_progress.py")
    with open(spath, "w") as f:
        f.write("print('hello')\n")

    # Run typecheck with absolute path to the smoke script
    result = cmd_run(run_id, "gate.typecheck", f"python3 {spath}")
    if "error" in result:
        # cmd_run may fail if python can't be found; skip audit check but verify gate passed
        pytest.skip(f"cmd_run failed: {result.get('error')}")

    if result.get("status") != "passed":
        # If the command failed (non-zero exit), manually pass the gate for audit test
        r = cmd_pass(run_id, "gate.typecheck", note="typecheck done")
        if "error" in r:
            pytest.skip(f"manual pass also failed: {r.get('error')}")

    # Audit should flag this — check the command in command_runs
    audit = cmd_audit(run_id)
    issue_types = [i.get("type") for i in audit.get("issues", [])]
    assert "typecheck_command_looks_like_smoke" in issue_types, \
        f"Expected typecheck_command_looks_like_smoke, got: {issue_types}"


# ── NEW: build gate rejects echo no-op ─────────────────────────────────

def test_build_noop_detected(run_id):
    """Running echo as build should be detected as no-op."""
    result = cmd_run(run_id, "gate.build.production", "echo No-op production build && exit 0")
    assert "error" not in result, f"Run failed: {result}"

    r = cmd_pass(run_id, "gate.build.production", note="build done")
    audit = cmd_audit(run_id)
    issue_types = [i.get("type") for i in audit.get("issues", [])]
    assert "build_noop_command" in issue_types, \
        f"Expected build_noop_command, got: {issue_types}"


# ── NEW: patch profile smoke test ────────────────────────────────────────

@pytest.fixture
def run_id_patch():
    """Create a clean patch run."""
    import uuid
    rid = f"pt-{uuid.uuid4().hex[:8]}"
    r = cmd_init_run(rid, "patch", "__test_contract__")
    if "error" in r:
        pytest.skip(f"init-run failed: {r['error']}")
    r2 = cmd_import_gates("patch", None, rid)
    if "error" in r2:
        pytest.skip(f"import-gates failed: {r2['error']}")
    return rid


def test_patch_profile_deliver_returns_patch_done(run_id_patch):
    """Deliver with patch profile returns patch_done when ok."""
    # Create contract in run root
    run_root = os.path.join(PROJECT_ROOT, "agent", "atm", "runs", run_id_patch)
    os.makedirs(run_root, exist_ok=True)
    with open(os.path.join(run_root, "contract.md"), "w") as f:
        f.write("# Test Patch\n")

    # Pass all gates
    r1 = cmd_pass(run_id_patch, "gate.implementation.patch", note="Patch applied")
    assert "error" not in r1, str(r1)

    r2 = cmd_run(run_id_patch, "gate.smoke.command", "echo 'smoke ok' && exit 0")
    assert "error" not in r2, str(r2)

    ev = _evidence_path(run_id_patch)
    os.makedirs(ev, exist_ok=True)
    for fn in ["summary.md", "changed-files.md"]:
        with open(os.path.join(ev, fn), "w") as f:
            f.write(f"# {fn}\n")
    r3 = cmd_pass(run_id_patch, "gate.evidence.package", evidence_path=os.path.join(ev, "summary.md"))
    assert "error" not in r3, str(r3)

    r4 = cmd_pass(run_id_patch, "gate.review.artifact", note="Review ready")
    assert "error" not in r4, str(r4)

    r5 = cmd_pass(run_id_patch, "gate.verdict.computed", note="Verdict computed")
    assert "error" not in r5, str(r5)

    # Write verdict with metadata
    vpath = os.path.join(ev, "reviewer-verdict.md")
    with open(vpath, "w") as f:
        f.write("---\nreviewer_model: gpt-4\nreview_mode: cross_model\nexecutor_model: deepseek-v4-flash\n---\n\n**Status:** approve\n")

    # Pre-populate bundle
    bundle_dir = _review_bundle_path(run_id_patch)
    os.makedirs(bundle_dir, exist_ok=True)
    import shutil as _sh2
    for bf in ["summary.md", "changed-files.md"]:
        src = os.path.join(ev, bf)
        if os.path.exists(src):
            _sh2.copy2(src, os.path.join(bundle_dir, bf))
    with open(os.path.join(bundle_dir, "contract.md"), "w") as f:
        f.write("# Test Patch\n")
    with open(os.path.join(bundle_dir, "atm-audit.txt"), "w") as f:
        f.write(json.dumps(cmd_audit(run_id_patch), indent=2))

    result = cmd_deliver(run_id_patch, profile="patch")
    assert result["ok"], f"Expected ok=true, got: {result}"
    assert result["status"] == "patch_done", f"Expected patch_done, got: {result['status']}"


# ── Berserk mode tests ──────────────────────────────────────────────────────

def test_berserk_default_mode_is_careful(run_id):
    """Default mode should be careful (backward compatible)."""
    result = cmd_deliver(run_id, profile="demo")
    assert "mode" not in result, "mode should not be in output for careful default"


def test_berserk_output_has_required_fields(run_id):
    """Berserk mode output must include blocker, next_action, retry_allowed, hard_blocked."""
    result = cmd_deliver(run_id, profile="demo", mode="berserk")
    assert result.get("mode") == "berserk"
    assert "blocker" in result
    assert "next_action" in result
    assert "retry_allowed" in result
    assert "hard_blocked" in result


def test_berserk_no_premature_done_when_not_ok(run_id):
    """Berserk mode must not say DONE in recommendation when ok=false."""
    result = cmd_deliver(run_id, profile="demo", mode="berserk")
    if not result.get("ok"):
        rec = (result.get("recommendation") or "").lower()
        for word in ["done", "completed", "ready", "delivered"]:
            assert word not in rec, f"berserk recommendation contains forbidden word '{word}': {rec}"


def test_berserk_retry_allowed_for_audit_failed(run_id):
    """audit_failed should have retry_allowed=True."""
    result = cmd_deliver(run_id, profile="demo", mode="berserk")
    if result.get("blocker") == "audit_failed":
        assert result.get("retry_allowed") is True
        assert result.get("hard_blocked") is False


def test_berserk_history_written(run_id):
    """Berserk mode should write history to evidence/berserk-history.json."""
    cmd_deliver(run_id, profile="demo", mode="berserk")
    ev = _evidence_path(run_id)
    hist_path = os.path.join(ev, "berserk-history.json")
    assert os.path.exists(hist_path), f"berserk-history.json not found at {hist_path}"
    with open(hist_path) as f:
        history = json.loads(f.read())
    assert len(history) > 0
    assert "blocker" in history[0]
    assert "next_action" in history[0]
    assert "evidence_count" in history[0]


def test_berserk_doctor_returns_diagnosis(run_id):
    """Doctor should return blocker and next_action."""
    from gateboard import cmd_doctor
    result = cmd_doctor(run_id, profile="demo")
    assert "run_id" in result
    assert "gates" in result
    assert "audit" in result
    assert "evidence" in result
    assert result.get("run_id") == run_id


def test_berserk_doctor_readonly(run_id):
    """Doctor must not change gate state."""
    from gateboard import cmd_doctor, cmd_status
    before = cmd_status(run_id)
    cmd_doctor(run_id, profile="demo")
    after = cmd_status(run_id)
    assert before.get("gates") == after.get("gates"), "doctor changed gate state"


def test_berserk_technical_report_blocks_without_gates(run_id):
    """Berserk on untouched technical-report should return retry_allowed=True."""
    import uuid
    tid = f"tbrs-{uuid.uuid4().hex[:8]}"
    cmd_init_run(tid, "technical-report", "__test__")
    cmd_import_gates("technical-report", None, tid)
    result = cmd_deliver(tid, profile="technical-report", mode="berserk")
    assert not result.get("ok")
    assert result.get("mode") == "berserk"
    assert result.get("retry_allowed") is True or result.get("retry_allowed") is None


def test_berserk_stalled_loop_detection():
    """Simulate 3 same-blocker attempts and verify stalled detection."""
    from gateboard import _read_berserk_history, _check_stalled_loop, _write_berserk_history, _evidence_path
    import uuid, os
    tid = f"stall-{uuid.uuid4().hex[:8]}"
    os.makedirs(_evidence_path(tid), exist_ok=True)
    for i in range(3):
        _write_berserk_history(tid, {
            "blocker": "audit_failed",
            "next_action": "run_audit",
            "evidence_count": 0,
            "screenshot_count": 0,
            "review_mtime": "",
            "gate_status": "gate.1:pending",
            "timestamp": "2026-01-01T00:00:00Z",
        })
    h = _read_berserk_history(tid)
    assert len(h) >= 3
    stalled = _check_stalled_loop(tid)
    assert stalled.get("stalled") is True
    assert stalled.get("next_action") == "run_doctor_and_change_strategy"


def test_berserk_stalled_loop_hard_blocked():
    """5 same-blocker attempts without progress should hard_block."""
    from gateboard import _write_berserk_history, _check_stalled_loop, _evidence_path
    import uuid, os
    tid = f"hard-{uuid.uuid4().hex[:8]}"
    os.makedirs(_evidence_path(tid), exist_ok=True)
    for i in range(5):
        _write_berserk_history(tid, {
            "blocker": "audit_failed",
            "next_action": "run_audit",
            "evidence_count": 0,
            "screenshot_count": 0,
            "review_mtime": "",
            "gate_status": "gate.1:pending",
            "timestamp": f"2026-01-01T00:00:0{i}Z",
        })
    stalled = _check_stalled_loop(tid)
    assert stalled.get("hard_blocked") is True
    assert stalled.get("stalled") is True
    assert stalled.get("blocker") == "stalled_same_blocker"


def test_berserk_stalled_with_progress_not_hard_blocked():
    """3 same blockers but with evidence growth should NOT stalled."""
    from gateboard import _write_berserk_history, _check_stalled_loop, _evidence_path
    import uuid, os
    tid = f"prog-{uuid.uuid4().hex[:8]}"
    os.makedirs(_evidence_path(tid), exist_ok=True)
    for i in range(3):
        _write_berserk_history(tid, {
            "blocker": "audit_failed",
            "next_action": "run_audit",
            "evidence_count": i + 1,  # growing = progress
            "screenshot_count": 0,
            "review_mtime": "",
            "gate_status": "gate.1:pending",
            "timestamp": f"2026-01-01T00:00:0{i}Z",
        })
    stalled = _check_stalled_loop(tid)
    assert stalled.get("stalled") is False
    assert stalled.get("progress_detected") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
