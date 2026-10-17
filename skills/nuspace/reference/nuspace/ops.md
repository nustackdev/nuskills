<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Ops

`from nuspace import ops`. Every op is a function returning a Nu term; nothing happens until the term runs. They are the space's language: the shell, the services and every cell change the space only through them.

**Prefer an op to a hand-written Ref chain.** Several facts in the store are written in pairs: a plane's `cells` list and each cell's `plane`, a plane's `children` and each child's `parent`, `Space.top` and the top level planes' `parent == ""`, a plane's `version` on every write to its cells. The ops are the only writers that keep each pair agreeing. Write `Space.planes[p].cells` by hand and the sidebar, the kernel and search disagree about what is on the plane.

## What an op promises

- **A write op is one commit**, bracketed by itself and retried on conflict. Never wrap one in a bracket; chain ops with `>>`.
- **A write yields nothing** (`None`). Whatever it made is in the record: a plane made is listed under its parent, a plane moved has its new parent.
- **A missing target is a no-op**, not an error: renaming a cell that is gone writes nothing. Read the record afterwards when you need to know.
- **Ids are minted when the term runs**, so a term built once and run many times makes a new thing each time. Pass `plane_id=` / `cell_id=` to fix one. To learn a minted id, pass `into=`, a Ref the op sets in the same commit: hold one in `nu.let` and hand it on.
- **A read op is bare**: it composes into any expression and reads in whatever bracket encloses it. Alone, wrap it in `ops.snapshot(...)`.

```python run
import nu
from nuspace import ops

CELL = """
import nu


def out():
    return nu.Str("hello")
"""


def out(plane):
    return nu.let(
        "",
        lambda made: (
            ops.add_plane(backend="async", name="Notes", parent=plane, ui=True, into=made)
            >> ops.add_cell(nu.Str(made), CELL, name="hello")
            >> ops.set_plane_icon(nu.Str(made), "notebook")
            >> ops.pin_plane(nu.Str(made))
        ),
    )
```

`ops.mint_ordered_id("p")` is plain Python: it mints when the module runs, which is every load of the cell (and once more when its prog is written). Use it only for an id you want fixed for one run of the term; prefer `into=`. For a key of your own minted at each evaluation (one per click), wrap it in a host function. Its ids sort by the time they were minted, so a dict keyed by them lists in creation order:

```python fragment
@nu.host
def new_id():
    return ops.mint_ordered_id("n")


add = ops.atomic_state(Notes.texts[new_id()].set(nu.Str(View.add.text)))
```

`nu.str(nustd.uuid.uuid4())` also mints per evaluation, when the order does not matter.

## Read before you write

A first pass that only reads is cheap and tells you what is actually there. Each row read yields plain dicts:

```python run
import nu
from nuspace import ops


def out(plane):
    return ops.snapshot(
        nu.Dict.of(
            planes=ops.plane_rows(),
            cells=ops.cell_rows(plane),
            runs=ops.runs(plane),
        )
    )
```

- `plane_rows()`: every plane as `{id, name, props: {system, ui, made_by, backend}, meta, parent}`.
- `cell_rows(plane_id)`: a plane's cells in order as `{id, name, prog, props: {made_by, has_ui}, meta}`.
- `planes()`, `cells(plane_id)`, `children(plane_id="")` (top level for `""`), `pinned()`: id lists, in order.
- `plane_exists(id)`, `cell_exists(id)`: Bool. `plane_title(id)`: the name, or the id when unnamed. `parent(id)`, `cell_plane(cell_id)`, `prog(cell_id)`: `""` when missing.
- `cell_named(plane_id, name)`: the first cell with that name, `""` for none. Names are not unique; ids are.

A read program yields its value. A write program yields `None`. Reads and writes do not share one `>>` chain; read into `nu.let` first ([nuspace/brackets](../../SKILL.md#brackets)).

## Planes

| Op | Does |
| --- | --- |
| `add_plane(plane_id=None, *, backend, name="", parent="", system=False, ui=False, made_by="", meta=None, into=None)` | Make an empty plane under `parent` (`""`: top level; a missing parent falls back to top). `backend` is required: `"async"` or `"mp"`. Given an existing id, rewrites its props and moves it, keeping its cells. |
| `create_plane(spec, *, parent="", name=None, plane_id=None, into=None)` | Make a plane from a registered `nuspace.Plane` spec, its seeded cells and child planes, in one commit. |
| `remove_plane(plane_id)` | Drop a plane, its cells and every plane below it, killing their live runs and unpinning them, then their state. Refused if any of them is `system`. |
| `rename_plane(plane_id, name)` | Set its name. |
| `set_plane_meta(plane_id, fields)` | Shallow merge into `meta`. Props are not reachable here. |
| `set_plane_icon(plane_id, icon)` | `"lucide:<name>"`, `"emoji:<char>"`, a bare lucide name, or `""` for the default. |
| `move_plane(plane_id, *, parent="", index=None)` | Reparent and reorder in one. Refused if it would make a cycle. |
| `pin_plane(plane_id, index=None)`, `unpin_plane(plane_id)`, `move_pin(plane_id, index)` | Sidebar pins. Only `ui` planes pin. |

## Cells

| Op | Does |
| --- | --- |
| `add_cell(plane_id, prog, *, cell_id=None, name="", index=None, made_by="", meta=None, into=None)` | Write a cell onto a plane at `index` (the end when None). `into` gets the id, `""` when nothing was written. |
| `insert_snippet(plane_id, snippet, *, index=None, cell_id=None, into=None)` | `add_cell` from a `nuspace.Snippet`: its source, its short name as name, its `pkg.name` as `made_by` ([nuspace/snippets](../../reference/nuspace/snippets.md)). |
| `set_prog(cell_id, prog)` | Replace the source. Live runs keep the old one until rerun. A broken prog stores fine. |
| `rename_cell(cell_id, name)`, `set_cell_meta(cell_id, fields)` | Name, merge into `meta`. |
| `reorder_cells(plane_id, cell_ids)` | Put the named cells first in that order; the rest keep their place after them. |
| `remove_cell(cell_id)` | Interrupt its live runs, take it off its plane, delete it, then its state. |
| `clear_cell_state(cell_id)`, `clear_plane_state(plane_id)` | Wipe state. A person's reset, not part of a restart. |

A cell never moves between planes: to move one, add it on the new plane and remove the old.

No CLI command adds a cell. While the space runs, a person adds one in the browser, or any cell's program does with `ops.add_cell`. A space directory has one owner at a time; with it not running, a script opens it and runs ops as the body, ending when the body does: `asyncio.run(nu.arun(nuspace.open_space(path, web=False, body=ops.add_cell(plane, SOURCE))))`.

```python run
import nu
from nuspace import ops

CELL = """
import nu


def out():
    return nu.Str("draft")
"""


def out(plane):
    return (
        ops.add_cell(plane, CELL, cell_id="c_draft", name="draft", index=0)
        >> ops.rename_cell("c_draft", "outline")
        >> ops.set_cell_meta("c_draft", {"status": "wip"})
        >> ops.reorder_cells(plane, ["c_draft"])
    )
```

## Runs

Kernel ops write intents only: the kernel, in the host, sees them and makes them true. So they are safe from any cell, and all but `plane_stop` return at once.

| Op | Does |
| --- | --- |
| `plane_run(plane_id, *, by="", envs=(), into=None)` | Start a plane run, one cell run per cell. `into` gets the run id. |
| `plane_interrupt(run_id)` | Ask every live cell run to stop (cooperative). |
| `plane_kill(run_id)` | Tear the run down; its cells end `killed`. |
| `plane_stop(run_id, grace=10.0)` | Interrupt, then kill if still running after `grace` seconds. Returns once the run ends or the kill is asked. |
| `cell_run(run_id, cell_id, *, by="")` | Run one cell again inside a live plane run. |
| `cell_interrupt(run_id, cell_run_id)` | Ask one cell run to stop. |
| `runs(plane=None)`, `run(run_id)`, `cell_runs(run_id, *, live=False)`, `latest(run_id, cell_id)`, `workers()` | Bare reads of the live runs, one run whole, its cell runs (`exit`, `error`, `out`), a cell's newest cell run id. |

```python
import nu
from nuspace import ops


def out(plane):
    return nu.let("", lambda run: ops.plane_run(plane, by="me", into=run))
```

## State

`ops.sibling`, `ops.cell_state`, `ops.plane_state` reach state that is not the running cell's; `ops.Here` holds the running ids. Both are in [nuspace/model](../../SKILL.md#the-space-model), and their brackets in [nuspace/brackets](../../SKILL.md#brackets).
