<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Pitfalls

Nu is written in Python and is not Python. The module runs once, to construct a term; the term runs later, against a Context, maybe many times. Most mistakes mix the two moments.

## Construct time is not run time

Every Python statement in the module runs at construct time. `if`, `for`, `while`, `and`, `or`, `not`, `len()`, `in`, comprehensions and f-strings never appear in the program. On a term most of them fail loudly:

- `if term:`, `term and x`, `not term` raise `TypeError: a Nu term has no truth value while building a program`. Branch with `nu.If` / `nu.IfDo` / `nu.SwitchDo`; combine with `.and_()`, `.or_()`, `.not_()`.
- `for x in ref:` raises `TypeError: a Nu term can't be looped over`. Loop with `nu.ForEachDo`, or chain the stream: `ref.iter().filter(f).map(g).to_list()`.
- `len(ref)` and `x in ref` raise; use `ref.len()` and `ref.contains(x)`.

Two fail silently:

- `str(term)` and `f"{term}"` return the rendered term text (a box drawing of atoms), not the value. Build strings in the program: `"n=" + nu.str(Cart.total)`, or `nu.format(value, ".2f")`.
- A Python value computed at construct time is baked into every run. `stamp = time.time()` at import, then `Log.at.set(stamp)`, writes the same number forever, even inside a `ForeverDo`. Ids minted in Python repeat the same way. Anything fresh per run is computed in the program, by an atom or a `@nu.host` function ([nu/host](../../reference/nu/host.md)).

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

## Values and yields

- **A Command chain yields `None`.** For a program that only writes, `nu.run` returns `(None, ctx)` and the evidence is in the state. That is success.
- **A read is never a step.** `>>` takes only mutators, so a Ref or Query anywhere in a chain, first or last, is refused (`Cart.total.set(1) >> Cart.total`). Put the read inside a write (`Report.total.set(Cart.total)`), hold it in `nu.let` around the steps that use it, make it the yield of a separate read program, or use an Action that writes and yields in one step.
- **`.pop()` is not a step either.** It comes back wrapped in a Form, which counts as a Query: `Log.last.set(Queue.items.pop())`, never `... >> Queue.items.pop()`.
- **`nu.print(...)` is a Command.** It writes to stdout and yields `None`; it hands nothing back to the caller. To see a value, make it the program's yield.
- **Forms type, they do not convert.** `"n=" + nu.Str(Cart.total)` fails at run time on an int. `nu.str(x)`, `nu.int(x)` convert and keep the Form (`nu.int(Form.age) + 1`). `nu.ToStr` / `nu.ToInt` convert but yield a bare atom with no `+`.
- **Some atoms have no Form.** `nu.Literal(5) > 3` and `nu.Len(x) > 3` raise `TypeError` at construct time. Give them one: `nu.Int(5) > 3`, `ref.len() > 3`, `nu.Str(x).len() > 3`.
- **Reductions take streams.** `nu.Sum(ref)` is refused (`reduction_takes_stream`); write `ref.iter().sum()`. `nu.Sorted(ref)` takes the list itself. A count over a chain is `ref.iter().filter(f).count()`.

## Names

A slot cannot share a name with a Ref method: `items`, `keys`, `values`, `len`, `iter`, `set`, `init`, `pop`, `copy`, `update`, `clear`, `contains`, `exists`, `missing`, `on_change` (on kv Refs) and the rest raise `TypeError: Shape Order: slot 'items' clashes with ShapeRef.items` when the class is created. Pick another word (`goods`, `entries`, `size`, `items_`).

## Anti-patterns

- Atom soup: `nu.And(nu.Gt(nu.Len(x), nu.Int(0)), nu.Not(done))`, `nu.Eq(nu.Str(x), nu.Str(""))`, `nu.Collect(nu.Map(nu.Filter(nu.Iter(xs), f), g))`, `nu.If(x.exists(), x, 0)`. Write the forms: `(x.len() > 0).and_(done.not_())`, `x == ""`, `xs.iter().filter(f).map(g).to_list()`, `x.fallback(0)` ([nu/crashcourse](../../SKILL.md#writing-nu)).
- A Python object that holds a bound Context and exposes methods (`open_store(path)`, `Logger(stream)`, `Store(path).put(...)`). Every interaction lives in the program under a bracket.
- A Python loop over a read's results that drives further writes (`for row in nu.run(read)[0]: nu.run(write(row))`). Compose it: `nu.ForEachDo(read, lambda row: ...)`.
- Wrapping read results in dataclasses. Rows are dicts built in the program with `nu.Dict.of(...)`.
- Converting a typed value to text before storing it (`ts.set(str(dt))`). A Ref knows its type; give `.set()` the typed value.
- A custom atom that keeps state on `self` or reaches into the runtime to run a nested program. Terms are immutable and shared across runs. Reads are Queries, eval-time Python is `@nu.host`, a write that also yields is an Action.
- `try: nu.run(...) except` as the program's error handling. Handle failures inside the program ([nu/errors](../../reference/nu/errors.md)).
- Extracting every subexpression into a helper `def`. Helpers are for reuse and parameters; a short term reads best where it is used.
