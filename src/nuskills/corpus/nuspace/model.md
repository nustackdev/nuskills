---
title: The space model
summary: What a nuspace is made of, where each thing lives, and how a cell's program is loaded and bound.
---

# The space model

A space is a durable store of planes and cells, plus a kernel that runs them. People, services and programs all change it the same way: by running Nu terms against the store.

- **Cell**: one program. Its source (`prog`) is Python that builds a Nu term. A cell sits on exactly one plane. Its id is unique across the space, so a cell is addressed by its id alone.
- **Plane**: a named, ordered group of cells. It is the thing that runs: running a plane makes a plane run, with one cell run per cell. Planes nest: each has a `parent` (`""` at the top level) and an ordered `children` list.
- **State**: what programs remember, typed, declared as `CellState` or `PlaneState` Shapes. Persistent across runs and restarts.

## Two stores, each tagged by its root class

The space keeps two kv stores, each bound under its root Shape class as the tag:

```text
Space                          what the space is
  planes      id -> Plane      name, props, meta, cells [ids, in order], children, parent, version
  cells       id -> Cell       name, prog, version, props, meta, plane
  top         [plane id]       top level planes, in order
  pinned      [plane id]       sidebar pins, in order
  kernel                       runs, live runs, workers: written by the kernel
  connections, state           written by the web device and the host

States                         what the programs remember, by the same ids
  planes      id -> {state}    PlaneState shapes land in planes[p].state
  cells       id -> {...}      CellState shapes land in cells[c]
```

Both roots are importable: `nuspace.Space`, `nuspace.States` (and the row Shapes from `nuspace.shapes`). A kv Ref finds its store by its root class object, so **import the roots, never redeclare them**. A `class Space(nu.Shape)` of your own is a different class, and every read of it raises `LookupError: No binding for: Navigator[Space]`.

Plane props are typed and set when the plane is made: `system` (protected, `remove_plane` refuses it), `ui` (the shell draws it), `made_by` (the registered Plane it came from), `backend` (`"async"` or `"mp"`, required, no default). `meta` is free, merged into any time; ui planes keep `editable`, `full_width` and `icon` there. Cell props: `made_by` (the snippet it came from) and `has_ui` (worked out from the prog whenever it is written, never by hand).

Output and errors belong to runs, never to cells. Plane and cell are definitions; what ran and how it ended is under `Space.kernel`.

## A cell's program

A prog is a Python module. Its entry point is `out`: a function returning a Nu term, or a module level term itself. `out` takes only what it names, from `plane` and `cell`, the running plane's and cell's ids as plain `str`.

```python run
import nu


def out(plane, cell):
    return nu.Str(cell + " on " + plane)
```

What the kernel does with it, every cell run:

1. Reads the prog from the store, in a snapshot of its own. A run always runs the source as it is now; a live run keeps the source it loaded until it is rerun.
2. Executes the module and calls `out`. Module level Python runs here, on every load, and also in the host whenever the prog is written (to work out `has_ui`). Keep module code to imports, Shapes and term building: no side effects, nothing slow.
3. Reroots the term's state chains (below), then runs it inside a frame over `nuspace.ops.Here`, which holds `plane`, `cell`, `run` and `cell_run`. Code that is not handed `plane` and `cell` (a helper module, a snippet's code) reads `ops.Here.plane` and `ops.Here.cell` at evaluation.

```python run
import nu
from nuspace import ops


def out():
    return nu.Dict.of(plane=ops.Here.plane, cell=ops.Here.cell)
```

The host binds both stores before your program runs. **Do not bind anything**: no `nu.With`, no `nu.Provide`, no `nustd.kv.auto_flow_atomic` around the stores. Nothing brackets your program for you either; every store access needs its own bracket (see nuspace/brackets). Other fabrics a cell brings (an http endpoint, its own kv db) it binds itself, as any Nu program does.

## State lands where the cell runs

A program names its state as if it were alone. At load, every chain rooted at a `CellState` subclass is spliced under `States.cells[cell]`, and every chain rooted at a `PlaneState` subclass under `States.planes[plane].state`. Chains rooted anywhere else (`nuspace.Space`, ui Refs, another db) are left alone.

```python run
import nustd.kv
import nuspace
from nuspace import ops


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


class Board(nuspace.PlaneState):
    hits = nustd.kv.IntRef.slot()


def out():
    return ops.atomic_state(
        Tick.n.set(Tick.n.fallback(0) + 1) >> Board.hits.set(Board.hits.fallback(0) + 1)
    )
```

- `CellState` is the cell's own: only its program writes it, every run of the cell shares it, a restart picks up where the last run stopped.
- `PlaneState` is where a plane's cells meet: the address is the slot name, not the class. Any cell on the plane declaring a `PlaneState` with a slot `hits` reads and writes the same key, whatever its class is called. Declare the same class in each cell that shares it, and pick slot names that will not collide with an unrelated cell's.
- A plain `nu.Shape` holding kv Refs lands nowhere: there is no store bound for it, and it raises `LookupError`. A `nu.Shape` of `nu.mem` Refs (`nu.IntRef`, ...) used with `nu.Frame` or `nu.let` is scratch for one evaluation, not state.

To reach state that is not the running cell's, wrap the term:

- `ops.sibling(cell_id, term)`: another cell on the same plane, eg `ops.sibling(other, Tick.n)`.
- `ops.cell_state(cell_id, term)`: any cell's state, from anywhere.
- `ops.plane_state(plane_id, term)`: any plane's shared state, from outside that plane.

All three are bare, like any store access, and route to `States`: bracket them with `ops.snapshot` to read and `ops.atomic_state` to write.

```python run
import nu
import nustd.kv
import nuspace
from nuspace import ops


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


def out(plane):
    # Read another cell's Tick.n by id: the first cell on this plane.
    first = nu.Str(ops.cells(plane).iter().first())
    return ops.snapshot(ops.cell_state(first, Tick.n.fallback(0)))
```

## Runs

A plane run executes on the plane's `backend`: `async` runs every cell as a task in one worker (good for many awaiting cells), `mp` gives each cell its own process (good for sync or CPU work). A plane can have several live runs at once (eg one per open tab), so the same cell may run twice against the same state: make writes idempotent or guard them with a check read in the same commit. A cell that subscribes or loops runs for as long as its plane run lives; a cell that finishes simply ends its cell run. Interrupt is cooperative and per cell; kill is per plane run.

Drawing a cell (its ui Refs, the shell, the browser) is its own piece: nuspace/drawing.
