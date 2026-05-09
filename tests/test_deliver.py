#!/usr/bin/env python3
"""Tests for atm deliver — runtime-owned review lifecycle.

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
    cmd_start, cmd_pass, cmd_run,
    cmd_deliver,
    _parse_review_verdict_extended,
    _normalize_status,
    _classify_review_mode,
    _get_latest_review_artifact,
    _evidence_path,
    _review_bundle_path,
    PROJECT_ROOT,
    DB_DIR,
)


@pytest.fixture
def run_id():
    """Create a clean demo run with gates imported."""
    rid = "test-deliver"
    # Init run returns dict, check for error key
    r = cmd_init_run(rid, "demo", "__test_contract__")
    if "error" in r:
        pytest.skip(f"init-run failed: {r['error']}")
    r2 = cmd_import_gates("demo", None, rid)
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
