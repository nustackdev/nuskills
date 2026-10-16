---
title: Composition
summary: The slot rule that decides what nests where, sequencing, moving values between steps, and how to lay out an app.
---

# Composition

## Operators

`a >> b` is `nu.Sequential(a, b)`: run `a`, then `b`. `a | b` is `nu.Parallel(a, b)`: run both, join when both finish, no order promised. `a & b` is `nu.Race(a, b)`: the first to finish wins. All three are Flows, so every child must mutate.

`>>` does not pass values: `b` never receives `a`'s value. To move a value between steps, write it to a Ref in one step and read the Ref in the next, or hold it in `nu.let` around both (nu/control).

## The slot rule

**A value slot needs something that yields. A body slot needs something that mutates.** Every composition law is this rule applied:

| Child | Value slot (operand, argument, `cond`, `items`) | Body slot (`>>` child, `IfDo` branch, loop body) |
| --- | --- | --- |
| Ref, Query | yes | no |
| Action | yes | yes |
| Command | no | yes |
| Flow | no | yes |
| Span | whatever its body is | whatever its body is |

So a read sits inside a write's value slot, never beside it, and a Flow takes a Ref or Query only in its parameter slots (`cond`, `items`, `start`, `stop`, a selector).

`.pop()` on a list or dict Ref is an Action, but the verb hands it back wrapped in a Form (`Int(Pop(...))`), and the Form counts as a Query. Use it in a value slot (`Log.last.set(Queue.items.pop())`); as a bare step in `>>` it is refused.

```python
import nu


class Cart(nu.Shape):
    total = nu.IntRef.slot()
    prices = nu.ListRef.slot(int)


# A Ref read inside a Command's value slot, an Action in a value slot.
ok = Cart.total.set(Cart.total * 2) >> Cart.total.set(Cart.prices.pop())

# Builds fine, refused at validation: a Query cannot hold a Command.
bad = nu.Add(Cart.total.set(1), 2)

# Also refused: a Ref read as a peer in a body. Sequential cannot hold a ref.
bad_too = Cart.total.set(1) >> Cart.total


def out():
    return ok
```

Validation names the law and where it broke:

```text
ValidationError: invalid program:
  [composition] scalar_query cannot hold scalar_command
      at Add  path=()  chain=Add
```

## Sinking a value

The only way a value enters a chain of steps is a write: `ref.set(query)` is a Command, and the write is the value's consumer. A Query placed directly in `>>` has nobody to consume it and is refused (`flow_body_is_mutator`).

Spans are transparent: `nu.TryCatch(query, ...)`, `nustd.kv.Snapshot(query)`, `nu.Provide(dict, {}, query)` still yield, so they fit a value slot and never a body. Wrapping a Query in a Span never makes it a step; set it into a Ref.

A Command's target must be a Ref (`ref_slots`): `nu.SetItem(nu.Dict.of(a=1), "k", 1)` is refused because a computed dict is not an address.

## Structural slots and value slots

A Ref chain such as `Library.shelf[key].title` holds its parent as an address, not as a value: `Library.shelf` is never read, it only locates. The key inside `[...]` is a value slot. Put a Ref there and it is read when the outer Ref resolves, so the address follows the state:

```python run
import nu


class Movie(nu.Shape):
    title = nu.StrRef.slot()


class Library(nu.Shape):
    pick = nu.StrRef.slot()
    shelf = nu.DictRef.slot(Movie)


def out():
    return nu.Provide(
        dict,
        {},
        Library.pick.set("dune")
        >> Library.shelf[Library.pick].title.set("Dune")
        >> Library.pick.set("heat")
        >> Library.shelf[Library.pick].title.set("Heat"),
    )
```

One term, two different addresses: nothing in Python closes over the key. The same holds for loop elements: `Library.shelf[x]` inside a `ForEachDo(..., lambda x: ...)` addresses through each element in turn.

## Laying out an app

- One program per app. Shapes at the top of the module, module-level terms composed with `>>` `|` `&`, one `nu.With(...)` at the bottom binding every fabric, then run.
- Every runtime dependency is a bracket in that `With`. Never a Python object that holds a bound Context and exposes `.method(...)` (`open_store(path)`, `Logger(stream)`): the Ref names the location, the bracket binds the fabric.
- A reusable factory returns a raw term and leaves binding to whoever assembles the app; it does not bake in its own `With`. The same term then runs against `memory_navigator()` in a test and `rocksdb_navigator(path)` in production.
- Inline a term when it is short and appears once. A `def` returning a term earns its place when it is reused, parametrized over a Shape or scope, or so long it hides the outer composition.
- A module-level term (`seed = Cart.total.init(0) >> ...`) reads better than a zero-argument helper that returns it.
- Do not split a `>>` chain across functions just to name it. The `>>` already shows the order.
