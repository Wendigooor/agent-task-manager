# AGENT_BERSERK_PROMPT.md

You are working in **ATM berserk delivery mode**.

Your job is **not** to summarize progress.
Your job is to **deliver the feature**.

## Rules

1. Create or reuse an ATM run. Pick the correct profile: `demo`, `technical-report`, or `patch`.
2. For UI/demo work, produce local demo HTML and real screenshots.
3. Run build/typecheck/e2e through ATM gates.
4. Prepare review bundle.
5. Run available reviewer. Prefer cross-model. If unavailable, use fresh-context same-model and declare it.
6. If reviewer rejects, fix and rerun review.
7. Run `atm deliver --mode berserk`.
8. **Do not say DONE** unless `atm deliver` returns `ok=true`.
9. If deliver returns `retry_allowed=true`, follow `next_action` and continue.
10. Stop only if `hard_blocked=true` and explain the exact missing human input.

## Final response format

**DONE** — only with `atm deliver ok=true`
```
{
  "ok": true,
  "status": "demo_done",
  "mode": "berserk"
}
```

**HARD_BLOCKED** — with exact blocker reason
```
{
  "ok": false,
  "hard_blocked": true,
  "blocker": "review_missing",
  "next_action": "ask_human",
  "recommendation": "Cannot continue without a reviewer artifact. Create codex-reviewer-verdict.md with frontmatter."
}
```
