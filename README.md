# nuskills

Prompt text about Nu and nuspace, in one place, tested against the current code.

- **nuagent** loads pieces into its system prompt.
- **Outside agents** (Claude Code, Codex) get skills built from the same pieces.
- Every fenced Python block in the corpus is built against the latest nucore, nustd and nuspace, so a piece cannot go stale without a red test.

## Layout

```
src/nuskills/
  __init__.py      loader: pieces(), load(), read(), __version__
  corpus/
    nu/            the kernel: thesis, crashcourse, composition, ...
    nustd/         fabrics: kv, mem, ui, ...
    nuspace/       the space model, ops, snippets, drawing a cell
  skills.py        which pieces each built skill carries, in order
  headers/         per skill SKILL.md frontmatter and a few lines of when-to-use
  build.py         assembles skills/ from headers + pieces
skills/            built skills, committed, never edited by hand
.claude-plugin/    plugin.json + marketplace.json: the repo is a Claude Code plugin
tests/             the block harness, the loader tests, the skills checks
```

## Using it from Python

```python fragment
import nuskills

nuskills.pieces("nu")              # ["nu/crashcourse", ...]
nuskills.read("nu/crashcourse")    # markdown, frontmatter stripped
nuskills.load("nu/crashcourse")    # Piece(id, title, summary, body)
```

Each consumer picks its pieces and decides their order. nuagent pins `nuskills` and assembles its system prompt from them, adding its own agent-specific text (role, protocol, finish) and the generated parts (the `nu.inspect` catalogue, the app surface). The pieces are package data, so `importlib.resources.files("nuskills") / "corpus" / "nu" / "crashcourse.md"` reaches the raw file too; the loader is the supported way.

## Skills

A skill is a header plus an ordered list of pieces, defined in `src/nuskills/skills.py`:

| Skill | For |
| --- | --- |
| `nu` | building Nu programs and apps (kernel + nustd fabrics, kv, service, ui) |
| `nuspace` | programming a running nuspace (cell progs, ops, brackets, state, drawing, snippets) |

Each one is built in Claude Code's progressive disclosure layout. `SKILL.md` holds the header, a table of the reference files with each piece's summary, and the pieces every task needs (`inline`). The rest (`reference`) are files next to it, read only when the task needs one, so they cost no context until then. A piece's mention of another piece (`nustd/ui-refs`) becomes a link to wherever it landed.

```
skills/<name>/
  SKILL.md
  reference/<group>/<piece>.md
```

The skills carry no catalogue. They tell the agent to render the API with `nu.inspect` in its own environment, so a skill is right for whatever version is installed.

Rebuild after editing a piece, a header or `skills.py`, and commit the result. `tests/test_skills.py` fails while `skills/` is out of date.

```bash
uv run python -m nuskills.build            # write skills/
uv run python -m nuskills.build --check    # exit 1 if skills/ is out of date
```

### Installing in Claude Code

The repo is a plugin marketplace (`nustack`) holding one plugin (`nuskills`):

```bash
claude plugin marketplace add nustackdev/nuskills
claude plugin install nuskills@nustack
```

Inside a session, `/plugin marketplace add nustackdev/nuskills` then `/plugin install nuskills@nustack` do the same. The skills show up as `/nuskills:nu` and `/nuskills:nuspace`, and Claude also loads them on its own when a task matches their description. To try a local checkout without installing: `claude --plugin-dir path/to/nuskills`. Validate after editing the manifests: `claude plugin validate .`.

## Writing a piece

A piece is one markdown file, `corpus/<group>/<name>.md`, its id is `<group>/<name>`. Keep it small enough to be picked on its own. Store only text that can't be generated: the catalogue (`nu.inspect`) and an app's surface are built at prompt time, never written here.

Optional frontmatter, `title` and `summary` only:

```text
---
title: Crash course
summary: The ten things you write in every Nu program.
---
```

### Fences

The info string on the opening fence says what the harness does with the block.

| Fence | Meaning | Checked by |
| --- | --- | --- |
| ```` ```python ```` | a whole program | loaded, `out` called, `nu.validate(nu.compile(term))` |
| ```` ```python run ```` | a whole program that finishes quickly in memory | the above, then evaluated with `nu.arun` (10s cap) |
| ```` ```python fragment ```` | a few lines, not a program | Python `compile()` only |
| anything else (`text`, `bash`, ...) | prose | skipped |

Any other word after `python` fails the test, so a typo can't turn a program into prose.

A whole program is a module with an entry point `out`, loaded by `nu.prog`'s own loader (the one nuspace uses for a cell):

- `out` is a function returning a Nu term, or a term itself.
- `out` takes only what its signature asks for, by name.
- In `nu/` and `nustd/` pieces nothing is offered: write `def out():`.
- In `nuspace/` pieces the block is a cell program. It is stored as a cell on a plane in an in-memory space and loaded the way the kernel loads it. `out` may ask for `plane` and `cell`, the ids as plain `str`. `CellState` and `PlaneState` slots land under that cell and plane. Store access needs its own bracket, as in a real cell (`ops.atomic_state(...)`, `ops.snapshot(...)`). A `run` block runs inside the cell's `ops.Here` frame against that space. There is no browser session, so a block that draws should not be marked `run`.
- A string literal in a block that contains `def out(` is another program's source (eg the cell an `ops.add_cell` adds) and is built the same way, under the same group's rules.

Mark `run` only on programs that finish and touch nothing outside memory. A program that subscribes, waits or serves stays unmarked: built and validated, not run.

## Checking a piece

```bash
uv sync                                  # once: Python 3.10 .venv with the sibling repos editable
uv run pytest -k nuspace/model           # every block in one piece
uv run pytest -k "nu/crashcourse:42"     # one block: piece and the fence's line
uv run pytest                            # everything
uv run ruff check
```

Each block is its own test, id `<piece>:<line>`, the line of its opening fence, so a failure points at the exact block. The dev env installs `../nu`, `../nu/pkgs/nustd[all]`, `../nuspace` and `../nuverse/pkgs/nuverse` editable, so it tests against main.

## CI

`.github/workflows/test.yml` runs ruff, the skills check and pytest against two stacks: **main** (nu, nuspace and nuverse checked out next to this repo, as `[tool.uv.sources]` expects) and **released** (the latest `nustd[all]`, `nuspace`, `nuverse` from PyPI). It runs on push and PR, nightly, by hand, and on a `repository_dispatch` (`nu-release`, `nuspace-release`, `nuverse-release`) a sibling release fires; the header of the workflow has the step a sibling adds.

## Versions

`nuskills` versions on its own, not in step with nu. CI tests the corpus against both current main and the latest released stack, so a version only says what changed in the text. `.claude-plugin/plugin.json` carries the same version as `pyproject.toml` (a test checks it), so installed plugins update when it moves.

Release: bump `version` in `pyproject.toml` and `.claude-plugin/plugin.json`, rename the CHANGELOG's `Unreleased` heading to the version + date, commit and push, then `git tag nuskills@X.Y.Z && git push origin nuskills@X.Y.Z`. `.github/workflows/publish.yml` publishes to PyPI (trusted publisher) and cuts a GitHub Release.

