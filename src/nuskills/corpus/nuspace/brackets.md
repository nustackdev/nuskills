---
title: Brackets
summary: Every store access in a cell needs a short bracket of its own; which one, where it goes, and what never to hold one across.
---

# Brackets

Nothing brackets a program for you and nothing autocommits. A read or a write of either store (`Space` or `States`) with no bracket around it fails at run time:

```text
LookupError: No binding for: SnapshotProtocol[States](site=('cells', '<cell>', 'n'), ...)
```

`SnapshotProtocol[States]` means a state Ref was read or written with no bracket open on `States`; `SnapshotProtocol[Space]` the same for structure. The program builds and validates fine; only running it fails.

## Which bracket

| You are | Wrap it in | Opens |
| --- | --- | --- |
| reading, anything | `ops.snapshot(term)` | a snapshot of `States` and of `Space`, each only if read |
| writing your state (`CellState`, `PlaneState`, `ops.sibling`, `ops.cell_state`, `ops.plane_state`) | `ops.atomic_state(term)` | one commit on `States`, Space readable, retried on conflict |
| writing `Space` by hand | `ops.atomic(term)` | one commit on `Space`, States readable, retried on conflict |
| calling an op | nothing | each op brackets itself |
| not sure, whole cell | `ops.bracketed(term)` | one bracket per step, placed for you |

A write in the wrong bracket fails too: `StorageInterfaceError: ... doesn't implement write access protocol`. That is a state write inside `ops.snapshot` or `ops.atomic`, or a Space write inside `ops.atomic_state`. Writing Space by hand is almost never right: the ops are the writers of structure (nuspace/ops).

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

## Read, then write

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

## What leaves a bracket

A store read yields a live view tied to its bracket: `.keys()`, `.values()`, `.items()` and a container read fail with `StorageClosedError` once it closes. Anything handed on (a `ForEachParReactive`'s items, a value in `nu.let`, a host function's argument) is made plain inside the bracket: `ops.snapshot(nu.list(Notes.texts.keys()))`. Shape values in such a list stay live; project them inside it with `nu.Dict.of(...)` or `nu.dict(value)`. A container never written reads empty, so it needs no `.fallback(...)`, which on a container drops its methods (nustd/kv).

## Keep each bracket short

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

## `ops.bracketed`: brackets placed for you

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
