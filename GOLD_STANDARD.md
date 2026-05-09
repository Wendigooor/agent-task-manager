# Autonomous Delivery Gold Standard

## Purpose

This document is a single canonical standard for autonomous feature delivery.

Use it when an AI agent must take a feature from brief to reviewable result without constant human supervision. It is designed for PUFF, Hermes, Codex, OpenCode, CommandCode, or any similar autonomous coding runner.

The standard is intentionally strict about outcomes, but adaptive about process. The goal is to prevent false completion, weak evidence, flaky demos, and results that technically work but are not worth showing without turning every small task into paperwork.

## Core Rule

The run is not done when code compiles.

The run is done only when the result is:

- functionally correct;
- deterministic enough to replay;
- visually or experientially credible;
- packaged with evidence;
- honestly summarized;
- reviewable by someone who did not watch the run.

If a gate fails, the run must continue, stop as partial, or stop as failed. It must not be marked done.

## ATM Execution Layer

This standard is the constitution. ATM is the runtime.

For Feature, Demo, and Benchmark modes, autonomous work must be executed through an Agent Task Manager / gate runner (`atm`) or an equivalent local CLI/state machine. Markdown alone is not an execution system.

If `atm` is available in the repository or workspace, the agent must use it. If `atm` is not available, the agent must create or use an equivalent minimal gate ledger CLI/state store before implementation. If neither is possible, the maximum allowed verdict is `partial`.

The agent is not allowed to manually declare `demo_done`. Only the ATM computed verdict, or an equivalent deterministic gate runner verdict, may produce `demo_done`.

Required ATM responsibilities:

- [ ] Import relevant gates from the Gold Standard and feature contract.
- [ ] Create the run record before coding.
- [ ] Store gate status transitions as data, not prose.
- [ ] Attach evidence refs to critical and major gates.
- [ ] Run or record verification commands.
- [ ] Compute final status from gates.
- [ ] Export evidence artifacts from the state machine.

Minimum required commands or equivalents:

```text
atm init-run --id <run-id> --mode <mode> --contract <feature-contract> --standard <gold-standard>
atm import-gates --run <run-id>
atm next --run <run-id>
atm start <gate-id>
atm evidence <gate-id> --file <path>
atm pass <gate-id>
atm fail <gate-id> --reason <reason>
atm run-command <gate-id> -- <command>
atm verify --run <run-id>
atm verdict --run <run-id>
atm export --run <run-id> --out <evidence-path>
```

The exact command names may differ, but the semantics must exist.

Manual work is allowed only when recorded:

- [ ] Manual inspection has a gate.
- [ ] Manual inspection has notes.
- [ ] Manual inspection references screenshots/files.
- [ ] Manual inspection cannot override machine-verifiable failures.

Forbidden:

- [ ] No hand-written final verdict that bypasses ATM.
- [ ] No batch-marking all gates at the end.
- [ ] No `passed` critical gate without evidence.
- [ ] No `demo_done` while `atm verify` fails.
- [ ] No `demo_done` while build/typecheck/E2E critical gates are failed, pending, or unverified.

ATM verdict rule:

```text
if atm verdict != summary/verdict:
  stricter status wins

if atm is absent or unused for Feature/Demo/Benchmark:
  max_status = partial
```

## Gate Ledger Rule

Markdown is the source of the standard. A gate ledger is the working control surface.

For Feature, Demo, and Benchmark modes, the agent must convert the relevant checklist items into a tracked gate ledger before implementation starts. The ledger can be a database table, JSON file, SQLite file, task graph, PUFF state, or equivalent structured store. The exact technology is flexible. The behavior is not.

The gate ledger exists to prevent the agent from relying on memory, vibe, or a final report written after the run.

Required:

- [ ] Gate ledger is created before code implementation starts.
- [ ] Gate ledger includes all critical and major gates relevant to the selected mode and feature contract.
- [ ] Each gate has a stable id, severity, status, owner, notes, and evidence refs.
- [ ] Gates start as `pending`, not pre-filled as passed.
- [ ] Gates are updated during the run, not only at the end.
- [ ] Final verdict is computed from gate statuses, not from a prose summary.
- [ ] `demo_done` is forbidden if no gate ledger existed before implementation.
- [ ] `demo_done` is forbidden if any critical gate is `pending`, `failed`, or unapproved `waived`.
- [ ] `partial` is required if the ledger was created after implementation began.

Minimum gate statuses:

- `pending`
- `in_progress`
- `passed`
- `failed`
- `not_applicable`
- `waived`

Minimum severities:

- `critical`: blocks done;
- `major`: blocks demo_done, allows partial;
- `minor`: can be accepted with residual risk.

Minimum ledger fields:

```json
{
  "gate_id": "quality.visual.open_screenshots",
  "title": "Final screenshots were visually reviewed before declaring done",
  "category": "quality",
  "severity": "critical",
  "status": "pending",
  "owner": "agent",
  "phase": "review",
  "evidence_required": true,
  "evidence_refs": [],
  "notes": "",
  "created_at": "...",
  "updated_at": null
}
```

Checkpoint rule:

- [ ] After Phase 0, update discovery gates.
- [ ] After plan creation, update planning gates.
- [ ] After each meaningful bugfix, update related gates and run copy-paste/source search gates.
- [ ] Before E2E, update pre-E2E gates.
- [ ] After E2E, update assertion/evidence gates.
- [ ] After screenshot capture, update visual review gates.
- [ ] Before final response, export gate ledger summary into evidence.

## Operating Modes

Do not apply every gate at full force to every task. Choose a mode before launch and record it in `summary.md`.

### Mode A: Patch

Use for small, localized changes with low user-facing risk.

Required:

- mission;
- changed files;
- verification command;
- concise summary;
- critical gate failures only.

Optional:

- screenshots;
- full timeline;
- demo narrative;
- self-contained demo.

### Mode B: Feature

Use for normal product features with user-facing behavior.

Required:

- mission and scope;
- state or behavior verification;
- summary and verdict;
- changed files;
- evidence artifacts relevant to the feature;
- timeline only for meaningful failures/decisions.

### Mode C: Demo

Use when the result will be shown to stakeholders or compared across models.

Required:

- full evidence folder;
- screenshots or equivalent artifacts;
- narrative artifact;
- quality review;
- E2E/demo stability checks;
- final readiness verdict.

### Mode D: Benchmark

Use when running multiple models/agents in parallel.

Required:

- all Mode C requirements;
- identical mission/scope/budget;
- scoring rubric;
- comparable artifact structure.

Mode checklist:

- [ ] Mode is declared before implementation.
- [ ] Gate set matches the selected mode.
- [ ] Heavy gates are waived when irrelevant, not silently ignored.
- [ ] Waived critical gates force `partial` unless justified by mode.

## Evidence Proportionality Rule

Evidence must be proportional to risk and review value.

- [ ] Low-risk patch does not require seven report files.
- [ ] Stakeholder demo requires narrative and artifacts.
- [ ] Parallel benchmark requires comparable structure.
- [ ] High-risk side effects require deeper discovery.
- [ ] Non-visual backend/API work does not require visual polish gates.

If the agent spends more effort producing paperwork than improving or proving the result, reduce the evidence surface and keep only gates that affect correctness, reproducibility, or reviewability.

## Lessons Integrated From Real Hermes Feedback

This version includes concrete failure modes observed during a real autonomous run. These are not optional notes; they are now part of the standard.

Observed failures:

- E2E was written before API schema was verified.
- DB schema and live fixture data were guessed instead of inspected.
- stale `.js` files shadowed `.tsx` files, so fixes were made in files that were not actually served.
- E2E ran against a dev server even though production build was the only reliable source of truth.
- bundle hash was not checked after fixes.
- frontend route paths were guessed incorrectly.
- screenshots were accepted before DOM/page/state verification was strict enough.
- screenshot file size was used as a weak proxy without content/state checks.
- transaction side effects were not traced end-to-end.
- SSE/live updates were not considered as race-condition sources.
- failures were retried without classification.
- timeline and decisions evidence were too thin to reconstruct what really happened.
- agent declared victory too early after technical gates passed.
- “premium” quality was treated as a one-pass CSS change instead of iterative polish.
- copy-paste bugs were fixed in one file but left in sibling files.
- screenshots existed but did not tell a human-readable story.
- screenshot set lacked diversity and content density checks.
- evidence was written after the run instead of captured in real time.
- discovery was allowed to drift without a hard timebox or stop-and-replan trigger.
- MVP-shaped output was treated as final even though it looked like an admin page, not a product experience.
- screenshots were generated but not opened/reviewed as a human would review them.
- existing trust breakers were ignored as “not my feature” even though they appeared in the demo path.
- E2E scripts logged missing assertions instead of failing the run.
- demo-critical UI actions had API fallbacks, so evidence could pass while the UX was broken.

The purpose of this standard is to make those mistakes structurally difficult to repeat.

## Technical Done Is Not Demo Done

Autonomous agents often stop at the first point where the system technically works. That is not enough for Feature, Demo, or Benchmark mode when the output is user-facing.

Technical done means:

- code compiles;
- API returns expected data;
- basic page renders;
- primary mutation succeeds;
- screenshots exist;
- E2E reports success.

Demo done means:

- the product story is visible without explanation;
- the first artifact has a clear product/commercial idea;
- critical states feel distinct and intentional;
- demo-critical actions happen through the UI;
- trust breakers on the demo path are fixed, not excused;
- evidence would convince someone who did not watch the run.

For stakeholder-facing work, technical done is only a milestone. It is not a final verdict.

Required checks:

- [ ] The run explicitly states whether it reached `technical_done`, `demo_done`, or only `partial`.
- [ ] If the result is user-facing, the agent opened/reviewed final screenshots or equivalent artifacts before declaring done.
- [ ] If the artifact looks like a generic admin/task list when the mission calls for a product experience, the run is not done.
- [ ] If trust breakers are visible on any demo path page, the run is not done.
- [ ] If evidence relies on API shortcuts for demo-critical UI moments, the run is not done.

## Product Experience Contract

Gold Standard defines how to work. Every non-trivial product feature also needs a feature-specific experience contract that defines what “good” looks like for that feature.

The contract must include:

- [ ] product category and intended user emotion;
- [ ] first-screen composition requirements;
- [ ] required visual hierarchy;
- [ ] required narrative moments;
- [ ] required before/after or lifecycle states;
- [ ] required trust breakers that must be fixed even if they are outside the new files;
- [ ] explicit anti-cheapness failures;
- [ ] minimum score threshold if the run is Demo or Benchmark mode.

Feature-specific example:

```text
Do not build a generic task list. Build a campaign hub.
The first screenshot must show campaign hero, reward pool, progress loop, next action, and at least three meaningful cards.
Generic dark cards plus text is a failed visual gate even if the API and E2E pass.
```

If no feature-specific experience contract exists, the agent must create a short one in Phase 1 before implementation.

## Demo Path Ownership Rule

If a page, component, API response, date, balance, realtime update, or state appears in the demo path, it is in scope for quality ownership.

The agent must not say “this is pre-existing” and leave it broken when the defect is visible in evidence.

Required checks:

- [ ] Every page in the demo path has the required readiness/state hooks or an accessibility equivalent.
- [ ] Every visible date, amount, balance, count, and status in final screenshots is credible.
- [ ] No visible `Invalid Date`, `undefined`, `NaN`, placeholder, stale value, or contradictory balance appears in final screenshots.
- [ ] If a pre-existing defect is visible and cannot be fixed within budget, the verdict is `partial`, not `done`.

Trust breaker examples:

- `Invalid Date`;
- inconsistent wallet/topbar balance;
- claim shown as successful while ledger is missing;
- stale count after mutation;
- button works through API but not through UI;
- screenshot path or artifact name belongs to another feature;
- final screenshot shows a hidden error, loading state, or wrong route.

## Required Run Inputs

Before launch, define every item below.

- [ ] Mission is written as one clear sentence.
- [ ] Repository path is specified.
- [ ] Target app/package is specified.
- [ ] Branch or workspace policy is specified.
- [ ] Evidence output path is specified.
- [ ] Product story is defined as a start-to-finish user journey.
- [ ] In-scope files/pages/services are listed.
- [ ] Out-of-scope areas are listed.
- [ ] Time or iteration budget is defined.
- [ ] Verification commands are listed.
- [ ] Required screenshots or artifacts are listed.
- [ ] Stop conditions are defined.
- [ ] Final evidence schema is defined.

Mission template:

```text
Deliver <feature-name> as a demo-ready product increment with deterministic verification and a complete evidence package.
```

Product story template:

```text
<Actor> can <start action>, progress through <main lifecycle>, and see <final result>.
```

## Output Folder

Every run must produce the files required by its operating mode. A full evidence folder is required for Demo and Benchmark modes, not for every small patch.

Full structure:

```text
evidence/<run-id>/
  summary.md
  verdict.md
  gate-ledger.json
  gate-ledger-summary.md
  changed-files.md
  artifacts.json
  timeline.md
  decisions.md
  screenshots/
  logs/
  DEMO_NARRATIVE.md
```

Mode-based output checklist:

- [ ] `summary.md` exists.
- [ ] `changed-files.md` exists.
- [ ] `verdict.md` exists for Feature, Demo, and Benchmark modes.
- [ ] `gate-ledger.json` exists for Feature, Demo, and Benchmark modes.
- [ ] `gate-ledger-summary.md` exists for Demo and Benchmark modes.
- [ ] `artifacts.json` exists when artifacts are produced.
- [ ] `timeline.md` exists when there are meaningful failures, retries, or decisions.
- [ ] `decisions.md` exists when non-trivial decisions were made.
- [ ] `screenshots/` or equivalent demo artifacts exist for visual/stakeholder demos.
- [ ] `DEMO_NARRATIVE.md` exists for Demo and Benchmark modes.
- [ ] `logs/` exists or command output is summarized when verification is non-trivial.

## Mandatory Workflow

### Phase -1: Gate Ledger Bootstrap

- [ ] Read the mission and selected operating mode.
- [ ] Read the Gold Standard sections relevant to the selected mode.
- [ ] Read the feature-specific experience contract, if present.
- [ ] Create the gate ledger before implementation starts.
- [ ] Import or create input gates.
- [ ] Import or create discovery gates.
- [ ] Import or create feature experience gates.
- [ ] Import or create demo path ownership gates.
- [ ] Import or create pre-E2E gates.
- [ ] Import or create E2E hard assertion gates.
- [ ] Import or create visual/evidence/final gates.
- [ ] Mark irrelevant gates as `not_applicable` with a reason.
- [ ] Mark risky waived gates as `waived` with a reason and severity impact.
- [ ] Export the initial gate ledger to evidence before coding.
- [ ] If no gate ledger can be created, downgrade maximum possible verdict to `partial`.

### Phase 0: Discover

- [ ] Read the mission.
- [ ] Inspect the repository structure.
- [ ] Identify existing product surfaces.
- [ ] Identify existing tests/demo scripts.
- [ ] Identify likely risks: flaky E2E, stale build files, missing state hooks, weak UI, fixture drift.
- [ ] Probe every API endpoint on the selected demo path, not unrelated endpoints.
- [ ] Record request payloads, response fields, and response field types.
- [ ] Inspect only DB tables/collections touched by the demo path or changed files.
- [ ] Verify frontend route paths in source code before writing E2E navigation.
- [ ] Check for stale source artifacts that may shadow the edited files.
- [ ] Trace transaction/side-effect chains for money, state, counters, ownership, permissions, or inventory-like resources.
- [ ] Inspect realtime/event channels that can mutate the page during the demo.
- [ ] Write a short implementation plan before editing.
- [ ] Discovery stayed within 15-20% of total run budget.
- [ ] If API/DB/route map remained unclear after 3 discovery iterations, the run stopped and replanned instead of guessing.

### Phase 1: Design The Run

- [ ] Define the minimum complete user story.
- [ ] Define the demo sequence.
- [ ] Define required app states.
- [ ] Define required artifacts.
- [ ] Define quality gates before coding.
- [ ] Define what will not be touched.

### Phase 2: Implement

- [ ] Make scoped code changes only.
- [ ] Follow existing repo patterns.
- [ ] Add deterministic state hooks where needed.
- [ ] Add stable selectors for demo actions.
- [ ] Avoid unrelated refactors.
- [ ] Keep changed files reviewable.
- [ ] After each bugfix, search the whole relevant source tree for the same bug pattern.
- [ ] If the bug is copy-paste shaped, check sibling files and repeated occurrences.
- [ ] Fix all occurrences or document why remaining occurrences are not the same bug.

### Phase 3: Verify

- [ ] Run static checks or typecheck.
- [ ] Run build if applicable.
- [ ] Run unit/integration tests if relevant.
- [ ] Run E2E against a production build/preview where the stack supports it.
- [ ] Record production bundle hash or equivalent build artifact identity.
- [ ] Verify that the expected fix exists in the built artifact when stale-code risk exists.
- [ ] Run deterministic E2E/demo flow.
- [ ] Capture artifacts only after readiness checks pass.
- [ ] Track time/iterations to first valid artifact.
- [ ] If there are 0 valid screenshots/artifacts after 3 verification iterations, stop and replan discovery.
- [ ] Record failures and fixes.

### Phase 4: Self-Review

- [ ] Inspect screenshots or demo artifacts.
- [ ] Reject wrong-page captures.
- [ ] Reject loading skeleton captures.
- [ ] Reject blank or mostly empty key frames.
- [ ] Reject artifacts that do not explain the story.
- [ ] Run up to 3 meaningful polish passes for demo-critical UI/artifacts in Demo/Benchmark mode, unless the quality bar is reached earlier or budget is exhausted.
- [ ] After each polish pass, capture/review new artifacts.
- [ ] After each polish pass, identify the weakest remaining element.
- [ ] Each polish pass has a named target, such as state clarity, content density, visual hierarchy, error visibility, or demo narrative.
- [ ] Padding/color-only changes do not count as meaningful polish unless tied to a visible gate failure.
- [ ] Stop polish when the quality bar is met, budget is exhausted, or remaining improvements are lower-value than the next run.
- [ ] Fix the weakest meaningful issue if budget remains.
- [ ] Rerun verification after meaningful fixes.

### Phase 5: Package

- [ ] Write `summary.md`.
- [ ] Write `verdict.md`.
- [ ] Write `DEMO_NARRATIVE.md` or equivalent story artifact for stakeholder review.
- [ ] Write `tasks.json`.
- [ ] Write `artifacts.json`.
- [ ] Write `timeline.md`.
- [ ] Write `decisions.md`.
- [ ] Write `changed-files.md`.
- [ ] Save screenshots and logs.
- [ ] Create a self-contained demo artifact when the result is intended to be shown quickly.
- [ ] State residual risks.

## Machine-Readable Demo State

Autonomous runs should not rely on screenshots, timing, or visual guessing as the primary source of truth.

Use the least intrusive reliable mechanism available.

Selector preference order:

1. Existing stable test IDs/selectors already accepted by the codebase.
2. Accessibility roles/names when they are stable and intentional.
3. API/backend state checks paired with visible UI assertions.
4. Non-production/demo-only state payloads.
5. New `data-*` attributes in product code, only when they fit local standards.

Required where applicable:

- [ ] Key pages expose a stable page identity through an accepted selector, role, route, or `data-page`.
- [ ] Key pages expose readiness through existing app state, visible content, API state, or `data-ready`.
- [ ] Lifecycle views expose state through DOM, API state, URL, or `data-state`.
- [ ] Important actions have stable selectors, roles, or test IDs.
- [ ] Important result panels have stable selectors or verifiable visible content.
- [ ] Randomness is seeded, mocked, or recorded when it affects output.

Recommended examples:

```html
<main data-page="checkout" data-ready="true">
<section data-feature="payment" data-state="paid">
<button data-testid="submit-payment">
<div data-testid="result-panel" data-result="approved">
```

For complex flows, expose hidden demo state in non-production or demo mode:

```html
<script type="application/json" id="demo-state">
{"page":"checkout","state":"paid","ready":true}
</script>
```

or:

```js
window.__AUTONOMOUS_DEMO_STATE__ = {
  page: "checkout",
  state: "paid",
  ready: true
};
```

Demo state checklist:

- [ ] Runner waits for expected page identity.
- [ ] Runner waits for expected readiness signal.
- [ ] Runner waits for expected lifecycle state when state matters.
- [ ] Runner asserts expected visible data before screenshots.
- [ ] Runner does not use fixed sleeps as the primary readiness mechanism.
- [ ] Any newly added demo/test hook is justified and follows local code standards.
- [ ] If test hooks are not allowed in product code, use non-production state, API assertions, or accessibility selectors.

## Pre-E2E Readiness Gate

No E2E or autonomous demo script may be written or trusted until this gate passes.

This gate is scoped to the selected demo path. Do not map the whole system unless the feature truly requires it.

### API Schema Discovery

- [ ] Health endpoint or equivalent backend readiness check passed.
- [ ] Auth/session setup was tested directly.
- [ ] Every endpoint used by the selected demo path was probed before E2E implementation.
- [ ] Request payload shape was recorded for every endpoint.
- [ ] Response payload fields were recorded for every endpoint.
- [ ] Response field types were recorded, especially object vs string, nullable vs non-null, numeric vs string.
- [ ] Demo IDs such as `gameId`, product IDs, tenant IDs, or fixture IDs were discovered from live data or source constants, not guessed.

Example probe pattern:

```bash
curl -s http://localhost:<api-port>/api/v1/health
curl -s -X POST http://localhost:<api-port>/<endpoint> \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '<known-good-payload>' | jq .
```

### DB And Fixture Discovery

Required when the flow depends on persisted state:

- [ ] Tables/collections touched by the demo path were inspected.
- [ ] Required columns/fields are known.
- [ ] Column/field types are known.
- [ ] NOT NULL or required constraints are known.
- [ ] Foreign keys/relations are known.
- [ ] Existing fixture data is known.
- [ ] Demo data strategy is deterministic: seeded, namespaced, or generated with a run ID.

Example relational checks:

```bash
psql -d <db> -c "\\d <table>"
psql -d <db> -c "SELECT id, name FROM <lookup_table> LIMIT 20;"
```

### Frontend Route Verification

- [ ] Every route visited by E2E is verified in source code.
- [ ] E2E path matches the app route exactly.
- [ ] Dynamic route params are generated from real entities.
- [ ] Redirect/auth guards are understood.

Example:

```bash
rg -n "Route path|path=" src
```

### Source Shadowing And Stale Artifact Check

Required for JS/TS frontend stacks and any compiled app:

- [ ] No stale `.js` files shadow edited `.ts` or `.tsx` files.
- [ ] No stale generated files are served instead of source changes.
- [ ] Build output was cleaned if stale-code risk exists.
- [ ] Served asset hash or equivalent build identifier was recorded.
- [ ] Build identifier changed after meaningful frontend fixes, or the reason it did not is explained.

Example shadow check:

```bash
find src -name "*.js" -print
```

If `.js` files sit next to `.ts`/`.tsx` siblings, classify as `stale_source_shadowing` until proven safe.

### Production-Served E2E

Use the right server mode for the phase.

- [ ] Fast iteration may use a dev server if fresh-code verification is recorded.
- [ ] Final evidence for Demo/Benchmark mode uses production build/preview where practical.
- [ ] Production build is required when stale bundle/source shadowing risk exists.
- [ ] Production build is required before claiming stakeholder-ready frontend evidence unless the stack makes that impractical.
- [ ] If dev server is used for final evidence, the reason is recorded.
- [ ] If dev server is used, hot reload/fresh-code verification is recorded.

Recommended frontend pattern:

```bash
npm run build
npm run preview
```

or:

```bash
npx vite build
npx vite preview --port <port>
```

Efficient workflow:

```text
dev server for quick implementation loops
production build/preview for final evidence
production rebuild whenever stale-code risk is suspected
```

### Side-Effect Chain Discovery

Required for flows that modify durable state:

- [ ] Every write operation in the selected demo path is identified.
- [ ] Every balance/counter/status/ownership update is identified.
- [ ] Transaction boundaries are understood.
- [ ] Duplicate debit/credit/update risks are checked.
- [ ] Idempotency behavior is known or explicitly out of scope.

### Realtime/Event Interference Check

Required when SSE, WebSocket, polling, subscriptions, queues, or background workers can update the page:

- [ ] Realtime channels affecting demo pages were searched.
- [ ] Events that can race with API responses are listed.
- [ ] E2E waits for final rendered state after realtime updates settle.
- [ ] Polling/refetch behavior is accounted for.

Example:

```bash
rg -n "broadcast|SSE|EventSource|WebSocket|subscribe|poll|refetch" src
```

## E2E Stability Gate

If E2E fails or flakes frequently, the run is not done.

Failure classes:

- readiness failure;
- state race;
- fixture drift;
- build artifact drift;
- randomness drift;
- environment failure.
- auth failure;
- API contract mismatch;
- route mismatch;
- stale source shadowing;
- page crash;
- weak artifact;
- realtime interference.

Required E2E checks:

- [ ] Failures are classified before retrying.
- [ ] Same failure class is not blindly retried more than 3 times.
- [ ] Non-retryable failure classes are debugged instead of retried.
- [ ] Test data is namespaced or deterministic.
- [ ] Auth/session readiness is explicitly checked.
- [ ] Stale build or generated files are checked if behavior looks old.
- [ ] Screenshots are captured after DOM/state assertions.
- [ ] Residual flake risk is documented if present.

Failure taxonomy:

| Failure class | Retry? | Required action |
|---|---:|---|
| `auth_failure` | yes | recreate session/user, verify token storage and guards |
| `api_contract_mismatch` | no | repro with direct API call, update payload/response handling |
| `api_error` | limited | capture response body, classify server vs data issue |
| `route_mismatch` | no | verify app route source and E2E URL |
| `wrong_page` | no | save debug screenshot, inspect redirects/auth/route |
| `missing_state_hook` | no | first verify selector/test expectation; then use existing signal; add hook only if no acceptable signal exists |
| `stale_source_shadowing` | no | remove/resolve shadow files, rebuild, record hash |
| `stale_bundle` | no | rebuild/restart served app, verify build artifact identity |
| `page_crash` | no | capture console/page error, fix component/runtime issue |
| `weak_artifact` | limited | verify DOM, improve UI/capture, retake |
| `timeout` | limited | inspect readiness condition, then adjust wait if valid |
| `realtime_interference` | limited | wait for settled state or control subscription/polling |

Stable E2E pattern:

```text
create deterministic fixture
navigate to page
wait data-page
wait data-ready
perform action via data-testid
wait data-state
assert visible result
capture screenshot
write artifact metadata
```

E2E acceptance:

- [ ] Demo flow passed.
- [ ] Important states were asserted before capture.
- [ ] Screenshot sequence matches the story.
- [ ] Any flaky behavior is classified and documented.
- [ ] No non-retryable failure was hidden by a later successful retry.

### Hard Assertion Rule

For Demo and Benchmark modes, E2E must fail loudly when a required condition is missing. Logging is not an assertion.

Required:

- [ ] Missing required selector throws and exits non-zero.
- [ ] Wrong `data-page` throws and exits non-zero.
- [ ] Missing `data-ready="true"` throws and exits non-zero.
- [ ] Wrong required `data-state` throws and exits non-zero.
- [ ] Missing reward/ledger/balance proof throws and exits non-zero.
- [ ] Browser page errors throw or mark the run failed unless explicitly classified as irrelevant.
- [ ] Console errors are counted and fail the run unless explicitly classified as irrelevant.
- [ ] Every required assertion appears in a machine-readable report with `passed`, `failed`, or `not_applicable`.

Forbidden for demo-critical steps:

- [ ] No API fallback for UI claim, submit, accept, purchase, reward, or any action that is part of the user story.
- [ ] No “if button missing, call API instead”.
- [ ] No “state missing, continue to screenshot”.
- [ ] No “report says passed” if any required assertion was only logged.

Allowed:

- API setup before the visible journey starts;
- API gameplay trigger only when the UI surface is explicitly out of scope and the report explains why;
- API verification after the visible journey, such as checking DB/API side effects.

## Visual And Experience Quality Gate

This gate applies to UI screenshots, generated demos, reports, terminal demos, CLI output, or any artifact intended for human review.

Quality checklist:

- [ ] The main artifact has a clear focal point.
- [ ] The result is understandable without chat history.
- [ ] The final state is visible.
- [ ] The artifact does not look accidental or half-loaded.
- [ ] The artifact has enough content density to feel real.
- [ ] Key states are visually or structurally distinct.
- [ ] There is no obvious layout overlap.
- [ ] No key text is clipped or unreadable.
- [ ] The result is comfortable to show to a stakeholder.

Screenshot rejection checklist:

- [ ] No wrong page.
- [ ] No unintended login page.
- [ ] No loading skeleton as final proof.
- [ ] No blank or mostly empty key frame.
- [ ] No duplicate state without story value.
- [ ] No key result off-screen.
- [ ] No visible crash or error.
- [ ] Screenshot size is above the project threshold or has explicit DOM/content verification.
- [ ] Screenshot metadata records the verified `data-page` and `data-state` where applicable.

Screenshot size guideline:

| Size at 1440x900 full-page capture | Likely content | Action |
|---|---|---|
| `< 100KB` | login, spinner, blank, error, or tiny page | reject |
| `100-150KB` | suspicious/minimal content | require DOM verification |
| `150-300KB` | plausible normal UI | accept only with DOM/state verification |
| `300KB+` | dense UI/data-heavy page | accept only with DOM/state verification |

Size is never sufficient by itself. It is only a cheap suspicion signal.

### Screenshot Diversity Gate

The screenshot set must tell a story, not merely prove that multiple pages exist.

- [ ] Each screenshot represents a distinct state, page, or narrative moment.
- [ ] No two screenshots show effectively the same state unless comparison is intentional.
- [ ] File sizes, DOM structure, or meaningful element counts were compared for suspicious sameness.
- [ ] Diversity check result is recorded in `artifacts.json`.
- [ ] If screenshots are technically different but visually indistinguishable, improve the demo path or choose better states.

Suggested cheap checks:

```text
Compare screenshot sizes.
Compare visible text length.
Compare count of buttons, links, inputs, and data-testid elements.
Compare data-page and data-state.
```

If all screenshots are within a narrow size band and have similar DOM/content counts, classify as `low_demo_diversity` and review manually.

### Content Density Gate

Screenshot size can be inflated by gradients, backgrounds, or decoration. Every key screenshot must contain meaningful content.

- [ ] Visible text length was checked for each key screenshot.
- [ ] Meaningful DOM element count was checked for each key screenshot.
- [ ] Key result/state text is present.
- [ ] Decorative/background-heavy screenshots are not accepted as proof.

Suggested minimum for application UI:

```text
visible text length: > 50 characters
meaningful elements: > 20 nodes or justified by artifact type
```

These thresholds are suspicion signals, not universal truth. If a sparse artifact is intentional, explain it in `artifacts.json`.

### Demo Narrative Gate

Every stakeholder-facing run needs a narrative artifact.

Required file:

```text
DEMO_NARRATIVE.md
```

or a clearly equivalent section/artifact.

It must include:

- [ ] User journey in human terms.
- [ ] Ordered screenshot/artifact list.
- [ ] What each screenshot shows.
- [ ] Why each screenshot matters.
- [ ] Final outcome/payoff.
- [ ] What is intentionally out of scope.

Template:

```markdown
# Demo: <Feature>

## User Journey
1. <User starts at...> -> <artifact>
2. <User performs...> -> <artifact>
3. <System reaches...> -> <artifact>

## Artifact Map
| Artifact | What it shows | Why it matters |
|---|---|---|
| 01-start.png | ... | ... |
```

### Self-Contained Demo Gate

If the result is meant for a stakeholder demo, create a fast-open artifact that explains the result without requiring the full evidence folder.

Acceptable formats:

- standalone HTML file;
- screenshot collage;
- short markdown README with embedded relative screenshots;
- generated report page;
- short video/GIF if the stack supports it.

Checklist:

- [ ] Self-contained demo artifact exists or is explicitly not applicable.
- [ ] It opens without the development server when practical.
- [ ] It can be understood in about 10-30 seconds.
- [ ] It references artifacts by relative paths.
- [ ] It does not reference missing files.
- [ ] It is listed in `artifacts.json`.

Quality labels:

- `A`: leadership-ready, strong result.
- `B`: review-ready with minor caveats.
- `C`: functional but not presentation-ready.
- `D`: incomplete or unstable.

Do not mark `C` or `D` as done.

## Evidence Schema

### summary.md

Must include:

- [ ] Run ID.
- [ ] Mission.
- [ ] Status: `done`, `partial`, or `failed`.
- [ ] What changed.
- [ ] What was verified.
- [ ] Artifact list.
- [ ] Known limitations.
- [ ] Final review readiness.

### verdict.md

Must include:

- [ ] Functional verdict.
- [ ] Determinism verdict.
- [ ] Evidence verdict.
- [ ] Quality verdict.
- [ ] Demo/review verdict.
- [ ] Weakest remaining area.

Allowed review readiness:

- `review-ready`;
- `partial-reviewable`;
- `not-reviewable`.

### tasks.json

Each task should include:

- [ ] ID.
- [ ] Title.
- [ ] Status.
- [ ] Start timestamp.
- [ ] Completion timestamp.
- [ ] Result.
- [ ] Evidence references.
- [ ] Failure class when a task failed or retried.
- [ ] Retry count when applicable.
- [ ] Verification command or artifact that closed the task.

### artifacts.json

Each artifact should include:

- [ ] Type.
- [ ] Path.
- [ ] State or purpose.
- [ ] Size or basic metadata if applicable.
- [ ] Verification source: selector, command, state hook, or human review.
- [ ] For screenshots: viewport, `data-page`, `data-state`, and size.
- [ ] For screenshots: visible text length and meaningful element count when applicable.
- [ ] For screenshot sets: diversity check summary.
- [ ] For logs: command, exit status, and summarized result.
- [ ] For builds: build hash or artifact identifier when applicable.

### timeline.md

Must include enough sequence to reconstruct the run:

- [ ] Run start.
- [ ] Discovery/preflight start and result.
- [ ] Implementation phases.
- [ ] Verification commands.
- [ ] Failures with classification.
- [ ] Retries with reason.
- [ ] Fixes applied.
- [ ] Evidence capture.
- [ ] Final gate result.
- [ ] Entries were appended during the run, not reconstructed only at the end.
- [ ] Significant actions include timestamp, phase, action, result, decision, failure class if any, and artifact reference if any.

A one-line timeline is not acceptable for a non-trivial autonomous run.

### decisions.md

Must include meaningful decisions:

- [ ] Scope decisions.
- [ ] API/schema discoveries that changed implementation.
- [ ] DB/fixture discoveries that changed implementation.
- [ ] Build/server strategy decisions.
- [ ] E2E failure classifications.
- [ ] Quality tradeoffs.
- [ ] Reasons for accepting partial work, if applicable.
- [ ] Each decision is written as context -> decision -> reason.

An empty or one-line decisions file is acceptable only if the run was trivial and the summary explains why.

### DEMO_NARRATIVE.md

Required for stakeholder-facing runs.

Must include:

- [ ] User journey.
- [ ] Artifact map.
- [ ] Why each artifact exists.
- [ ] Final outcome.
- [ ] What the reviewer should conclude.

### Self-contained demo artifact

Required unless explicitly not applicable.

Must include:

- [ ] Path to artifact.
- [ ] How it opens.
- [ ] Whether it requires a server.
- [ ] Linked screenshots/assets verified to exist.
- [ ] Listed in `artifacts.json`.

### changed-files.md

Must include:

- [ ] File path.
- [ ] Purpose of change.
- [ ] Risk level.
- [ ] Verification related to the file.
- [ ] Whether the file is source, generated, build artifact, test, or evidence.
- [ ] Whether stale/shadowed sibling files were checked when applicable.

## Stop Conditions

The agent may stop only when one of these is true:

- [ ] All gates pass and the result is `review-ready`.
- [ ] Budget is exhausted and the result is marked `partial` or `failed`.
- [ ] Continuing requires unsafe or out-of-scope action.
- [ ] Remaining improvements are documented and clearly lower-value than the next run.

Hard stop rules:

- [ ] If tests pass but evidence is weak, do not mark done.
- [ ] If screenshots look good but state verification is brittle, do not mark done.
- [ ] If evidence exists but cannot convince another reviewer, do not mark done.
- [ ] If E2E flakes repeatedly without classification, do not mark done.
- [ ] If final summary hides known weakness, do not mark done.

## Escalation Policy

Autonomy does not mean wasting the whole budget on a blocker that a human can resolve quickly.

The agent may escalate when:

- [ ] the same critical failure class repeats after allowed retries;
- [ ] a type/schema conflict blocks progress and the intended product behavior is ambiguous;
- [ ] a risky architectural choice has two plausible paths with different consequences;
- [ ] credentials, permissions, or external services block verification;
- [ ] a 2-minute human answer would likely save a large fraction of remaining budget.

Escalation request must include:

- blocker summary;
- options considered;
- recommended option;
- exact question for the human;
- cost of continuing without input;
- what evidence has already been collected.

Escalation does not reset the run. After input, continue from the current evidence state.

## Readiness Assertion And Honesty Gate

Before marking a Demo or Benchmark run `done`, the agent must write an evidence-backed readiness claim in `verdict.md`.

Required claim:

```text
Review readiness: <review-ready|partial-reviewable|not-reviewable>
Reason: <specific evidence-based reason>
Supporting artifacts: <paths>
Weakest remaining area: <specific area or none>
```

Readiness checklist:

- [ ] Readiness claim is present in `verdict.md`.
- [ ] Claim references concrete artifacts or verification results.
- [ ] Claim does not rely on agent feelings, shame, pride, or generic confidence.
- [ ] If the agent has meaningful uncertainty, status is `partial`, not `done`.
- [ ] If there is any embarrassing artifact or behavior, it is named specifically in residual risks.

Evidence honesty questions:

- [ ] If a random developer saw the artifacts, would they understand what was built?
- [ ] Is the run stopping because the feature is ready, not because the agent is tired or out of ideas?
- [ ] Is there anything in the result the agent would be embarrassed to show?

If the answer exposes weakness:

- [ ] Name the weakness specifically.
- [ ] Mark the run `partial` unless the weakness is minor.
- [ ] Do not hide the weakness behind generic phrasing like "could be polished".

## Parallel Benchmark Rubric

Use this when running multiple models against the same mission.

Keep constant:

- [ ] Mission.
- [ ] Scope.
- [ ] Repo baseline.
- [ ] Budget.
- [ ] Evidence schema.
- [ ] Demo sequence.
- [ ] Quality gates.

Vary only:

- [ ] Model.
- [ ] Execution engine.
- [ ] Prompt variant label if intentionally tested.

Score each category from 0 to 5:

- [ ] Functional completeness.
- [ ] Determinism.
- [ ] Evidence quality.
- [ ] Product or artifact quality.
- [ ] Scope discipline.
- [ ] Self-correction.

Comparison table:

```markdown
| Run | Model | Functional | Determinism | Evidence | Quality | Scope | Self-correction | Total | Verdict |
|-----|-------|------------|-------------|----------|---------|-------|-----------------|-------|---------|
| A | model-1 | 4 | 5 | 5 | 4 | 5 | 4 | 27 | review-ready |
```

Winner rule:

- [ ] Highest score wins only if no critical gate failed.
- [ ] If the highest score has weak evidence, choose the best reviewable run.
- [ ] If no run is reviewable, tighten the contract and rerun.

## Anti-Pattern Checklist

Before finalization, actively check that none of these patterns are present.

| Anti-pattern | Symptom | Detection |
|---|---|---|
| Hopeful E2E | E2E written before API/DB/route discovery | Phase 0 lacks probes/inspection |
| Dev-server faith | assumes served code is fresh | no production build or build identity |
| File-name story | screenshots named well but content is same | diversity gate missing/failing |
| Silence is victory | no page error, so assumed OK | no DOM/state verification |
| Thin evidence | one-line timeline or empty decisions | evidence schema fails |
| One more retry | retries without classification | failure taxonomy missing |
| Premature leadership-ready | summary claims quality without artifact proof | readiness assertion/honesty gate fails |
| Copy-paste bugfix | fixed one occurrence, missed siblings | post-fix source search missing |
| Declared premium | one polish pass and done | minimum polish pass missing |
| Broken self-contained demo | demo artifact references missing files | self-contained demo gate fails |
| MVP camouflage | technically works but looks like an admin/task list | product experience contract fails |
| Screenshot blindness | screenshots exist but were never visually reviewed | visual review notes missing |
| Not-my-page defect | visible demo path bug left because it is pre-existing | demo path ownership rule fails |
| API escape hatch | UI action falls back to direct API call | hard assertion rule fails |
| Log-only assertion | missing condition is printed but does not fail E2E | machine-readable report contradicts script behavior |
| Gate archive theater | gate DB/checklist created after implementation | no initial gate ledger or timestamps |
| ATM bypass | Feature/Demo/Benchmark run proceeds without ATM/gate runner | no run record, no imported gates, manual verdict |
| Verdict forgery | summary/verdict claims stricter status than ATM computed status allows | ATM verdict mismatch |

Checklist:

- [ ] Hopeful E2E is not present.
- [ ] Dev-server faith is not present.
- [ ] File-name story is not present.
- [ ] Silence is victory is not present.
- [ ] Thin evidence is not present.
- [ ] One more retry is not present.
- [ ] Premature leadership-ready is not present.
- [ ] Copy-paste bugfix is not present.
- [ ] Declared premium is not present.
- [ ] Broken self-contained demo is not present.
- [ ] MVP camouflage is not present.
- [ ] Screenshot blindness is not present.
- [ ] Not-my-page defect is not present.
- [ ] API escape hatch is not present.
- [ ] Log-only assertion is not present.
- [ ] Gate archive theater is not present.
- [ ] ATM bypass is not present.
- [ ] Verdict forgery is not present.

## Launch Template

Use this block as the mission file for a new run.

### Minimal Agent Launch Instruction

Use this short instruction when launching any agent/model:

```text
Read the feature contract and the Autonomous Delivery Gold Standard.

You must run this work through ATM or an equivalent gate runner.

Before code:
1. Create an ATM run.
2. Import relevant gates from the Gold Standard and feature contract.
3. Export initial gate state.

During work:
1. Use ATM gates as the task controller.
2. Attach evidence to gates as soon as it exists.
3. Run build/typecheck/E2E through ATM command evidence where possible.
4. Do not batch-pass gates at the end.

Final:
1. Run ATM verify.
2. Generate verdict through ATM.
3. Export gate ledger and evidence package.
4. If ATM verdict is partial/failed, do not claim demo_done in prose.

Manual demo_done is invalid.
If ATM is unavailable or unused, maximum status is partial.
```

```markdown
# Autonomous Run Mission

## Mission

Deliver <feature-name> as a demo-ready product increment with deterministic verification and a complete evidence package.

## Repository

- Repo path:
- Main app/package:
- Branch:
- Evidence output path:

## Mandatory ATM Runtime

Before writing code, execute the ATM/gate-runner bootstrap or equivalent:

```text
atm init-run --id <run-id> --mode <mode> --contract <feature-contract> --standard <gold-standard>
atm import-gates --run <run-id>
atm verify --run <run-id> --phase bootstrap
atm export --run <run-id> --out <evidence-output-path>
```

Rules:

- Do not start implementation until the run and gates exist in ATM.
- Do not manually write final verdict.
- Final verdict must come from `atm verdict --run <run-id>` or equivalent.
- If ATM is unavailable or not used, maximum verdict is `partial`.
- If ATM verdict and prose summary disagree, the stricter status wins.

## Product Story

<Actor> can <start action>, progress through <main lifecycle>, and see <final result>.

## In Scope

- <item>
- <item>
- deterministic demo runner
- evidence package
- state hooks for demo-critical pages

## Out Of Scope

- unrelated refactors
- speculative features
- risky infrastructure changes
- production integrations unless required

## Budget

- Time budget:
- Major iterations:
- Verification retries:
- Polish after functional pass: yes/no

## Required State Hooks

- data-page:
- data-ready:
- data-state:
- data-testid:

## Demo Sequence

1. <state>
2. <state>
3. <state>
4. <final state>

## Required Artifacts

1. 01-<state>.png
2. 02-<state>.png
3. 03-<state>.png
4. 04-<final>.png

## Verification Commands

- Static/typecheck:
- Build:
- Tests:
- E2E/demo:

## Pre-E2E Discovery Requirements

- API endpoints to probe:
- DB tables/collections to inspect:
- Frontend routes to verify:
- State hooks required:
- Realtime/polling sources to inspect:
- Stale source/build artifact risks:
- Side-effect chains to trace:
- Copy-paste bug patterns to search after fixes:
- Discovery timebox:
- First valid artifact iteration limit:

## Final Output

Produce:

- summary.md
- verdict.md
- gate-ledger.initial.json
- gate-ledger.json
- gate-ledger-summary.md
- DEMO_NARRATIVE.md
- tasks.json
- artifacts.json
- timeline.md
- decisions.md
- changed-files.md
- screenshots/
- logs/
- self-contained demo artifact if stakeholder-facing
```

## Final Quality Gate

Before finalizing, every run must answer the checks relevant to its operating mode. Mark irrelevant checks as `not_applicable` with a short reason instead of forcing unnecessary artifacts.

- [ ] Was the operating mode declared and followed?
- [ ] Was ATM or an equivalent gate runner used as the execution runtime?
- [ ] Does ATM contain a run record created before implementation?
- [ ] Were gates imported into ATM before implementation?
- [ ] Was the final verdict produced by ATM or equivalent computed gate logic?
- [ ] Does the prose summary match ATM computed status?
- [ ] Was the gate ledger created before implementation started?
- [ ] Does `gate-ledger.initial.json` or equivalent prove initial gate bootstrap happened before code?
- [ ] Does `gate-ledger.json` or equivalent contain final gate states?
- [ ] Does `gate-ledger-summary.md` or equivalent list failed, waived, pending, and blocking gates?
- [ ] Does the final verdict match the gate ledger computed status?
- [ ] Is the evidence proportional to the chosen mode and risk?
- [ ] Did the agent complete the readiness claim with artifact references where required?
- [ ] Did the agent answer the evidence honesty questions?
- [ ] Were up to 3 meaningful polish passes completed for demo-critical UI/artifacts where applicable, or stopped early because the quality bar/budget was reached?
- [ ] Was a copy-paste source search run after bugfixes?
- [ ] Was screenshot/artifact diversity checked?
- [ ] Was content density checked for key screenshots/artifacts?
- [ ] Does `DEMO_NARRATIVE.md` or equivalent explain the story when stakeholder-facing?
- [ ] Does a self-contained demo artifact exist when stakeholder-facing?
- [ ] Was real-time evidence captured for meaningful failures, retries, and decisions?
- [ ] Was discovery completed inside the timebox or stopped/replanned?
- [ ] Was time to first valid artifact tracked?
- [ ] Were anti-patterns checked and absent?
- [ ] Was the result classified as `technical_done`, `demo_done`, `partial`, or `failed`?
- [ ] For user-facing work, did a feature-specific experience contract exist or get created before implementation?
- [ ] For stakeholder-facing work, did the agent visually review screenshots/artifacts before declaring done?
- [ ] Were visible trust breakers on the demo path fixed or explicitly downgraded to `partial`?
- [ ] Did E2E fail hard on missing required selectors, states, pages, and side-effect proofs?
- [ ] Were API fallbacks forbidden for demo-critical UI actions?
- [ ] Did API schema discovery happen before E2E was trusted?
- [ ] Did DB/fixture discovery happen where persisted state matters?
- [ ] Were frontend routes verified from source?
- [ ] Were stale source/build artifacts checked?
- [ ] Was E2E run against production build/preview where practical?
- [ ] Was build artifact identity recorded where stale-code risk exists?
- [ ] Were side-effect chains traced where durable writes happen?
- [ ] Were realtime/polling sources considered where they affect UI state?
- [ ] Were failures classified before retries?
- [ ] Did the main story work end-to-end?
- [ ] Did deterministic verification pass?
- [ ] Were artifacts captured after readiness checks?
- [ ] Are screenshots or demo outputs reviewable?
- [ ] Is the evidence package complete?
- [ ] Are timeline and decisions detailed enough to reconstruct the run?
- [ ] Is the final verdict honest?
- [ ] Is the result `review-ready`, `partial-reviewable`, or `not-reviewable`?
- [ ] Are residual risks named?
- [ ] Could another reviewer understand the result without reading chat history?

Final rule:

```text
If any critical item fails, do not mark the run done.
Mark it partial or failed, explain why, and preserve the evidence.
```

## Database Gate Model

If this standard is moved into a database or state machine, each checkbox should become a gate record.

The database/state machine is not an archive. It is the run controller. Creating it after the feature is complete does not satisfy the Gold Standard.

### Gate Ledger Operating Procedure

Before every substantial action, the agent should know which gate it is trying to satisfy.

Loop:

```text
1. Select the next pending critical or major gate for the current phase.
2. Do the smallest useful work that can satisfy or clarify that gate.
3. Attach evidence refs immediately.
4. Mark the gate passed, failed, waived, or not_applicable.
5. If failed, classify the failure and decide: fix, replan, partial, or failed.
6. Continue with the next gate.
```

The agent must not batch-update all gates at the end from memory.

Required gate ledger exports:

- [ ] `gate-ledger.initial.json`: state after Phase -1 bootstrap.
- [ ] `gate-ledger.final.json` or `gate-ledger.json`: final gate states.
- [ ] `gate-ledger-summary.md`: human-readable summary of failed, waived, pending, and critical gates.

Minimum summary:

```markdown
# Gate Ledger Summary

## Status Counts
- critical passed:
- critical failed:
- critical pending:
- critical waived:
- major passed:
- major failed:
- major pending:

## Blocking Gates
- gate_id:
- severity:
- status:
- evidence:
- decision:

## Verdict Computation
- computed_status:
- human_claimed_status:
- mismatch:
```

Verdict consistency rule:

- [ ] `summary.md`, `verdict.md/json`, and gate ledger computed status must agree.
- [ ] If they disagree, the stricter status wins.
- [ ] A prose claim of `demo_done` cannot override the gate ledger.

### Recommended Gate Seed Set

Every Demo/Benchmark run should seed at least these gates before implementation:

- `input.mode.declared`
- `input.feature_contract.read`
- `workflow.discovery.plan_before_code`
- `workflow.discovery.api_probed`
- `workflow.discovery.db_schema_verified`
- `workflow.discovery.routes_verified`
- `workflow.discovery.stale_artifacts_checked`
- `workflow.implementation.copy_paste_search_after_fixes`
- `workflow.verification.build_passes`
- `workflow.verification.typecheck_passes`
- `demo_path.ownership.visible_trust_breakers_fixed`
- `demo_path.ownership.all_visible_pages_owned`
- `e2e.hard_assertions.no_soft_logs`
- `e2e.hard_assertions.no_api_fallback_for_ui`
- `e2e.hard_assertions.console_errors_fail`
- `e2e.hard_assertions.page_errors_fail`
- `quality.visual.screenshots_opened`
- `quality.visual.mobile_reviewed`
- `quality.visual.not_admin_table`
- `quality.visual.story_clear_without_chat`
- `evidence.package.required_files_present`
- `evidence.package.screenshot_paths_valid`
- `final.verdict.computed_from_gates`

Recommended gate fields:

```json
{
  "gate_id": "pre_e2e.api_schema.probe_endpoints",
  "category": "pre_e2e",
  "title": "Every endpoint used by the demo was probed before E2E implementation",
  "severity": "critical",
  "status": "pending",
  "evidence_required": true,
  "evidence_refs": [],
  "failure_class": null,
  "owner": "agent",
  "checked_at": null,
  "notes": null
}
```

Recommended categories:

- `input`
- `workflow`
- `pre_e2e`
- `demo_state`
- `e2e_stability`
- `quality`
- `evidence`
- `stop`
- `benchmark`
- `final`

Recommended severities:

- `critical`: failure blocks `done`;
- `major`: failure allows only `partial`;
- `minor`: failure can be documented as residual risk.

Status values:

- `pending`
- `passed`
- `failed`
- `not_applicable`
- `waived`

Waiver rule:

- [ ] Every `waived` gate has a reason.
- [ ] Every `waived` critical gate forces `partial` unless explicitly approved by a human.
- [ ] Every failed critical gate blocks `done`.
- [ ] Every failed major gate must be listed in `verdict.md`.
- [ ] Every gate with `evidence_required=true` must reference a file, command output, selector assertion, or artifact.

Suggested gate ID prefixes:

```text
input.*
workflow.discover.*
workflow.plan.*
workflow.implement.*
workflow.verify.*
workflow.review.*
workflow.package.*
pre_e2e.api_schema.*
pre_e2e.db_schema.*
pre_e2e.routes.*
pre_e2e.stale_artifacts.*
pre_e2e.production_build.*
pre_e2e.side_effects.*
pre_e2e.realtime.*
demo_state.*
e2e.failure_taxonomy.*
e2e.screenshot.*
quality.visual.*
evidence.summary.*
evidence.verdict.*
evidence.timeline.*
evidence.decisions.*
stop.*
benchmark.*
final.*
```

Minimum aggregate run status logic:

```text
if any critical gate failed:
  status = failed or partial
elif any critical gate waived without human approval:
  status = partial
elif any major gate failed:
  status = partial
elif all critical and major gates passed or are not_applicable:
  status = done
else:
  status = partial
```
