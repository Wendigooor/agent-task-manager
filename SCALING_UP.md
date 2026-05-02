# How to Scale This for a Real Company

## Current State — Single-Project MVP

The framework does: one DB, one project, CLI scripts, AI calls them by reading README.

## What's Missing for a Giant Codebase

### 1. Multi-project / Multi-service Awareness

`plans.db` doesn't know about project structure. Need:

```sql
CREATE TABLE services (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,          -- "auth-service", "billing-monolith", "user-api"
    repo_path TEXT,              -- github.com/company/auth-service
    language TEXT,               -- "ruby", "go", "typescript"
    owner_team TEXT,
    active BOOLEAN DEFAULT 1
);

ALTER TABLE work_items ADD COLUMN service_id INTEGER REFERENCES services(id);
```

Now the agent knows: "this task is in the Go billing service, here's the repo path."

### 2. Code Analysis Before Planning

Currently the agent blindly grabs a task. Need a "Code Discovery" step:

```
workflow: idea → discover → plan → review → execute → verify → done

discover = scan relevant files, find connections, dependencies,
           gather context (not the whole project, just relevant files)
plan     = based on context, build a plan: files to change, approach, AC
review   = show plan to human (via MCP), wait for approval
```

Implementation: new `discovery_agent.py` script that:
1. Takes a task description
2. Searches relevant files in the repo (via grep/ast)
3. Gathers brief context (function signatures, imports, connections)
4. Stores in `work_item_context` table

### 3. Plan Review (Acceptance Criteria)

Currently tasks are created without AC. Need:

```sql
ALTER TABLE work_items ADD COLUMN acceptance_criteria TEXT;  -- JSON array
ALTER TABLE work_items ADD COLUMN review_status TEXT DEFAULT 'pending';
-- pending → approved → rejected
```

Pipeline:
1. AI creates task draft with status `review`
2. Via MCP sends plan to human: "Here's what I want to do, OK?"
3. Human: OK → status `todo`, or edits → AI revises

### 4. MCP Integration (Instead of CLI)

Currently: `python3 read_agent.py next` in terminal.  
Need: MCP server providing the same functions as typed tools.

```
MCP Server (FastMCP/Python):
  tools:
    - get_next_task() → { id, title, description, files, context }
    - claim_task(task_id) → { ok, claim_token }
    - submit_plan(task_id, plan) → { review_url }
    - complete_task(task_id, summary) → { ok }
    - get_project_status() → { phases, milestones, progress }

  resources:
    - plans://phases → JSON with all phases
    - plans://tasks/active → active tasks
    - plans://tasks/{id} → task details + context
```

Now any AI client (Claude Desktop, Cursor, VS Code) can pull tasks via MCP without knowing CLI.

### 5. Dependency Graph (DAG)

Currently tasks are independent. In reality, B depends on A.

```sql
CREATE TABLE work_item_deps (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER REFERENCES work_items(id),
    child_id INTEGER REFERENCES work_items(id),
    dep_type TEXT DEFAULT 'blocks'  -- 'blocks' | 'related' | 'duplicate'
);
```

`read_agent.py next` must account for: don't return a task if its dependencies aren't done.

### 6. Context Budgets (Per Service)

Each service has its own context limit:

```sql
ALTER TABLE services ADD COLUMN context_budget_tokens INTEGER DEFAULT 8000;
ALTER TABLE services ADD COLUMN key_files TEXT;  -- JSON array: ["app/models/user.rb", "config/routes.rb"]
```

Before a task, the agent gets: short README (300 tokens) + service key_files + context from discovery.

### 7. Idea Inbox (No Orphaned Ideas)

Currently ideas get lost. Need an inbox table:

```sql
CREATE TABLE inbox (
    id INTEGER PRIMARY KEY,
    source TEXT,           -- "slack", "jira", "manual", "mcp"
    raw_text TEXT,         -- original task text
    status TEXT DEFAULT 'new',  -- new | triaged | converted | rejected
    converted_to INTEGER REFERENCES work_items(id),
    created_at TEXT
);
```

Pipeline:
1. Idea lands in inbox (via MCP, Slack, Jira webhook)
2. Agent periodically processes inbox: analyzes, classifies, creates task drafts
3. Human manually or auto-approves
4. Not converted within a week → rejected with comment

### 8. What NOT to Overcomplicate

- **No** full Kanban UI — SQLite Viewer + CLI + MCP is enough
- **No** real-time collaboration — agents work sequentially (WAL gives basic concurrency)
- **No** Jira migration — can run in parallel, migrate gradually
- **No** Kubernetes/cloud — SQLite works locally or on a shared drive

## Minimal V2 Implementation

```
agent-task-manager-v2/
├── README.md              # Constitution (shared across all services)
├── .gitignore
├── plans.db               # SQLite database
├── services.json          # Service list and configs
├── src/
│   ├── memory.py          # DB connection + services config loader
│   ├── taskboard.py       # ORM: tasks, milestones, AC, deps, inbox
│   ├── read_agent.py      # Read-only
│   ├── workitem_agent.py  # CRUD
│   ├── status_agent.py    # State machine
│   ├── milestone_agent.py # Milestones
│   ├── db_log.py          # Readable DB dump
│   ├── discovery_agent.py # NEW: code analysis before planning
│   ├── inbox_agent.py     # NEW: parsing incoming ideas
│   └── mcp_server.py      # NEW: MCP server (FastMCP)
```

## Summary: What to Simplify, What to Add

**Simplify:**
1. No Web UI — CLI + MCP is enough. SQLite Viewer for browsing.
2. No real-time sync — WAL mode gives basic concurrency.
3. No direct Jira API integration — inbox table is simpler.
4. No complex DAG — only direct block relationships (A blocks B).
5. No full repo analysis — discovery only scans service key_files.

**Add:**
1. MCP server — AI gets tasks via typed tools, not CLI
2. Inbox — ideas don't get lost
3. Services config — agent understands codebase structure
4. AC + review step — human control before execution
5. Context budgets per service — don't overload the model
