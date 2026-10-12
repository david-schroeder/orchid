# CLAUDE.md — ORChiD (Open Rapid Chip Designer)

ORChiD is a **template repository / framework** for mixed-signal (AMS) chip design. It glues
open-source tools (LibreLane, ORDeC, KLayout, NGSpice, Magic, Netgen, ...) into one
[PyDesignFlow](https://pydesignflow.readthedocs.io) flow with a single global entrypoint.
Digital and analog macros are hardened by reusable flow blocks and combined by an
analog (ORDeC) toplevel into a full chip.

Long-form project documentation lives in `llm/` — **read it before non-trivial work**:

| File | Content |
|------|---------|
| `llm/01_project_goal.md` | Goal, principles, intended directory layout |
| `llm/02_flow_architecture.md` | Target flow blocks, tasks, dependencies |
| `llm/03_roadmap.md` | Ordered plan toward the target architecture |
| `llm/04_conventions_and_notes.md` | Tooling, environment, conventions, open questions |

## The docs describe the target, not the present

`llm/` (and this file) deliberately describe **where the project is going**, never a
snapshot of what exists, so they cannot go stale. Consequently:

- **Before acting, review the current state yourself**: `ls`/read `flow/`, `src/`,
  `flow/__init__.py` (block registration and wiring), `git status`/`git log` (read-only),
  and the installed tool sources if relevant. Do not assume a planned block/task exists.
- Do not write current-state descriptions, "known issues" lists, or "present/done" markers
  into docs. Document intent, interfaces and conventions only.
- When a roadmap item is completed, remove it from `03_roadmap.md` rather than marking it done.

## Git policy

The user owns the repository history and upstream. You may use git freely for working
locally — including `stash`, checking out older commits or other branches, worktrees, diffs,
bisecting — **as long as** the upstream repository and the commit history stay clean:

- Never commit, amend, rebase, merge, cherry-pick, tag, force anything, or push, and never
  create/alter remote branches or PRs, unless the user explicitly asks.
- Don't leave the working tree on another branch/commit, stashes, or worktrees behind
  unannounced: **tell the user at the end of the prompt** about any git operation you
  performed that changed local state (branch checkouts, stashes, etc.), and restore the
  original state where possible.
- Don't discard the user's uncommitted work.

## Hard rules

1. **`src/` is a template.** Only very simple example content may live there. No real design
   data, large IP, or project-specific content. Keep examples minimal and generic.
2. **Don't edit generated/untracked state**: `build/`, `.venv/`, `.Xil/`, `setup_flow`
   (user-local, gitignored), vivado logs/journals.
3. **Keep the flow generic.** Design names, coordinates, PDK paths belong in example/config
   data, not in reusable block logic. New flow blocks must be parametrizable and
   instantiable multiple times.
4. **Don't invent facts about tools.** Check the installed source in
   `.venv/lib/python*/site-packages/`, the sibling clone `../ordec`, or the docs
   (pydesignflow.readthedocs.io, ordec.readthedocs.io, librelane.readthedocs.io).

## Repository structure (conventions)

- `flow/` — the flow (framework code): PyDesignFlow `Block` subclasses, registered in
  `flow/__init__.py`; `flow/tools/` for thin external-tool wrappers; `flow/pdk/` for
  PDK-specific data/plugins.
- `src/` — example design data only (see rule 1).
- `docs/` — Sphinx/ReadTheDocs docs; `llm/` — documentation for LLM agents.
- `shortcut.py` — CLI entrypoint (`python shortcut.py <block>.<task>`).
- `build/` — flow output, one directory per block/task (gitignored).

## Working with the flow

- Run from the repo root with the venv active: `python shortcut.py <block>.<task>`; use
  `--help` to discover tasks.
- Environment: `PDK_ROOT` and `ORDEC_PDK_IHP_SG13G2` point to the PDK's `ihp-sg13g2`
  directory; proprietary/heavy tools (Vivado, QuestaSim) must be on `PATH` only for tasks
  that use them. Don't run heavy or licensed tasks speculatively; prefer static reading and
  lightweight checks (`python -m py_compile`, importing the flow).
- Tasks are `@task` methods; dependencies via `requires={'arg': 'block.task'}`, wired with
  `dependency_map` in `flow/__init__.py`. Results go in a `Result()`, files into `cwd`.
  `hidden=True` hides a task from the default listing.
- Prefer plain JSON/files over pickles for data passed between tasks.
- Environment lookups (tool paths, env vars) belong inside tasks, not at import time.

## Code guidelines

- Python, 4-space indent, type hints where cheap, one-line docstrings on tasks (they are
  the CLI descriptions).
- **REUSE/SPDX**: every new file gets `SPDX-License-Identifier` + `SPDX-FileCopyrightText`
  headers (flow code: Apache-2.0; example RTL: SHL-2.1; see `REUSE.toml`); files that can't
  carry headers go into `REUSE.toml`. Copyright holder for new files: `David Schröder 2026`.
- Match surrounding style; don't reformat unrelated code; small reviewable changes.
- Tool wrappers in `flow/tools/`, PDK data in `flow/pdk/`, block logic in `flow/<block>.py`.
- Prefer ORDeC (ORD, otherwise Python views) for analog macros, schematics, layouts and
  analog testbenches.
- No hardcoded absolute paths/user names; use `self.flow.base_dir`, env variables or task
  parameters.
- Note new Python dependencies in `requirements.txt` and tell the user.
