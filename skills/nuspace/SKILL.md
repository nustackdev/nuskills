---
name: nuspace
description: Program a running nuspace: write a cell's prog, read and change planes, cells and state through nuspace.ops, keep CellState and PlaneState, draw a cell with nustd.ui, insert snippets. Use when code imports nuspace or nuspace.ops, or the task is about a space, a plane, a cell or a snippet.
---

<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Programming a nuspace

Use this skill to write a cell's program (its prog) or any program that reads and changes a space through `nuspace.ops`. A cell's prog is a Nu program like any other, loaded and bound by the space, so the Nu ground below applies in full.

Before you write:

- Install: `pip install nuspace` (it pulls nucore and the fabrics a space runs on; `nuspace[all]` adds every other fabric). `nuspace run [PATH]` opens a space in the browser; a cell's prog is the source you put in a cell there.
- The API is whatever the installed version says. Render it with `nu.inspect` rather than guessing a name, eg `python -c "import nu; print(nu.inspect.render('nuspace.ops'))"` (module first, then the exact subject; the `nu/inspect` reference file has the rest). The catalogue is not copied into this skill, so it never goes stale.
- Check a prog builds before you store it: `nu.validate(nu.compile(out()))` raises on a term that is not a valid Nu program.
- The space binds its stores and runs the program for you. Never bind them yourself, and bracket every store access (both are below).

The sections after the Reference list are what every cell needs. Each reference file goes deeper on one topic; open the one the task needs (ops before changing structure, drawing before a cell draws or keeps a list of rows).

## Reference

Open a file when the task needs its topic. A piece id in the text (`nu/control`) names one of these or a section below.

| File | What it covers |
| --- | --- |
| [nu/inspect](reference/nu/inspect.md) | How to read the API of any Nu module, atom, fabric or app Shape with nu.inspect instead of guessing. |
| [nuspace/ops](reference/nuspace/ops.md) | The nuspace ops a program uses to read and change a space, and the rules they keep. |
| [nuspace/snippets](reference/nuspace/snippets.md) | Content goes in snippet cells, set and read through their ops: inserting one, reaching it from any plane, writing your own, and the helpers cells share. |
| [nuspace/drawing](reference/nuspace/drawing.md) | How a cell draws its block on a plane with nustd.ui, keeps it live from the store, acts on clicks, and keeps a keyed list with per-row actions. |
| [nu/thesis](reference/nu/thesis.md) | Refs, Interactions, Fabrics, Contexts, and the six kinds every Nu term belongs to. |
| [nu/composition](reference/nu/composition.md) | The slot rule that decides what nests where, sequencing, moving values between steps, and how to lay out an app. |
| [nu/pitfalls](reference/nu/pitfalls.md) | Where a Python reading of Nu goes wrong, and the anti-patterns first attempts keep landing on. |
| [nu/control](reference/nu/control.md) | Branches, loops, streams and reductions, and scratch state with nu.let and nu.Frame, all as atoms of the program. |
| [nu/reactive](reference/nu/reactive.md) | Running a body on change: event Flows for things that happened, level Flows for state kept in step or waited for. |
| [nu/errors](reference/nu/errors.md) | EMPTY and the writes that refuse it, validation errors and law names, unbound fabrics, and handling failures inside the program. |
| [nu/host](reference/nu/host.md) | @nu.host turns a plain Python function into a Nu atom: when it runs, what it receives, and the one-capture rule. |
| [nu/examples](reference/nu/examples.md) | Three complete small Nu programs, each with the lines that carry the weight explained. |
| [nustd/fabrics](reference/nustd/fabrics.md) | The map of fabrics, nu.mem in the kernel and the rest in nustd, and how a program picks and binds one. |
| [nustd/kv](reference/nustd/kv.md) | nustd.kv stores Shapes durably over memory, RocksDB, LMDB, SQLite or text; Refs, backends, brackets, reads as Queries, which change subscription fires on what, minting ids, conflict retries, sharding. |
| [nustd/service](reference/nustd/service.md) | nustd.service exposes a plain Python object's methods as Nu Refs, one Ref kind per effect. |
| [nustd/ui-refs](reference/nustd/ui-refs.md) | nustd.ui leaves: writing to a widget, reading it back, reacting to it, and the kit. |
| [nustd/ui-layout](reference/nustd/ui-layout.md) | nustd.ui containers: Column, Row, Grid, Line and the chrome boxes, as Shapes or as Refs alone, with keyed children. |
| [nustd/ui-app](reference/nustd/ui-app.md) | Serving a plain Nu program in the browser: Page, Index, nustd.ui.serve, one program per tab, and the keyed list over a store with per-row actions. |

## Writing Nu

A Nu program is a Python module that constructs a term. `import nu` gives the kernel: every atom, the Flows, the Spans and the `nu.mem` fabric (state in plain dicts), flat on `nu`. Other fabrics (`nustd.kv`, `nustd.ui`, `nustd.service`, `nustd.http`, ...) live in `nustd`. A module exposes its program as `out()` returning the term.

### Shapes

A Shape declares slots. Each slot is a Ref, an address in a fabric.

```python
import nu


class Movie(nu.Shape):
    title: nu.StrRef
    year: nu.IntRef


class Library(nu.Shape):
    name: nu.StrRef
    tags = nu.ListRef.slot(str)
    scores = nu.DictRef.slot(int)
    shelf = nu.DictRef.slot(Movie)
    featured = nu.ShapeRef.slot(Movie)


def out():
    return (
        Library.tags.init([])
        >> Library.tags.append("dune")
        >> Library.featured.year.set(1984)
        >> Library.scores["dune"].set(4)
        >> Library.shelf["dune"].title.set("Dune")
    )
```

Two slot forms, mixable in one class: the annotation (`title: nu.StrRef`) when the Ref class is the whole declaration, `.slot(...)` when the slot takes an argument (element type `str`, `int`, a Shape) or config. Never both on one slot.

**A Shape is never instantiated.** There is no `Library()`. Refs are class attributes used unbound, and every expression on them builds a term: `Library.tags.append("dune")` is a Command, `Library.featured.year` a nested Ref, `Library.scores["dune"]` a keyed Ref.

Verbs on every slot: `set init erase exists missing is_empty not_empty fallback`; `init(v)` writes only when the slot is missing. Per type: `inc dec` on `IntRef`; `append extend insert pop remove clear sort reverse len contains index first_elem last_elem slice iter` on `ListRef`; `keys values items get_item set_item del_item update setdefault pop len contains` on `DictRef`; `add discard remove union ...` on `SetRef`; the `str` methods (`upper split startswith ...`) on `StrRef`. Containers declare their element: `nu.DictRef.slot(Movie)`, then `Library.shelf["dune"].title` addresses inside one entry. A slot may not share a name with one of these verbs ([nu/pitfalls](reference/nu/pitfalls.md)).

### Forms first

Refs and computed values carry a typed **Form** (`Int`, `Str`, `Bool`, `List`, `Iterator`, ...) whose Python operators and methods build the atoms. Write the form; the atom is what it compiles to.

| Write | Compiles to |
| --- | --- |
| `a + b`, `a * 2`, `"id-" + nu.str(n)` | `nu.Add`, `nu.Mul`, ... |
| `a == b`, `a != ""`, `a > 3`, `a <= b` | `nu.Eq`, `nu.Ne`, `nu.Gt`, `nu.Le` |
| `a.and_(b)`, `a.or_(b)`, `a.not_()` | `nu.And`, `nu.Or`, `nu.Not` |
| `a >> b`, `a \| b`, `a & b` | `nu.Sequential`, `nu.Parallel`, `nu.Race` |
| `x.len()`, `x.contains(k)`, `d[k]`, `d.get_item(k, default)` | `nu.Len`, `nu.Contains`, `nu.GetItem`, `nu.Get` |
| `x.fallback(0)`, `x.is_empty()`, `x.not_empty()` | `nu.Fallback`, `nu.IsEmpty`, `nu.NotEmpty` |
| `xs.iter().filter(f).map(g).to_list()`, `.first()` | `nu.Collect(nu.Map(nu.Filter(nu.Iter(xs), f), g))`, `nu.First` |
| `s.strip()`, `s.split(",")`, `s.upper()`, `nu.Str(", ").join(xs)` | the `str` atoms |

- Boolean logic is a method, never a keyword: `and`, `or`, `not` raise on a term.
- A plain Python value becomes a literal wherever a child is expected (`Library.tags.append("dune")`, `n + 1`, `x == ""`); never wrap an operand in `nu.Int(0)` or `nu.Str("")`. A bare literal standing alone has no operators; give it a Form: `nu.Int(5) > 3`, `nu.Dict(PRICES)[item]`.
- `nu.Str(x)`, `nu.Int(x)`, `nu.List(x)` only type `x`; they do not convert. `nu.str(x)`, `nu.int(x)`, `nu.list(x)` convert and keep the Form. `nu.ToStr`, `nu.ToInt` convert to a bare atom with no operators.
- Build a dict with `nu.Dict.of(title=Movie.title, year=Movie.year)`, a list with `nu.List.of(a, b)`.
- No form yet: the stream reductions `nu.Count`, `nu.Sum`, `nu.Min`, `nu.Max`, `nu.Last`, `nu.AnyOf`, `nu.AllOf` and `nu.SortBy` take the stream as an argument (`nu.Sum(xs.iter())`); branching is `nu.If` / `nu.IfDo`. A host call or a service stream has no Form either: type it (`nu.Str(slug_of(t)).fallback("")`) or reduce it.

### Binding a fabric

A Ref resolves only through a fabric provided around it. From outside the program:

```python fragment
state = {}
ctx = nu.Context().bind(dict, state)  # nu.mem for every Shape
ctx = nu.Context().bind(dict, {}, Library).bind(dict, {}, Movie)  # one dict per Shape
```

`Context.bind` returns a new Context. Inside the program:

```python fragment
nu.Provide(dict, {}, body)  # one fabric around one body; the mapping seeds the new dict
nu.Provide(dict, {}, body, tag=Library)  # scoped to one Shape
nu.With(nu.Provide(dict, {}, tag=Library), nustd.kv.memory_navigator(), body=body)
```

`nu.With(*brackets, body=...)` is Python's `with A, B, C:`: brackets open in order, each sees what the earlier ones bound, teardown runs in reverse. Fabric helpers return such brackets (`nustd.kv.memory_navigator()`, `nustd.service.bind(Svc, target=obj)`); stack them in one `With` head with `body=` last.

`nu.mem` addresses by slot name, so two Shapes with a same-named slot share one key under an untagged `bind(dict, state)`. Bind one dict per Shape (the tag) when that matters.

### Running

`nu.run(term, ctx=None)` compiles, validates and evaluates, and returns `(value, ctx)`. `await nu.arun(term, ctx)` is the async sibling.

```python fragment
value, ctx = nu.run(term, ctx)
value, ctx = await nu.arun(term, ctx)
```

- A program that only writes yields `None`. The result is the changed state: read the dict you bound, or run a read program afterwards.
- A program holding an async-only atom (`ParallelAsync`, `ForEachParAsync`, `Timeout`, the reactive Flows, `nustd.ui`, anything a fabric marks async-only) needs `arun`; `nu.run` refuses it with `RuntimeError: eval: program contains an async-only atom (Timeout); use aeval.`
- Everything else runs under either.

A whole app is one program with one `nu.With(...)` binding every fabric at the bottom ([nu/composition](reference/nu/composition.md)). A host that loads the module (a script, a test, a space) calls `out()` and runs the term.

```python run
import nu


class Tally(nu.Shape):
    seen = nu.ListRef.slot(str)
    count = nu.IntRef.slot()


record = Tally.seen.append("x") >> Tally.count.set(Tally.seen.len())


def out():
    return nu.Provide(dict, {"seen": []}, record >> record)
```

In tests, hold the state yourself and assert on it after the run: `state = {}`, `nu.run(record, nu.Context().bind(dict, state))`.

## The space model

A space is a durable store of planes and cells, plus a kernel that runs them. People, services and programs all change it the same way: by running Nu terms against the store.

- **Cell**: one program. Its source (`prog`) is Python that builds a Nu term. A cell sits on exactly one plane. Its id is unique across the space, so a cell is addressed by its id alone.
- **Plane**: a named, ordered group of cells. It is the thing that runs: running a plane makes a plane run, with one cell run per cell. Planes nest: each has a `parent` (`""` at the top level) and an ordered `children` list.
- **State**: what programs remember, typed, declared as `CellState` or `PlaneState` Shapes. Persistent across runs and restarts.

### Two stores, each tagged by its root class

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

### A cell's program

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

The host binds both stores before your program runs. **Do not bind anything**: no `nu.With`, no `nu.Provide`, no `nustd.kv.auto_flow_atomic` around the stores. Nothing brackets your program for you either; every store access needs its own bracket (see [nuspace/brackets](#brackets)). Other fabrics a cell brings (an http endpoint, its own kv db) it binds itself, as any Nu program does.

### State lands where the cell runs

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

### Runs

A plane run executes on the plane's `backend`: `async` runs every cell as a task in one worker (good for many awaiting cells), `mp` gives each cell its own process (good for sync or CPU work). A plane can have several live runs at once (eg one per open tab), so the same cell may run twice against the same state: make writes idempotent or guard them with a check read in the same commit. A cell that subscribes or loops runs for as long as its plane run lives; a cell that finishes simply ends its cell run. Interrupt is cooperative and per cell; kill is per plane run.

Drawing a cell (its ui Refs, the shell, the browser) is its own piece: [nuspace/drawing](reference/nuspace/drawing.md).

## Brackets

Nothing brackets a program for you and nothing autocommits. A read or a write of either store (`Space` or `States`) with no bracket around it fails at run time:

```text
LookupError: No binding for: SnapshotProtocol[States](site=('cells', '<cell>', 'n'), ...)
```

`SnapshotProtocol[States]` means a state Ref was read or written with no bracket open on `States`; `SnapshotProtocol[Space]` the same for structure. The program builds and validates fine; only running it fails.

### Which bracket

| You are | Wrap it in | Opens |
| --- | --- | --- |
| reading, anything | `ops.snapshot(term)` | a snapshot of `States` and of `Space`, each only if read |
| writing your state (`CellState`, `PlaneState`, `ops.sibling`, `ops.cell_state`, `ops.plane_state`) | `ops.atomic_state(term)` | one commit on `States`, Space readable, retried on conflict |
| writing `Space` by hand | `ops.atomic(term)` | one commit on `Space`, States readable, retried on conflict |
| calling an op | nothing | each op brackets itself |
| not sure, whole cell | `ops.bracketed(term)` | one bracket per step, placed for you |

A write in the wrong bracket fails too: `StorageInterfaceError: ... doesn't implement write access protocol`. That is a state write inside `ops.snapshot` or `ops.atomic`, or a Space write inside `ops.atomic_state`. Writing Space by hand is almost never right: the ops are the writers of structure ([nuspace/ops](reference/nuspace/ops.md)).

A read:

```python run
import nu
import nustd.kv
import nuspace
from nuspace import ops


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


def out(plane):
    return ops.snapshot(nu.Dict.of(n=Tick.n.fallback(0), cells=ops.cells(plane)))
```

A write. The check that decides a write goes inside the same bracket, so nothing lands between them:

```python run
import nu
import nustd.kv
import nuspace
from nuspace import ops


class Seed(nuspace.CellState):
    seeded = nustd.kv.BoolRef.slot()
    rows = nustd.kv.ListRef.slot(str)


def out():
    return ops.atomic_state(
        nu.IfDo(Seed.seeded.missing(), Seed.rows.set(["a", "b"]) >> Seed.seeded.set(True))
    )
```

`ops.snapshot`, `ops.atomic_state` and `ops.atomic` are `nustd.kv.Snapshot` and `nustd.kv.Transaction` with `scope=nuspace.Space` or `scope=nuspace.States`, plus `RetryOnConflict` on the writes. Spelling them out raw works, eg `nustd.kv.Transaction(Jobs.selected.set(job), scope=nuspace.States)`; the ops helpers are shorter and pick the right pairing.

### Read, then write

A read is a Query and `>>` chains only effects, so a read and a write side by side in one chain does not validate (`strategy cannot hold scalar_query`), whichever comes first. Read first in its own snapshot, hold the value in `nu.let`, then write in a short commit:

```python run
import nu
import nustd.kv
import nuspace
from nuspace import ops


class Seen(nuspace.CellState):
    planes = nustd.kv.IntRef.slot()


def out():
    rows = ops.snapshot(ops.plane_rows())
    return nu.let(rows, lambda got: ops.atomic_state(Seen.planes.set(got.len())))
```

When the read decides whether to write at all (a check and its write), keep both in one `ops.atomic_state` instead, as in the seed above: a value carried out of one bracket into another can be stale by the time it is written.

### What leaves a bracket

A store read yields a live view tied to its bracket: `.keys()`, `.values()`, `.items()` and a container read fail with `StorageClosedError` once it closes. Anything handed on (a `ForEachParReactive`'s items, a value in `nu.let`, a host function's argument) is made plain inside the bracket: `ops.snapshot(nu.list(Notes.texts.keys()))`. Shape values in such a list stay live; project them inside it with `nu.Dict.of(...)` or `nu.dict(value)`. A container never written reads empty, so it needs no `.fallback(...)`, which on a container drops its methods ([nustd/kv](reference/nustd/kv.md)).

### Keep each bracket short

Never hold a bracket across:

- a loop or a wait (`ForeverDo`, `WhileDo`, `Delay`, `WaitReactive`, a subscription's body);
- another op (it opens its own bracket, and two write brackets on one store never join: on SQLite the inner one is the same thread waiting on its own lock);
- a loaded program (`nu.prog.Eval`), an llm or http call, anything slow.

Put the bracket inside the loop, one per step:

```python
import nu
import nustd.kv
import nuspace
from nuspace import ops


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


def out():
    step = ops.atomic_state(Tick.n.set(Tick.n.fallback(0) + 1))
    return nu.ForeverDo(nu.DelayedDo(1.0, step))
```

Not `ops.atomic_state(nu.ForeverDo(...))`: that holds one commit open for as long as the cell runs, and nothing else ever sees a tick.

A subscription to the store is a read too. Wrap the change in a snapshot; the reaction brackets its own work:

```python
import nu
import nustd.kv
import nuspace
from nuspace import ops


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()
    seen = nustd.kv.IntRef.slot()


def out():
    copy = ops.atomic_state(Tick.seen.set(Tick.n.fallback(0)))
    return nu.ReactForever(ops.snapshot(Tick.n.on_change()), copy)
```

Ops stay outside every bracket. Chain them with `>>` next to your own bracketed steps:

```python run
import nustd.kv
import nuspace
from nuspace import ops


class Seen(nuspace.CellState):
    renamed = nustd.kv.BoolRef.slot()


def out(plane):
    return ops.rename_plane(plane, "Notes") >> ops.atomic_state(Seen.renamed.set(True))
```

When the order matters across stores, structure goes first and state second, each its own commit (that is what `remove_cell` does): a crash in between then leaves state nothing points at, never a live cell whose state is gone.

### `ops.bracketed`: brackets placed for you

Wrap a cell's whole `out()` in `ops.bracketed(...)` and write the rest bare. It lands your state chains under the running cell, then gives each step of every Flow (each arm of `>>`, each loop iteration, each reaction) a snapshot if it reads or a transaction if it writes, per store. Brackets already there, the ops' own included, are kept and never doubled.

```python run
import nustd.kv
import nuspace
from nuspace import ops


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


def out(plane):
    return ops.bracketed(
        Tick.n.set(Tick.n.fallback(0) + 5) >> ops.rename_plane(plane, "Notes") >> Tick.n.set(Tick.n + 1)
    )
```

Its limit: a wrapper that is not a Flow (`nu.let`, `nu.Frame`, `nu.TryCatch`, `nu.With`, `nu.Timeout`) and reads a store in its own arguments gets one bracket around all of it. If that wrapper holds a loop, a wait or an `Eval`, the bracket is held as long as they run. Bracket code shaped like that by hand. `ops.bracketed` works only inside a cell run, where `ops.Here` is held.
