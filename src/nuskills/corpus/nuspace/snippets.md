---
title: Snippets
summary: Content goes in snippet cells, set and read through their ops: inserting one, reaching it from any plane, writing your own, and the helpers cells share.
---

# Snippets

A snippet is a cell a person inserts from the `/` menu: text, a table, an input. Its prog is a few lines that import the snippet's code, and what it holds lives in the cell's own state. Search finds it there, a person edits it in place, and the snippet's ops read and write it from any program on any plane.

**Content goes in snippets, behaviour in a program.** Text, a heading, notes, a value a person sets: insert the snippet and set what it holds with its ops. Write a cell program of your own only for real behaviour: a live view, something interactive, a computation. Content baked into a program's source is content nobody can search or edit.

## Insert one, then set what it holds

`ops.insert_snippet(plane, <pkg>.SNIPPET, into=cell)` adds the cell at the end of `plane` (or at `index=`) and sets `cell`, a Ref you hold in `nu.let`, to the new id (`""` when the plane is missing). Each snippet op takes the cell id first. Each write op is a commit of its own, so a program made of them needs no bracket:

```python run
import nu
from nuspace import ops
from nuverse.snippets import prose


def out(plane):
    return nu.let(
        "",
        lambda cell: (
            ops.insert_snippet(plane, prose.SNIPPET, into=cell)
            >> prose.set_text(cell, "## Garden\n\n- Water the basil")
        ),
    )
```

A read op is bare: wrap it in `ops.snapshot(...)`. A snippet cell is named after its snippet unless renamed, so `ops.cell_named(plane, "text")` finds the first text cell. Names are not unique; keep the id from `into` to come back to the cell.

```python run
import nu
from nuspace import ops
from nuverse.snippets import prose


def out(plane):
    cell = ops.cell_named(plane, "text")
    return ops.snapshot(nu.If(cell == "", "", prose.text_of(cell)))
```

## The standard set

nuverse ships the standard snippets, one package each under `nuverse.snippets`: the package exposes `SNIPPET` and its ops. The convention:

- `prose` is the text snippet, `nuverse.text` (`nuspace.TEXT`), whose cells document editing works on: `set_text(cell, markdown)`, `text_of(cell)`.
- Input snippets keep one value: `set_value(cell, value)`, `value_of(cell)` (`text_input`, `number`, `slider`, `switch`, `select`, `date`).
- Some have no ops: a person works them in place (`table`), or they show something (`lens`, `cell_lens`, `ticker`).

The space's registry decides which snippets exist and what ops each has; where it disagrees with this list, the registry wins.

```python run
import nu
from nuspace import ops
from nuverse.snippets import number, text_input


def out(plane):
    return nu.let(
        "",
        lambda budget: nu.let(
            "",
            lambda owner: (
                ops.insert_snippet(plane, number.SNIPPET, into=budget)
                >> ops.rename_cell(nu.Str(budget), "budget")
                >> number.set_value(budget, 420.0)
                >> ops.insert_snippet(plane, text_input.SNIPPET, into=owner)
                >> ops.rename_cell(nu.Str(owner), "owner")
                >> text_input.set_value(owner, "Ana")
            ),
        ),
    )
```

## Ops of your own over a cell's state

A snippet's ops are nothing special: they wrap the cell's `CellState` in `ops.cell_state(cell_id, ...)` and bracket it. Follow the same shape for state your own cells keep, so other programs reach it by id without knowing your classes:

```python fragment
import nu
import nustd.kv
import nuspace
from nuspace import ops


class Doc(nuspace.CellState):
    text = nustd.kv.StrRef.slot()


def set_text(cell_id: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """One commit on States; a no-op when the cell is gone."""
    kept = ops.cell_state(cell_id, Doc.text.set(text))
    return ops.atomic_state(nu.IfDo(ops.cell_exists(cell_id), kept))


def text_of(cell_id: nu.StrArg) -> nu.Nu:
    """Bare: the caller wraps it in ops.snapshot."""
    return ops.cell_state(cell_id, Doc.text.fallback(""))
```

## Writing a snippet

A snippet is data, `nuspace.Snippet(name, label, source, *, search=None, description="", ops=(), group="", icon="")`, registered through an `Extension` that a package names under the `nuspace.extensions` entry point group (or a host passes to `nuspace.open_space`). Keep the code in a module and store only a shim as the source, so a fix to the code reaches every cell already made from it:

```python fragment
# mypkg/notes/shim.py: the source every inserted cell stores.
from mypkg.notes import snippet

out = snippet.out()
```

```python fragment
# mypkg/notes/ext.py
from importlib import resources

from nuspace import Snippet

from .ops import set_text, text_of

SNIPPET = Snippet(
    "notes",
    "Notes",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="Notes kept in the cell's state.",
    ops=(set_text, text_of),
    group="Content",
    icon="notebook",
)
```

`search`, when given, is a module level function `search(query, cell)` returning a term that yields `[{"excerpt": ...}]` or `[]`. A whole plane is registered the same way, as a `nuspace.Plane(name, label, *, backend, cells=((name, source), ...), children=(...), meta=..., icon=...)`, made with `ops.create_plane(spec)`.

## Shared helpers for cells

`nuspace.system.utils` holds the loops nuverse's own cells are built from. They are plain functions, not ops. Each brackets its own reads and never holds a bracket across a wait.

- `follows(ref, body)`: run `body(value)` with the str at a store `ref`, and restart it with the new value whenever the ref changes. The way one cell follows a selection another cell writes into `PlaneState`.
- `redraws(changes, read, draw)`: run `draw(view)` with what `read` reads now, on every change of any of `changes` and on a re-check every 30 seconds, and only when the view differs from the last one drawn.
- `snap(term)`: `term` read in a snapshot of both stores (`ops.snapshot` does the same).
- `park()`: sit until cancelled, `nu.ForeverDo(nu.Delay(3600.0))`. What a cell that only draws ends with.

```python
import nu
import nustd.kv
import nuspace
from nuspace import ops
from nuspace.system.utils import follows


class Pick(nuspace.PlaneState):
    selected = nustd.kv.StrRef.slot()


class Shown(nuspace.CellState):
    title = nustd.kv.StrRef.slot()


def showing(plane_id):
    return ops.atomic_state(Shown.title.set(ops.plane_title(plane_id)))


def out():
    return follows(Pick.selected, showing)
```

```python
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace.system.utils import redraws


class Counter(nuspace.CellState):
    value = nustd.kv.IntRef.slot()


tile = nustd.ui.StatRef("count")


def out():
    show = redraws([Counter.value.on_change()], Counter.value.fallback(0), lambda n: tile.set_value(nu.str(n)))
    return tile.set_label("Count") >> show
```

Drawing the cell itself (the kit, containers, live views, forms) is nuspace/drawing.
