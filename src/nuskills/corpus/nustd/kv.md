---
title: The kv fabric
summary: nustd.kv stores Shapes durably over memory, RocksDB, LMDB, SQLite or text; Refs, backends, brackets, reads as Queries, which change subscription fires on what, minting ids, conflict retries, sharding.
---

# The kv fabric

`nustd.kv` lays a Shape over transactional key-value storage. The program reads like a `nu.mem` one (same Shapes, same verbs), and the state survives the process, is shared between processes, and publishes changes reactive Flows follow. Two differences: slots use `nustd.kv` Refs, and every access sits inside a bracket.

```python run
import nu
import nustd


class Item(nu.Shape):
    name = nustd.kv.StrRef.slot()
    qty = nustd.kv.IntRef.slot()


class Shop(nu.Shape):
    stock = nustd.kv.DictRef.slot(Item)
    restocks = nustd.kv.IntRef.slot()
    low = nustd.kv.PrimitiveListRef.slot()


# Seed once: a store that already holds data keeps it.
seed = nustd.kv.Transaction(
    nu.IfDo(
        Shop.restocks.missing(),
        Shop.restocks.set(0)
        >> Shop.stock["apl"].set({"name": "apple", "qty": 3})
        >> Shop.stock["pea"].set({"name": "pear", "qty": 0})
        >> Shop.stock["fig"].set({"name": "fig", "qty": 12}),
    ),
    scope=Shop,
)

# A hot counter under concurrent writers: retry the whole transaction on conflict.
restock = nustd.kv.RetryOnConflict(
    nustd.kv.Transaction(
        Shop.stock["pea"].qty.set(Shop.stock["pea"].qty + 10) >> Shop.restocks.inc(),
        scope=Shop,
    )
)

# A read is a Query: stream the entries, filter, project each one into a plain dict row.
low_rows = nu.Collect(
    nu.Map(
        nu.Filter(nu.Iter(Shop.stock.items()), lambda entry: entry[1]["qty"] < 5),
        lambda entry: nu.Dict.of(id=entry[0], name=entry[1]["name"], qty=entry[1]["qty"]),
    )
)
report = nustd.kv.Transaction(Shop.low.set(low_rows), scope=Shop)


def out():
    return nu.With(nustd.kv.memory_navigator(), body=seed >> restock >> report)
```

After the run `Shop.low` holds `[{'id': 'apl', 'name': 'apple', 'qty': 3}]`.

## Refs

All under `nustd.kv`, declared in an ordinary `nu.Shape`. Render one with `nu.inspect` for its full method list.

| Ref | Holds |
| --- | --- |
| `IntRef` `FloatRef` `StrRef` `BoolRef` `BytesRef` `ObjectRef` | one value, read and written whole |
| `DictRef.slot(T)` | a mapping, one stored child per key; `T` a type, a kv leaf class, or a Shape |
| `ListRef.slot(T)`, `SetRef.slot(T)` | a list or set, one stored child per element |
| `ShapeRef.slot(S)` | one nested Shape, navigated with dots |
| `Kh57Ref.slot(T)` | a sparse map keyed by non-negative 57-bit ints, ordered, with range reads and sampling |
| `PrimitiveDictRef` `PrimitiveListRef` `PrimitiveSetRef` `PrimitiveFrozenSetRef` `PrimitiveTupleRef` | a whole collection as one blob |
| `ProgramRef` | stored Nu source |

- Addresses chain: `Shop.stock["pea"].qty` is one int inside one entry. A write vivifies every level above it; a key never written reads `EMPTY`. `Shop.stock.get_item(key, default)` reads with a fallback.
- A container never written reads empty: `.keys()` is `[]`, `.len()` is `0`. It needs no fallback, and `.fallback(...)` on a container yields a plain value without the container's methods (`Shop.stock.fallback({}).items()` is a `TypeError` at build). Leaves take `.fallback(0)` as usual.
- The key may be a term or a Ref, resolved at run time: `Shop.stock[Picked.id].qty` follows whatever `Picked.id` holds now.
- Decomposed containers (`DictRef`, `ListRef`, ...) give each element its own address, so one element can be written or watched alone. A primitive Ref is one opaque value: write it whole with `.set(...)` and do not rely on element verbs (`append`, `del_at`) reaching storage.
- `Kh57Ref`: `series.range(begin, end)` reads keys in `[begin, end)` in ascending order as `(key, value)` pairs, `series.sample(n, begin, end)` draws up to `n`. When the key encodes time, offset from a recent epoch and leave low bits for a counter so two writes in the same instant do not collide.
- A slot named like a Ref method (`items`, `keys`, `values`, `on_change`, ...) raises `TypeError` at class creation (nu/pitfalls). Rename it (`stock`, `items_`).

## Backends

A preset returns a `With` that stands up the whole stack (codec, transport, publisher, observer, storage, navigator). Put it in the head of the app's `nu.With`.

- `nustd.kv.memory_navigator()`: in process, gone at exit. Tests and examples.
- `nustd.kv.rocksdb_navigator(path)`: persistent, the default for real data. Also `lmdb_navigator`, `sqlite_navigator`, `text_navigator`.
- `*_redis` variants (`rocksdb_navigator_redis`, ...) carry change notifications across processes; the plain ones notify only in process.

## Brackets

Every kv read needs a `Snapshot` or a `Transaction` around it, and every write a `Transaction`. Without one, a read raises `LookupError: No binding for: SnapshotProtocol[Shop]`; a write inside a `Snapshot` raises `StorageInterfaceError` (no write access).

- `nustd.kv.Snapshot(body, scope=S)`: one consistent read view for the whole body.
- `nustd.kv.Transaction(body, scope=S)`: the body's writes land together at a clean exit, or none do if it raises. Reads inside see the transaction's own pending writes.
- `nustd.kv.Atomic(body, scope=S)`: picks `Transaction` if the body writes, else `Snapshot`.
- Several children form one `Sequential` body: `Transaction(a, b, scope=S)`.
- Brackets are transparent: they yield the body's own value. `Snapshot(read)` is still a read and cannot stand bare in a `>>` chain; sink it with `.set(...)`.
- Brackets open lazily, so one around a body that touches no storage costs nothing.
- Keep brackets short. Never hold one across a loop that waits, a `Delay`, or a reactive Flow: a held snapshot never sees new writes and a held transaction never commits. Bracket each step inside instead.
- What a read yields stays tied to its bracket. A container read (`Shop.stock["apl"]`) yields a live view that fails with `StorageClosedError` once the bracket closes, and so do `.keys()`, `.values()` and `.items()`. Whatever leaves the bracket (a `ForEachParReactive`'s items, a value held in `nu.let`, a host function's argument) is made plain inside it: `nu.list(Shop.stock.keys())`. `nu.list` makes the list plain, not the Shape values in it; project those with `nu.Dict.of(...)` as above, or `nu.dict(value)`.

### `scope=`

`scope` is the Shape whose storage the bracket is for. It routes to the navigator bound under that Shape's tag (`memory_navigator(tags=(Shop,))`), falling back to the untagged one. Without `scope`, a sharded store raises `LookupError: No binding for: Navigator`. Pass `scope=` on every hand-written bracket so the program survives a later split.

### `auto_flow_atomic`

`nustd.kv.auto_flow_atomic(term, scope=None)` places the brackets for you. At each Flow it wraps every direct child that writes in a `Transaction` and every one that only reads in a `Snapshot`, so sibling branches commit independently; brackets already there are kept. Loops, waits and reactive Flows get a bracket per step, never one around themselves.

- Wrap once, at the top of the app, where the storage layout is known. A reusable function returns a raw term and leaves the wrapping to its caller.
- Sharded: run one pass per scope first, then the default pass. The default pass treats every ref as its own, so run first it would leave nothing for the scoped ones.

```python fragment
term = program
for shard in (Orders, Users):
    term = nustd.kv.auto_flow_atomic(term, scope=shard)
term = nustd.kv.auto_flow_atomic(term)
app = nu.With(
    nustd.kv.rocksdb_navigator(".db/orders", tags=(Orders,)),
    nustd.kv.rocksdb_navigator(".db/users", tags=(Users,)),
    body=term,
)
```

## Concurrency

- Commits can lose a race to another writer. `nustd.kv.RetryOnConflict(Transaction(...))` re-runs the transaction on a conflict or a lock timeout and on nothing else. Put it outside the `Transaction`, so each attempt re-enters the bracket and reads fresh state. Defaults: 5 attempts with delay, backoff and jitter (honoured under `nu.arun`); it takes `Retry`'s keywords (`max_attempts=`, `delay=`, ...).
- Any write to a shared key (a counter, a membership set, a list length) under several workers needs it. A bare `Transaction` there fails the whole program on the first conflict.
- Create shared containers in one seed step before workers fan out, not in a race on first insert.

## Reads as Queries

Reads are composed in Nu, never pulled into Python and looped over.

- `.keys()`, `.values()`, `.items()` yield a list; `nu.Iter(...)` turns it into a stream for `nu.Map`, `nu.Filter`, `nu.ForEachDo`. `.items()` gives `(key, value)` pairs: `entry[0]`, `entry[1]["field"]`. A Shape value from `.values()` is indexed the same way, `todo["done"]`; attribute access (`todo.done`) fails at run time.
- A stream reaches a scalar slot only through a reduction: `nu.Collect`, `nu.First`, `nu.Count`, `nu.Sum`. `nu.Len` is not one: it takes the list (`nu.Len(Shop.stock)`), and over a stream it is refused (`scalar_stream_refused`). Several counts over one store go in one `nu.Dict.of(...)` under one `Snapshot`.
- Rows are dicts built with `nu.Dict.of`. Do not wrap them in Python classes; format fields with a `@nu.host` function inside the row expression.
- `.len()`, `.contains(k)` and `.keys()` are answered by storage without loading the values.

## Tests

Build a Context once and run brackets against it; the held Context never leaves the fixture.

```python fragment
from virtuals import Navigator

with nustd.kv.memory_storage() as storage:
    ctx = nu.Context().bind(Navigator, Navigator(storage))
    nu.run(nustd.kv.Transaction(Shop.restocks.set(0), scope=Shop), ctx)
    assert nu.run(nustd.kv.Snapshot(Shop.restocks + 1, scope=Shop), ctx)[0] == 1
```

## Watching changes

Changes to kv slots drive reactive Flows (`ReconcileReactive`, `WaitReactive`, `ForEachParReactive`, nu/reactive). Each subscription below is a read, so it needs a bracket like any other (`auto_flow_atomic` places it). On `entries = nustd.kv.DictRef.slot(Todo)`:

| Subscription | Fires on |
| --- | --- |
| `entries.on_change()` | any write under the dict: a key added or removed, and a field of any entry (`entries[k].done.set(...)`) |
| `entries.on_children_change()` | a key added or removed; not a field write inside an entry |
| `entries.on_child_change(k)` | key `k` written whole or removed; not a field write inside it |
| `entries.on_descendants_change("*", "done")` | the `done` field of any entry, including an entry written whole or removed |
| `entries[k].on_change()` | any write under entry `k` |
| `ref.on_change()` on a leaf | that value |

`on_descendants_change(*pattern)` takes one segment per level below the container, a key or `"*"` for any one key: `("*",)` is the entries themselves, `("*", "*")` any field of any entry. There is no deep wildcard.

Pick the narrowest that covers what the body reads: a list of rows follows `on_children_change()`, one row its own `entries[k].on_change()`, a total over every entry `on_change()`.

## Minting ids

A key minted for a new entry must be minted when the term runs, once per click or per message, not once when the module builds the term. A Python call at build time (`uuid.uuid4()`, `time.time_ns()`) bakes one id into the term and every add then writes the same key.

- Order does not matter: `nu.str(nustd.uuid.uuid4())`, a fresh uuid at each evaluation.
- Rows must come back in the order they were added: a dict lists its keys sorted, so mint keys that sort by time, with a `@nu.host` function (nu/host). It runs at each evaluation.
- A counter in the store (`next_id`) works too, but it is a shared key every add writes: read and write it in one `Transaction` under `RetryOnConflict`.

```python run
import time

import nu
import nustd.kv


class Todo(nu.Shape):
    text = nustd.kv.StrRef.slot()
    done = nustd.kv.BoolRef.slot()


class Todos(nu.Shape):
    entries = nustd.kv.DictRef.slot(Todo)
    pending = nustd.kv.PrimitiveListRef.slot()


@nu.host
def new_id():
    return f"t{time.time_ns():020d}"


def add(text):
    return Todos.entries[new_id()].set(nu.Dict.of(text=text, done=False))


#: The texts of the open todos, in the order they were added.
still_open = nu.Collect(
    nu.Map(
        nu.Filter(nu.Iter(Todos.entries.values()), lambda t: nu.Bool(t["done"]).not_()),
        lambda t: t["text"],
    )
)


def out():
    program = add("milk") >> add("eggs") >> Todos.pending.set(still_open)
    return nu.With(nustd.kv.memory_navigator(), body=nustd.kv.auto_flow_atomic(program))
```

After the run `Todos.pending` holds `['milk', 'eggs']`: two keys, minted one per `add`.
