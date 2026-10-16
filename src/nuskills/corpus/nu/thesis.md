---
title: What Nu is
summary: Refs, Interactions, Fabrics, Contexts, and the six kinds every Nu term belongs to.
---

# What Nu is

`Nu = Ref | Interaction`. Every term of a Nu program is one of the two.

**Ref** names an address: a dict slot, a db row, a config key, an http endpoint, a method on an object. It carries the address, not the value. Placed where a value is wanted, a Ref resolves and yields the value it points at. Refs are the only atoms that touch the world: every read and every write happens at a Ref. A term with no Refs has no effects.

**Interaction** says what to do with Refs and other Interactions: read, write, compute, branch, iterate, compose. Refs name, Interactions describe.

**Fabric** is an addressable space where Refs live, plus the machinery that resolves them: a Python dict, RocksDB, an http api, a Ray cluster. **Context** is the set of Fabrics a program runs against. Fabrics execute.

The program is the Interaction; the world is in the Context. The same program against a different Context touches a different world with no edit: test, staging and prod are one program with three bindings.

```python run
import nu


class Counter(nu.Shape):
    n = nu.IntRef.slot()


bump = Counter.n.set(Counter.n + 1)


def out():
    # One program, two worlds: each Provide hands it a fresh dict holding a different n.
    return nu.Provide(dict, {"n": 1}, bump) >> nu.Provide(dict, {"n": 41}, bump)
```

## Mutation is the point

`Context v0` -> `Interaction(Ref)` -> `Context v1`, with `v1 != v0`. A program exists to change its Context. An atom matters only if it mutates the Context or yields a value an ancestor consumes on the way to a mutation. A program that writes nothing still runs (validation only warns, `program_mutates`), but changes nothing.

Constructing a term runs nothing: `Counter.n.set(Counter.n + 1)` is an immutable value describing a write. Laws are checked when the term is compiled and validated, which `nu.run` does first, so a broken composition fails with a `ValidationError` before any effect.

## The six kinds

| Kind | Mutates Context | Yields a value | Role |
| --- | --- | --- | --- |
| Ref | no (own) | yes | address atom; the only path to the Context |
| Query | no | yes | pure value producer |
| Command | yes | no | pure mutator |
| Action | yes | yes | mutates and yields, atomically |
| Flow | no (own) | no | composes mutating children |
| Span | transparent | transparent | cross-cutting wrapper |

The name tells the kind:

- A bare verb (`If`, `Map`, `Add`, `Len`, `Switch`) is a **Query**: it yields a value or a stream.
- A `*Do` suffix (`IfDo`, `SwitchDo`, `WhileDo`, `ForEachDo`, `ForRangeDo`) is a **Flow**: its body needs something that mutates.
- `.set(...)`, `.append(...)`, `.inc()` on a Ref build **Commands**.
- `.pop()` on a list or dict Ref is an **Action**: it removes the element and yields it in one step, because "write, then read back" as two atoms loses atomicity.
- `Sequential` (`>>`), `Parallel` (`|`), `Race` (`&`) are **Flows**.
- `TryCatch`, `Retry`, `Timeout`, `Snapshot`, `Transaction`, `Provide`, `With`, `Frame` are **Spans**: they wrap any term and forward its yield unchanged, so they fit wherever their body fits.

One rule decides what nests where: **a value slot needs something that yields; a body slot needs something that mutates.** nu/composition spells it out.
