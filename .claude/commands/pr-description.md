Generate a structured pull request description for this project by reading the diff and understanding the changes.

## Your task

Produce a complete, accurate PR description in Markdown. Follow the steps below exactly.

---

## Step 1 — Gather the diff

The user may have provided a base branch or context as arguments: $ARGUMENTS

Run the following to understand what has changed. Handle each command gracefully if it errors (e.g. no git repo, no upstream).

```bash
# Identify current branch and likely base
git -C /config/workspace/python/toodoo branch --show-current 2>&1
git -C /config/workspace/python/toodoo log --oneline main..HEAD 2>&1 || \
git -C /config/workspace/python/toodoo log --oneline master..HEAD 2>&1 || \
git -C /config/workspace/python/toodoo log --oneline -20 2>&1

# Full diff against base (try main, then master, then staged+unstaged)
git -C /config/workspace/python/toodoo diff main..HEAD 2>&1 || \
git -C /config/workspace/python/toodoo diff master..HEAD 2>&1 || \
git -C /config/workspace/python/toodoo diff HEAD 2>&1 || \
git -C /config/workspace/python/toodoo diff 2>&1

# Stat summary (files changed, insertions, deletions)
git -C /config/workspace/python/toodoo diff --stat main..HEAD 2>&1 || \
git -C /config/workspace/python/toodoo diff --stat 2>&1
```

If git is unavailable or the repo has no commits, read the primary source files directly to understand the current state of the project:
- /config/workspace/python/toodoo/web.py
- /config/workspace/python/toodoo/db.py
- /config/workspace/python/toodoo/mcp_server.py
- /config/workspace/python/toodoo/requirements.txt

---

## Step 2 — Read context files for anything the diff alone doesn't explain

Only read what you need. Common candidates:
- `docs/knowledge-graph.md` — system overview and behavioural rules
- `docs/api.md` — route reference (useful if routes changed)
- `docs/data-model.md` — schema (useful if columns or tables changed)
- `tests/` — verify what is tested

---

## Step 3 — Classify every changed file

Group each changed file into one or more of these categories:
- **feature** — new capability visible to users or API consumers
- **fix** — corrects incorrect behaviour
- **refactor** — internal restructure, no behaviour change
- **test** — additions or updates to the test suite
- **docs** — documentation only
- **config** — pyproject.toml, requirements.txt, settings, .env.example
- **chore** — tooling, hooks, CI, non-functional maintenance

---

## Step 4 — Write the PR description

Output ONLY the Markdown block below, filled in accurately. Do not add any prose before or after it. Do not invent changes that aren't in the diff.

```markdown
## Summary

<!-- One paragraph. What does this PR do and why? Write for a reviewer who hasn't been following along. -->

## Changes

### ✨ Features
<!-- Bullet list. Omit section if empty. -->

### 🐛 Fixes
<!-- Bullet list. Omit section if empty. -->

### ♻️ Refactoring
<!-- Bullet list. Omit section if empty. -->

### 🧪 Tests
<!-- Bullet list of what was added or changed in the test suite. Omit if empty. -->

### 📚 Documentation
<!-- Bullet list. Omit if empty. -->

### ⚙️ Configuration & Tooling
<!-- pyproject.toml, requirements.txt, hooks, .env.example, etc. Omit if empty. -->

## Files Changed

<!-- Auto-generated from diff --stat. Table: File | Change type | Notes -->
| File | Type | Notes |
|------|------|-------|

## Testing Notes

<!-- How should a reviewer verify this works? Include:
- Manual steps to exercise the change
- Which automated tests cover it (test file + test name)
- Any setup required (env vars, seed data, etc.) -->

## Breaking Changes

<!-- List any breaking changes to the API, data model, MCP tools, or env vars.
Write "None." if there are none. Never omit this section. -->

## Migration Notes

<!-- Steps an operator must take when deploying: schema changes, new required env vars,
config file changes. Write "None." if there are none. Never omit this section. -->

## Checklist

- [ ] All tests pass (`pytest tests/ -q`)
- [ ] Ruff lint + format clean (`ruff check . && ruff format --check .`)
- [ ] No secrets or credentials in diff
- [ ] `.env.example` updated if new env vars were added
- [ ] `docs/` updated to reflect changes
- [ ] `mcp_server.py` in sync with `web.py` / `db.py`
- [ ] Breaking changes documented above
```

---

## Rules

- Every bullet point must be grounded in the actual diff. No speculation.
- Omit empty sections (except **Breaking Changes** and **Migration Notes** — always include those with "None." if clean).
- The **Files Changed** table must list every file that appears in `diff --stat`, not a subset.
- If the diff is empty or git is unavailable, say so clearly in the Summary and describe the current project state instead.
- Write for a reviewer, not for yourself. Assume they know the tech stack but not the specific change.
