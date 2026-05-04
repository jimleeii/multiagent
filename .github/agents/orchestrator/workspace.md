# Workspace Policies

## Governing Reference Files

At session start and before any rules-enforcement or wiki-scaffold action, read these files using `read/readFile` to load current content into context. Do not rely on inline summaries.

The `rules/` path is `<workspace_root>/.github/agents/rules/`.

The `templates/` path is `<workspace_root>/.github/agents/templates/`.

Path resolution note: references to "Orchestrator root" mean `<workspace_root>/.github/agents/`.

### Rules (Always Load at Session Start)

| File | Purpose |
|---|---|
| `rules/Code-Commenting-And-Regions.md` | C# commenting and `#region` standards; enforced by Senior Developer and audited by Code Reviewer |
| `rules/Orchestrator-Markdown-Alignment.md` | Markdown writing profile and alignment checklist |
| `rules/Rules.md` | Authoritative markdownlint rule definitions |

### Templates (Load During Workspace Initialization)

| File | Wiki Target |
|---|---|
| `templates/Home.md` | `.wiki/orchestrator/Home.md` |
| `templates/Project-Context-Log.md` | `.wiki/orchestrator/Project-Context-Log.md` |
| `templates/Behavior-Log.md` | `.wiki/orchestrator/Behavior-Log.md` |
| `templates/Skill-Usage-Log.md` | `.wiki/orchestrator/Skill-Usage-Log.md` |
| `templates/Behavior-Patterns.md` | `.wiki/orchestrator/Behavior-Patterns.md` |
| `templates/Learning-Backlog.md` | `.wiki/orchestrator/Learning-Backlog.md` |
| `templates/Runbook.md` | `.wiki/orchestrator/Runbook.md` |
| `templates/state.json` | `.wiki/orchestrator/state.json` |
| `templates/AGENTS.md` | `AGENTS.md` (workspace root) |

Read each template file verbatim before copying it to a missing target.

## Workspace Initialization

Run initialization at first orchestration cycle of a session, on `workspace init`, and before first write to wiki artifacts.

### AGENTS.md

- Check whether `AGENTS.md` exists at workspace root.
- If missing, create it with `create-agentsmd` skill and `templates/AGENTS.md`.
- If present, update only stale sections (agents, rules, conventions, routing policy summary).
- Log create/update action in project context log.

### Required Folder and File Scaffold

Verify paths below exist and create missing ones from templates:

| Required Path | Template Source |
|---|---|
| `.wiki/orchestrator/Home.md` | `templates/Home.md` |
| `.wiki/orchestrator/Project-Context-Log.md` | `templates/Project-Context-Log.md` |
| `.wiki/orchestrator/Behavior-Log.md` | `templates/Behavior-Log.md` |
| `.wiki/orchestrator/Skill-Usage-Log.md` | `templates/Skill-Usage-Log.md` |
| `.wiki/orchestrator/Behavior-Patterns.md` | `templates/Behavior-Patterns.md` |
| `.wiki/orchestrator/Learning-Backlog.md` | `templates/Learning-Backlog.md` |
| `.wiki/orchestrator/Runbook.md` | `templates/Runbook.md` |
| `.wiki/orchestrator/state.json` | `templates/state.json` |

Rules:

- Create `.wiki/orchestrator/` first if missing.
- Copy template content verbatim for new files.
- Do not modify template source files.
- During scaffold checks, do not modify existing files except scaffold summary append to `.wiki/orchestrator/Project-Context-Log.md`.
- If a template source is missing, log blocker and notify user.

### Initialization Trigger Conditions

Run automatically:

- At first orchestration cycle in a session
- On `workspace init`
- Before any logging action targeting a wiki file not yet confirmed in session

Do not re-scaffold files that already exist.
