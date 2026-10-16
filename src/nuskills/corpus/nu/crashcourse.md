---
title: Writing Nu
summary: Shapes and slots, forms first (the operators and methods that build Nu terms), binding a fabric, running a program.
---

# Writing Nu

A Nu program is a Python module that constructs a term. `import nu` gives the kernel: every atom, the Flows, the Spans and the `nu.mem` fabric (state in plain dicts), flat on `nu`. Other fabrics (`nustd.kv`, `nustd.ui`, `nustd.service`, `nustd.http`, ...) live in `nustd`. A module exposes its program as `out()` returning the term.

## Shapes

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

Verbs on every slot: `set init erase exists missing is_empty not_empty fallback`; `init(v)` writes only when the slot is missing. Per type: `inc dec` on `IntRef`; `append extend insert pop remove clear sort reverse len contains index first_elem last_elem slice iter` on `ListRef`; `keys values items get_item set_item del_item update setdefault pop len contains` on `DictRef`; `add discard remove union ...` on `SetRef`; the `str` methods (`upper split startswith ...`) on `StrRef`. Containers declare their element: `nu.DictRef.slot(Movie)`, then `Library.shelf["dune"].title` addresses inside one entry. A slot may not share a name with one of these verbs (nu/pitfalls).

## Forms first

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

## Binding a fabric

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

## Running

`nu.run(term, ctx=None)` compiles, validates and evaluates, and returns `(value, ctx)`. `await nu.arun(term, ctx)` is the async sibling.

```python fragment
value, ctx = nu.run(term, ctx)
value, ctx = await nu.arun(term, ctx)
```

- A program that only writes yields `None`. The result is the changed state: read the dict you bound, or run a read program afterwards.
- A program holding an async-only atom (`ParallelAsync`, `ForEachParAsync`, `Timeout`, the reactive Flows, `nustd.ui`, anything a fabric marks async-only) needs `arun`; `nu.run` refuses it with `RuntimeError: eval: program contains an async-only atom (Timeout); use aeval.`
- Everything else runs under either.

A whole app is one program with one `nu.With(...)` binding every fabric at the bottom (nu/composition). A host that loads the module (a script, a test, a space) calls `out()` and runs the term.

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
