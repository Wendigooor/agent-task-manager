#!/usr/bin/env python3
"""
review-bundle-generator — собирает полный evidence bundle для fresh-context reviewer.

Usage:
  python3 scripts/review-bundle-generator.py \\
    --id <run-id> \\
    --project-root <path> \\
    [--atm-bin <path-to-scripts-atm>]

If --atm-bin is not provided, defaults to <project-root>/scripts/atm.
ATM_DB_DIR and ATM_PROJECT_ROOT are set from --project-root and cleared after.
"""

import sys, os, json, shutil, subprocess, argparse, glob, datetime, sqlite3

def build_bundle(run_id: str, project_root: str, atm_bin: str):
    rdir = os.path.join(project_root, "agent", "atm", "runs", run_id)
    ev = os.path.join(rdir, "evidence")
    bundle = os.path.join(rdir, "review-bundle")
    os.makedirs(bundle, exist_ok=True)
    src_dir = os.path.join(bundle, "source")
    rpt_dir = os.path.join(bundle, "reports")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(rpt_dir, exist_ok=True)

    manifest = {}

    def copy_if_exists(name, src_path, dest_subdir=None):
        target = os.path.join(bundle, dest_subdir or ".", name) if dest_subdir else os.path.join(bundle, name)
        if os.path.exists(src_path):
            shutil.copy2(src_path, target)
            manifest[name] = "✅"
        else:
            manifest[name] = "❌ MISSING"

    # Contract, summary, changed-files, export
    copy_if_exists("contract.md", os.path.join(rdir, "contract.md"))
    copy_if_exists("summary.md", os.path.join(ev, "summary.md"))
    copy_if_exists("changed-files.md", os.path.join(ev, "changed-files.md"))
    copy_if_exists("atm-export.json", os.path.join(ev, "atm-export.json"))

    # Profile — resolve from project DB
    profile_src = None
    profile_name = None
    db_path = os.environ.get("ATM_DB_PATH") or os.path.join(project_root, "agent", "atm", ".atm", "state.db")
    if os.path.exists(db_path):
        try:
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
        detail = profile_name or "none (DB not found or run has no profile)"
        print(f"ERROR: Cannot resolve active profile for run '{run_id}': {detail}")
        manifest["active-profile.yaml"] = f"❌ CANNOT RESOLVE: {detail}"
        sys.exit(1)

    # Audit via project's atm-bin (NEVER gate_agent.py directly)
    audit_txt = os.path.join(bundle, "atm-audit.txt")
    try:
        audit_env = {**os.environ, "ATM_PROJECT_ROOT": project_root, "ATM_DB_DIR": os.path.join(project_root, "agent", "atm", ".atm")}
        proc = subprocess.run(
            [atm_bin, "audit", "--id", run_id, "--json"],
            capture_output=True, text=True, timeout=30,
            cwd=project_root, env=audit_env
        )
        if proc.returncode == 0:
            with open(audit_txt, "w") as f:
                f.write(proc.stdout)
            manifest["atm-audit.txt"] = "✅"
        else:
            err = proc.stderr.strip() or "non-zero exit"
            manifest["atm-audit.txt"] = f"❌ ({err})"
    except Exception as e:
        manifest["atm-audit.txt"] = f"❌ ({e})"

    # Changed source files — read from changed-files.md
    changed_files = []
    changed_md_path = os.path.join(ev, "changed-files.md")
    if os.path.exists(changed_md_path):
        with open(changed_md_path) as f:
            for line in f:
                if "|" in line and "---" not in line and "File |" not in line:
                    parts = line.split("|")
                    if len(parts) > 1:
                        fname = parts[1].strip()
                        if fname and "/" in fname:
                            changed_files.append(fname)

    # Route registration (project-specific paths — adjust for your project)
    for idx_path in [
        os.path.join(project_root, "product", "apps", "api", "src", "index.ts"),
        os.path.join(project_root, "product", "apps", "api", "src", "app.ts"),
    ]:
        if os.path.exists(idx_path):
            dst = os.path.join(src_dir, "index.ts")
            shutil.copy2(idx_path, dst)
            manifest["source/index.ts (route registration)"] = "✅"
            break

    # Copy changed source files — search recursively under project_root
    for cf in changed_files:
        name = os.path.basename(cf)
        dst = os.path.join(src_dir, name)
        if os.path.exists(dst):
            continue  # already copied
        # Try direct path first
        cf_src = os.path.join(project_root, cf)
        if os.path.exists(cf_src):
            shutil.copy2(cf_src, dst)
            manifest[f"source/{name}"] = "✅"
            continue
        # Search recursively (changed-files paths may be relative to subdir)
        matches = glob.glob(os.path.join(project_root, "**", cf), recursive=True)
        if matches:
            shutil.copy2(matches[0], dst)
            manifest[f"source/{name}"] = "✅ (found via search)"
            continue
        # Fallback: try just the filename anywhere
        matches = glob.glob(os.path.join(project_root, "**", name), recursive=True)
        if matches:
            shutil.copy2(matches[0], dst)
            manifest[f"source/{name}"] = "✅ (found via basename search)"
            continue
        manifest[f"source/{name}"] = "❌ NOT FOUND: " + cf

    # If no source files were copied, try git
    if not any(k.startswith("source/") and ("✅" in v or "found" in v) for k, v in manifest.items()):
        try:
            git_files = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1..HEAD"],
                capture_output=True, text=True, timeout=10, cwd=project_root
            )
            if git_files.returncode == 0 and git_files.stdout.strip():
                for gf in git_files.stdout.strip().split("\n"):
                    if not gf.strip():
                        continue
                    name = os.path.basename(gf)
                    dst = os.path.join(src_dir, name)
                    if os.path.exists(dst):
                        continue
                    if os.path.exists(os.path.join(project_root, gf)):
                        shutil.copy2(os.path.join(project_root, gf), dst)
                        manifest[f"source/{name}"] = "✅ (from git diff)"
        except Exception:
            pass

    # Reports
    for rpt_file in glob.glob(os.path.join(ev, "*-report.json")):
        shutil.copy2(rpt_file, os.path.join(rpt_dir, os.path.basename(rpt_file)))
        manifest[f"reports/{os.path.basename(rpt_file)}"] = "✅"
    for rpt_file in glob.glob(os.path.join(ev, "*.log")):
        shutil.copy2(rpt_file, os.path.join(rpt_dir, os.path.basename(rpt_file)))
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
        if "Known limitation" in summary_content or "known limitation" in summary_content.lower():
            manifest["known-limitations.md"] = "❌ (needs extraction)"
        else:
            with open(os.path.join(bundle, "known-limitations.md"), "w") as f:
                f.write(f"# Known Limitations\n\nRun: {run_id}\n\nNo known limitations declared in summary.md.\nReviewer should note this as missing evidence if risks are unstated.\n")
            manifest["known-limitations.md"] = "📄 (auto-generated placeholder)"
    else:
        manifest["known-limitations.md"] = "❌ MISSING"

    # Freshness check — compare current generation time vs latest git commit
    # (Do NOT compare against REVIEW_BUNDLE_MANIFEST.md timestamp — it gets overwritten)
    freshness_issues = []
    now = datetime.datetime.now()
    try:
        last_commit = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=10, cwd=project_root
        )
        if last_commit.returncode == 0 and last_commit.stdout.strip():
            commit_ts = int(last_commit.stdout.strip())
            commit_dt = datetime.datetime.fromtimestamp(commit_ts)
            if now < commit_dt:
                freshness_issues.append(f"Current time {now.isoformat()} before commit {commit_dt.isoformat()}")
    except Exception:
        freshness_issues.append("Could not verify freshness (git unavailable)")

    if freshness_issues:
        manifest["freshness"] = "❌ " + "; ".join(freshness_issues)
    else:
        manifest["freshness"] = "✅ bundle is fresh (after latest commit)"

    # Write manifest
    manifest_lines = [
        f"# Review Bundle Manifest: {run_id}",
        f"\nGenerated: {datetime.datetime.now().isoformat()}",
        f"Project root: {project_root}",
        f"ATM bin: {atm_bin}",
        f"\n## Files\n",
    ]
    for name, status in sorted(manifest.items()):
        manifest_lines.append(f"- {status} {name}")

    passed = sum(1 for v in manifest.values() if v.startswith("✅"))
    partial = sum(1 for v in manifest.values() if v.startswith("📄"))
    missing = sum(1 for v in manifest.values() if v.startswith("❌"))
    manifest_lines.append(f"\n**Summary:** {passed} present, {partial} partial, {missing} missing")

    with open(os.path.join(bundle, "REVIEW_BUNDLE_MANIFEST.md"), "w") as f:
        f.write("\n".join(manifest_lines))

    critical_missing = missing - (1 if "freshness" in str(manifest.get("freshness", "")) else 0)
    print(f"Bundle for '{run_id}': {passed}/{len(manifest)} present, {missing} missing")
    return bundle, missing, passed, len(manifest)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Run ID")
    ap.add_argument("--project-root", default=os.getcwd(), help="Project root (default: cwd)")
    ap.add_argument("--atm-bin", default=None, help="Path to project's scripts/atm (default: <project-root>/scripts/atm)")
    args = ap.parse_args()

    # Resolve atm-bin
    if args.atm_bin:
        atm_bin = args.atm_bin
    else:
        atm_bin = os.path.join(args.project_root, "scripts", "atm")

    if not os.path.exists(atm_bin):
        print(f"ERROR: atm-bin not found at {atm_bin}")
        print("Provide --atm-bin or place scripts/atm in your project root.")
        sys.exit(1)

    # Isolate: we run as an external tool, NOT inside the ATM repo.
    # Clear any ATM env vars pointing at the ATM repo itself.
    old_path = os.environ.pop("ATM_DB_PATH", None)
    old_root = os.environ.pop("ATM_PROJECT_ROOT", None)
    old_dir = os.environ.pop("ATM_DB_DIR", None)

    try:
        build_bundle(args.id, args.project_root, atm_bin)
    finally:
        # Always restore env vars, even on crash/exit(1)
        if old_path: os.environ["ATM_DB_PATH"] = old_path
        if old_root: os.environ["ATM_PROJECT_ROOT"] = old_root
        if old_dir: os.environ["ATM_DB_DIR"] = old_dir
