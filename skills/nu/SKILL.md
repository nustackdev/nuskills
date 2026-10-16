---
name: nu
description: Build Nu programs in Python with nucore and nustd (import nu, nustd.kv, nustd.ui, nustd.service), from a single term to a served app. Use when code imports nu or nustd, or the task asks for a Nu program or app, a Nu term, Shapes and Refs, a kv-backed store, or a nustd.ui browser app. Not for cells inside a running nuspace (use the nuspace skill).
---

<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Building Nu programs

Use this skill to write, fix or review a Nu program: a Python module whose `out()` returns a Nu term, run by `nu.run` / `nu.arun` or served with `nustd.ui.serve`.

Before you write:

- Install: `pip install "nustd[all]"` pulls the kernel (`nucore`, imported as `nu`) and every fabric. Use the project's own environment for everything below.
- The API is whatever the installed version says. Render it with `nu.inspect` (the last section here) rather than guessing a name; the catalogue is not copied into this skill, so it never goes stale.
- Check a program builds before you run it: `nu.validate(nu.compile(out()))` raises on a term that is not a valid Nu program.

The sections after the Reference list are the ground every program stands on. Each reference file goes deeper on one topic; open the one the task needs.

## Reference

Open a file when the task needs its topic. A piece id in the text (`nu/control`) names one of these or a section below.

| File | What it covers |
| --- | --- |
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

## What Nu is

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

### Mutation is the point

`Context v0` -> `Interaction(Ref)` -> `Context v1`, with `v1 != v0`. A program exists to change its Context. An atom matters only if it mutates the Context or yields a value an ancestor consumes on the way to a mutation. A program that writes nothing still runs (validation only warns, `program_mutates`), but changes nothing.

Constructing a term runs nothing: `Counter.n.set(Counter.n + 1)` is an immutable value describing a write. Laws are checked when the term is compiled and validated, which `nu.run` does first, so a broken composition fails with a `ValidationError` before any effect.

### The six kinds

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

One rule decides what nests where: **a value slot needs something that yields; a body slot needs something that mutates.** [nu/composition](#composition) spells it out.

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

Verbs on every slot: `set init erase exists missing is_empty not_empty fallback`; `init(v)` writes only when the slot is missing. Per type: `inc dec` on `IntRef`; `append extend insert pop remove clear sort reverse len contains index first_elem last_elem slice iter` on `ListRef`; `keys values items get_item set_item del_item update setdefault pop len contains` on `DictRef`; `add discard remove union ...` on `SetRef`; the `str` methods (`upper split startswith ...`) on `StrRef`. Containers declare their element: `nu.DictRef.slot(Movie)`, then `Library.shelf["dune"].title` addresses inside one entry. A slot may not share a name with one of these verbs ([nu/pitfalls](#pitfalls)).

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
| `xs.iter().count()`, `.sum()`, `.min()`, `.max()`, `.last()`, `.any()`, `.all()` | `nu.Count`, `nu.Sum`, `nu.Min`, `nu.Max`, `nu.Last`, `nu.AnyOf`, `nu.AllOf` |
| `xs.iter().sort_by(f)`, `.unique()`, `.enumerate()`, `.zip(ys)`, `.sorted()` | `nu.SortBy`, `nu.Unique`, `nu.Enumerate`, `nu.Zip`, `nu.Sorted` |
| `s.strip()`, `s.split(",")`, `s.upper()`, `nu.Str(", ").join(xs)` | the `str` atoms |

- Boolean logic is a method, never a keyword: `and`, `or`, `not` raise on a term.
- A plain Python value becomes a literal wherever a child is expected (`Library.tags.append("dune")`, `n + 1`, `x == ""`); never wrap an operand in `nu.Int(0)` or `nu.Str("")`. A bare literal standing alone has no operators; give it a Form: `nu.Int(5) > 3`, `nu.Dict(PRICES)[item]`.
- `nu.Str(x)`, `nu.Int(x)`, `nu.List(x)` only type `x`; they do not convert. `nu.str(x)`, `nu.int(x)`, `nu.list(x)` convert and keep the Form. `nu.ToStr`, `nu.ToInt` convert to a bare atom with no operators.
- Build a dict with `nu.Dict.of(title=Movie.title, year=Movie.year)`, a list with `nu.List.of(a, b)`.
- A stream ends in a fold that keeps chaining: `xs.iter().filter(f).sum() > 10`. Branching has no form: `nu.If` / `nu.IfDo`. A host call or a service stream has no Form either: type it (`nu.Str(slug_of(t)).fallback("")`) or reduce it.

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

A whole app is one program with one `nu.With(...)` binding every fabric at the bottom ([nu/composition](#composition)). A host that loads the module (a script, a test, a space) calls `out()` and runs the term.

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

## Composition

### Operators

`a >> b` is `nu.Sequential(a, b)`: run `a`, then `b`. `a | b` is `nu.Parallel(a, b)`: run both, join when both finish, no order promised. `a & b` is `nu.Race(a, b)`: the first to finish wins. All three are Flows, so every child must mutate.

`>>` does not pass values: `b` never receives `a`'s value. To move a value between steps, write it to a Ref in one step and read the Ref in the next, or hold it in `nu.let` around both ([nu/control](reference/nu/control.md)).

### The slot rule

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

### Sinking a value

The only way a value enters a chain of steps is a write: `ref.set(query)` is a Command, and the write is the value's consumer. A Query placed directly in `>>` has nobody to consume it and is refused (`flow_body_is_mutator`).

Spans are transparent: `nu.TryCatch(query, ...)`, `nustd.kv.Snapshot(query)`, `nu.Provide(dict, {}, query)` still yield, so they fit a value slot and never a body. Wrapping a Query in a Span never makes it a step; set it into a Ref.

A Command's target must be a Ref (`ref_slots`): `nu.Dict.of(a=1).set_item("k", 1)` is refused because a computed dict is not an address.

### Structural slots and value slots

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

### Laying out an app

- One program per app. Shapes at the top of the module, module-level terms composed with `>>` `|` `&`, one `nu.With(...)` at the bottom binding every fabric, then run.
- Every runtime dependency is a bracket in that `With`. Never a Python object that holds a bound Context and exposes `.method(...)` (`open_store(path)`, `Logger(stream)`): the Ref names the location, the bracket binds the fabric.
- A reusable factory returns a raw term and leaves binding to whoever assembles the app; it does not bake in its own `With`. The same term then runs against `memory_navigator()` in a test and `rocksdb_navigator(path)` in production.
- Chain forms (`xs.iter().filter(f).to_list()`, `a.and_(b)`); an atom only where no form says it.
- Inline a term when it is short and appears once. A `def` returning a term earns its place when it is reused, parametrized over a Shape or scope, or so long it hides the outer composition.
- A module-level term (`seed = Cart.total.init(0) >> ...`) reads better than a zero-argument helper that returns it.
- Do not split a `>>` chain across functions just to name it. The `>>` already shows the order.

## Pitfalls

Nu is written in Python and is not Python. The module runs once, to construct a term; the term runs later, against a Context, maybe many times. Most mistakes mix the two moments.

### Construct time is not run time

Every Python statement in the module runs at construct time. `if`, `for`, `while`, `and`, `or`, `not`, `len()`, `in`, comprehensions and f-strings never appear in the program. On a term most of them fail loudly:

- `if term:`, `term and x`, `not term` raise `TypeError: a Nu term has no truth value while building a program`. Branch with `nu.If` / `nu.IfDo` / `nu.SwitchDo`; combine with `.and_()`, `.or_()`, `.not_()`.
- `for x in ref:` raises `TypeError: a Nu term can't be looped over`. Loop with `nu.ForEachDo`, or chain the stream: `ref.iter().filter(f).map(g).to_list()`.
- `len(ref)` and `x in ref` raise; use `ref.len()` and `ref.contains(x)`.

Two fail silently:

- `str(term)` and `f"{term}"` return the rendered term text (a box drawing of atoms), not the value. Build strings in the program: `"n=" + nu.str(Cart.total)`, or `nu.format(value, ".2f")`.
- A Python value computed at construct time is baked into every run. `stamp = time.time()` at import, then `Log.at.set(stamp)`, writes the same number forever, even inside a `ForeverDo`. Ids minted in Python repeat the same way. Anything fresh per run is computed in the program, by an atom or a `@nu.host` function ([nu/host](reference/nu/host.md)).

```python
import nu


class Cart(nu.Shape):
    total = nu.IntRef.slot()
    label = nu.StrRef.slot()


# WRONG: raises TypeError while the module loads, if this line ever runs.
def decided():
    if Cart.total > 3:
        return Cart.label.set("big")
    return Cart.label.set("small")


# RIGHT: the branch is an atom, decided on every run.
def out():
    return Cart.label.set(nu.If(Cart.total > 3, "big", "small"))
```

Construct-time Python is still the right tool for shaping the term from data you hold while constructing it: a loop over a list of Shapes that emits one term each, a constant table passed as a literal.

### Values and yields

- **A Command chain yields `None`.** For a program that only writes, `nu.run` returns `(None, ctx)` and the evidence is in the state. That is success.
- **A read is never a step.** `>>` takes only mutators, so a Ref or Query anywhere in a chain, first or last, is refused (`Cart.total.set(1) >> Cart.total`). Put the read inside a write (`Report.total.set(Cart.total)`), hold it in `nu.let` around the steps that use it, make it the yield of a separate read program, or use an Action that writes and yields in one step.
- **`.pop()` is not a step either.** It comes back wrapped in a Form, which counts as a Query: `Log.last.set(Queue.items.pop())`, never `... >> Queue.items.pop()`.
- **`nu.print(...)` is a Command.** It writes to stdout and yields `None`; it hands nothing back to the caller. To see a value, make it the program's yield.
- **Forms type, they do not convert.** `"n=" + nu.Str(Cart.total)` fails at run time on an int. `nu.str(x)`, `nu.int(x)` convert and keep the Form (`nu.int(Form.age) + 1`). `nu.ToStr` / `nu.ToInt` convert but yield a bare atom with no `+`.
- **Some atoms have no Form.** `nu.Literal(5) > 3` and `nu.Len(x) > 3` raise `TypeError` at construct time. Give them one: `nu.Int(5) > 3`, `ref.len() > 3`, `nu.Str(x).len() > 3`.
- **Reductions take streams.** `nu.Sum(ref)` is refused (`reduction_takes_stream`); write `ref.iter().sum()`. `nu.Sorted(ref)` takes the list itself. A count over a chain is `ref.iter().filter(f).count()`.

### Names

A slot cannot share a name with a Ref method: `items`, `keys`, `values`, `len`, `iter`, `set`, `init`, `pop`, `copy`, `update`, `clear`, `contains`, `exists`, `missing`, `on_change` (on kv Refs) and the rest raise `TypeError: Shape Order: slot 'items' clashes with ShapeRef.items` when the class is created. Pick another word (`goods`, `entries`, `size`, `items_`).

### Anti-patterns

- Atom soup: `nu.And(nu.Gt(nu.Len(x), nu.Int(0)), nu.Not(done))`, `nu.Eq(nu.Str(x), nu.Str(""))`, `nu.Collect(nu.Map(nu.Filter(nu.Iter(xs), f), g))`, `nu.If(x.exists(), x, 0)`. Write the forms: `(x.len() > 0).and_(done.not_())`, `x == ""`, `xs.iter().filter(f).map(g).to_list()`, `x.fallback(0)` ([nu/crashcourse](#writing-nu)).
- A Python object that holds a bound Context and exposes methods (`open_store(path)`, `Logger(stream)`, `Store(path).put(...)`). Every interaction lives in the program under a bracket.
- A Python loop over a read's results that drives further writes (`for row in nu.run(read)[0]: nu.run(write(row))`). Compose it: `nu.ForEachDo(read, lambda row: ...)`.
- Wrapping read results in dataclasses. Rows are dicts built in the program with `nu.Dict.of(...)`.
- Converting a typed value to text before storing it (`ts.set(str(dt))`). A Ref knows its type; give `.set()` the typed value.
- A custom atom that keeps state on `self` or reaches into the runtime to run a nested program. Terms are immutable and shared across runs. Reads are Queries, eval-time Python is `@nu.host`, a write that also yields is an Action.
- `try: nu.run(...) except` as the program's error handling. Handle failures inside the program ([nu/errors](reference/nu/errors.md)).
- Extracting every subexpression into a helper `def`. Helpers are for reuse and parameters; a short term reads best where it is used.

## Looking things up

Nu documents itself from its own code. `nu.inspect` reads a module, an atom, a Ref, a method, or a Shape or Service you wrote, and renders it as text: summary, args, notes, what it yields, worked examples, and for a Ref every method it carries. Read the surface before writing against it: a guessed name or argument is the most common way a program fails.

There are two doors to the same text.

**From Python, outside a program:** `nu.inspect.render(path)` returns the text as a `str`, or `""` when the path names nothing it can describe. From a shell, in the project's environment:

```bash
python -c "import nu; print(nu.inspect.render('nustd.kv'))"
```

**Inside a program:** `nu.inspect.Inspect(path)` is a Query atom that yields the same text, or `EMPTY` when the path names nothing. Make it the program's yield; `nu.print` around it only writes to the process's stdout.

```python run
import nu


def out():
    return nu.inspect.Inspect("nu.mem")
```

### Paths

`path` is one dotted string. Resolution imports the longest module prefix and walks the rest.

| Path | Renders |
| --- | --- |
| a module: `nu.mem`, `nustd.kv`, `nu.core.flows`, `myapp.shapes` | its docstring, then one line per Shape, Service, Form, Ref, Interaction and function it holds |
| a flat or qualified subject: `nu.ForEachDo`, `nu.core.flows.WhileDo`, `nustd.kv.Snapshot` | the full record: call form, args, notes, yields, examples |
| a Ref class: `nu.IntRef`, `nustd.kv.DictRef`, `nustd.ui.ButtonRef` | its record plus one line per method and operator it supports |
| a method: `nustd.ui.ButtonRef.set` | its signature and arguments |
| your own Shape or Service: `myapp.shapes.Task` | its prose and one line per slot or endpoint |
| one entry of it: `myapp.shapes.Task.title`, `myapp.shapes.Task.owner.email` | that slot's Ref record, walking nested Shapes |

### How to use it

- **Module first, then exact names.** Render the module (`nustd.kv`, `nustd.service`, `nustd.ui`), take the exact name off its list, then render that subject. Never guess a subject path: a wrong one gives back nothing, and an atom you invent does not exist.
- **Every fabric outside the kernel is under `nustd`.** The kernel and the memory fabric are `nu` (flat names like `nu.IntRef`, `nu.ForEachDo` resolve); everything else (`nustd.kv`, `nustd.service`, `nustd.ui`, `nustd.http`, `nustd.llm`, `nustd.uuid`, ...) needs its `nustd.` path.
- **Ref records list the verbs.** The methods table of a Ref is the authoritative list of what `.set`, `.append`, `.on_change`, `.range` and the operators accept on that slot type. Same-named Refs in different fabrics (`nu.IntRef` and `nustd.kv.IntRef`) carry different surfaces; render the one you declare.
- **Examples are tested.** An example line ending in `-> value` is a doctest that passes against the installed version, so copy its form.
- **The text is whole.** Nothing is truncated; a fabric module runs to several thousand characters. Read it through.
