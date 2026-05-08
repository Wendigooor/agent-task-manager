#!/usr/bin/env python3
"""
review-bundle-generator — собирает полный evidence bundle для fresh-context reviewer.

Usage:
  python3 scripts/review-bundle-generator.py --id <run-id> [--project-root <path>]

Output:
  agent/atm/runs/<run-id>/review-bundle/
  - REVIEW_BUNDLE_MANIFEST.md
  - contract.md
  - summary.md
  - changed-files.md
  - atm-export.json
  - active-profile.yaml
  - atm-audit.txt
  - source/ (all changed files + route registration)
  - reports/ (smoke report, build/typecheck logs)
  - known-limitations.md
"""

import sys, os, json, shutil, subprocess, argparse, glob, datetime, sqlite3

def build_bundle(run_id: str, project_root: str):
    rdir = os.path.join(project_root, "agent", "atm", "runs", run_id)
    ev = os.path.join(rdir, "evidence")
    bundle = os.path.join(rdir, "review-bundle")
    os.makedirs(bundle, exist_ok=True)
    src = os.path.join(bundle, "source")
    rpt = os.path.join(bundle, "reports")
    os.makedirs(src, exist_ok=True)
    os.makedirs(rpt, exist_ok=True)

    manifest = {}

    def copy_if_exists(name, src_path, dest_subdir=None):
        target = os.path.join(bundle, dest_subdir or ".", name) if dest_subdir else os.path.join(bundle, name)
        if os.path.exists(src_path):
            shutil.copy2(src_path, target)
            manifest[name] = "✅"
        else:
            manifest[name] = "❌ MISSING"

    # Contract
    copy_if_exists("contract.md", os.path.join(rdir, "contract.md"))
    # Summary
    copy_if_exists("summary.md", os.path.join(ev, "summary.md"))
    # Changed files
    copy_if_exists("changed-files.md", os.path.join(ev, "changed-files.md"))
    # ATM export
    copy_if_exists("atm-export.json", os.path.join(ev, "atm-export.json"))
    # Profile — resolve from live ATM DB
    profile_src = None
    profile_name = None
    try:
        db_path = os.environ.get("ATM_DB_PATH") or os.path.join(project_root, "agent", "atm", ".atm", "state.db")
        if os.path.exists(db_path):
            import sqlite3
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT profile FROM runs WHERE id = ?", [run_id]).fetchone()
            conn.close()
            if row and row[0]:
                profile_name = row[0]
    except Exception:
        pass

    if profile_name:
        for ext in (".yaml", ".yml"):
            c = os.path.join(project_root, "agent", "atm", "profiles", profile_name + ext)
            if os.path.exists(c):
                profile_src = c
                break

    if profile_src:
        shutil.copy2(profile_src, os.path.join(bundle, "active-profile.yaml"))
        manifest["active-profile.yaml"] = f"✅ ({profile_name})"
    else:
        manifest["active-profile.yaml"] = "❌ CANNOT RESOLVE — aborting"
        print(f"ERROR: Cannot resolve active profile for run '{run_id}'. Bundle generation failed.")
        sys.exit(1)

    # Audit output — run via subprocess
    audit_txt = os.path.join(bundle, "atm-audit.txt")
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "..", "src", "gate_agent.py"), "audit", "--id", run_id, "--json"],
            capture_output=True, text=True, timeout=30,
            cwd=project_root,
            env={**os.environ, "ATM_PROJECT_ROOT": project_root, "ATM_DB_DIR": os.path.join(project_root, "agent", "atm", ".atm")}
        )
        if proc.returncode == 0:
            with open(audit_txt, "w") as f:
                f.write(proc.stdout)
            manifest["atm-audit.txt"] = "✅"
        else:
            manifest["atm-audit.txt"] = "❌ (audit command failed)"
    except Exception as e:
        manifest["atm-audit.txt"] = f"❌ ({e})"

    # Changed source files — read from changed-files.md
    changed_md = os.path.join(ev, "changed-files.md")
    changed_files = []
    if os.path.exists(changed_md):
        with open(changed_md) as f:
            for line in f:
                if "|" in line and "---" not in line and "File |" not in line:
                    parts = line.split("|")
                    if len(parts) > 1:
                        fname = parts[1].strip()
                        if fname and "/" in fname:
                            changed_files.append(fname)

    # Always include route registration
    for idx_path in [
        os.path.join(project_root, "product", "apps", "api", "src", "index.ts"),
        os.path.join(project_root, "product", "apps", "api", "src", "app.ts"),
    ]:
        if os.path.exists(idx_path):
            dst = os.path.join(src, "index.ts")
            shutil.copy2(idx_path, dst)
            manifest["source/index.ts (route registration)"] = "✅"
            break

    # Also include any config/routes files
    for extra_pattern in [
        "product/apps/api/src/routes/*.ts",
        "product/apps/api/src/services/*.ts",
    ]:
        matches = glob.glob(os.path.join(project_root, extra_pattern))
        for m in matches:
            name = os.path.basename(m)
            # Only copy if it's among changed files
            if any(name in cf for cf in changed_files):
                dst = os.path.join(src, name)
                if not os.path.exists(dst):
                    shutil.copy2(m, dst)
                    manifest[f"source/{name}"] = "✅ (changed)"

    # Copy explicitly mentioned changed files
    for cf in changed_files:
        cf_src = os.path.join(project_root, cf)
        if os.path.exists(cf_src):
            name = os.path.basename(cf)
            dst = os.path.join(src, name)
            if not os.path.exists(dst):
                shutil.copy2(cf_src, dst)
                manifest[f"source/{name}"] = "✅"

    # Reports — smoke, build logs
    for rpt_file in glob.glob(os.path.join(ev, "*-report.json")):
        shutil.copy2(rpt_file, os.path.join(rpt, os.path.basename(rpt_file)))
        manifest[f"reports/{os.path.basename(rpt_file)}"] = "✅"
    for rpt_file in glob.glob(os.path.join(ev, "*.log")):
        shutil.copy2(rpt_file, os.path.join(rpt, os.path.basename(rpt_file)))
        manifest[f"reports/{os.path.basename(rpt_file)}"] = "✅"

    # Known limitations
    summary_src = os.path.join(ev, "summary.md")
    known_limit_src = os.path.join(ev, "known-limitations.md")
    if os.path.exists(known_limit_src):
        shutil.copy2(known_limit_src, os.path.join(bundle, "known-limitations.md"))
        manifest["known-limitations.md"] = "✅"
    elif os.path.exists(summary_src):
        with open(summary_src) as f:
            summary_content = f.read()
        # Check if summary already documents limitations
        if "Known limitation" in summary_content or "known limitation" in summary_content.lower():
            manifest["known-limitations.md"] = "❌ (needs extraction)"
        else:
            # Create placeholder — reviewer should note this
            with open(os.path.join(bundle, "known-limitations.md"), "w") as f:
                f.write(f"# Known Limitations\n\nRun: {run_id}\n\nNo known limitations declared in summary.md.\nReviewer should note this as missing evidence if risks are unstated.\n")
            manifest["known-limitations.md"] = "📄 (auto-generated placeholder)"
    else:
        manifest["known-limitations.md"] = "❌ MISSING"

    # Freshness check
    freshness_issues = []
    try:
        last_commit = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=10, cwd=project_root
        )
        if last_commit.returncode == 0 and last_commit.stdout.strip():
            commit_ts = int(last_commit.stdout.strip())
            commit_dt = datetime.datetime.fromtimestamp(commit_ts)
            bundle_dt = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(bundle, "REVIEW_BUNDLE_MANIFEST.md")))
            if bundle_dt < commit_dt:
                freshness_issues.append(f"Bundle generated {bundle_dt.isoformat()} before last commit {commit_dt.isoformat()}")
    except Exception:
        freshness_issues.append("Could not verify freshness (git unavailable)")

    if freshness_issues:
        manifest["freshness"] = "❌ " + "; ".join(freshness_issues)
    else:
        manifest["freshness"] = "✅ bundle is fresh (after latest commit)"

    # Write manifest
    manifest_lines = []
    manifest_lines.append(f"# Review Bundle Manifest: {run_id}")
    manifest_lines.append(f"\nGenerated: {__import__('datetime').datetime.now().isoformat()}")
    manifest_lines.append(f"Project root: {project_root}")
    manifest_lines.append(f"\n## Files\n")
    for name, status in sorted(manifest.items()):
        manifest_lines.append(f"- {status} {name}")

    # Summary
    passed = sum(1 for v in manifest.values() if v.startswith("✅"))
    partial = sum(1 for v in manifest.values() if v.startswith("📄"))
    missing = sum(1 for v in manifest.values() if v.startswith("❌"))
    manifest_lines.append(f"\n**Summary:** {passed} present, {partial} partial, {missing} missing")

    with open(os.path.join(bundle, "REVIEW_BUNDLE_MANIFEST.md"), "w") as f:
        f.write("\n".join(manifest_lines))

    total = len(manifest)
    print(f"Bundle for '{run_id}': {passed}/{total} present, {missing} missing")
    return bundle

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Run ID")
    ap.add_argument("--project-root", default=os.getcwd(), help="Project root")
    args = ap.parse_args()
    build_bundle(args.id, args.project_root)
