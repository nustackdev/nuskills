<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Control flow

Python `if`, `for` and `while` run once, at construct time. Branching and looping over values the program reads happen in Nu atoms. Two families mirror each other: a bare verb is a Query that yields, a `*Do` is a Flow that runs bodies for their writes.

| Yields a value (Query) | Runs bodies (Flow) |
| --- | --- |
| `nu.If(cond, then, else_)` | `nu.IfDo(cond, then, else_=None)` |
| `nu.Switch(sel, {k: value}, default=)` | `nu.SwitchDo(sel, {k: body}, default=None)` |
| `xs.iter().map(f)`, `.filter(f)`, `.sort_by(f)` | `nu.ForEachDo(items, body)` |
| | `nu.ForRangeDo(start, stop, body, step=1)` |
| | `nu.WhileDo(cond, body)`, `nu.ForeverDo(body)` |
| | `nu.Delay(seconds)`, `nu.DelayedDo(seconds, body)` |

- `IfDo` with no `else_` runs nothing on false. An EMPTY `cond` counts as false, in `IfDo`, `WhileDo` and `.filter` alike.
- `SwitchDo` and `Switch` match keys by equality in the order given, first match wins. Keys are plain Python constants.
- `WhileDo` re-checks `cond` before every turn and has no turn cap.
- `ForeverDo` ends only when the process stops, an error escapes, or a surrounding `Race` or `Timeout` cancels it.

## Loops bind their element

A loop body is a lambda (or any function) over the element. It runs once, at construct time, and receives a Ref to the element, not a value: it builds the body and never branches on the element in Python.

```python run
import nu


class Order(nu.Shape):
    goods = nu.ListRef.slot(str)
    lines = nu.ListRef.slot(str)
    total = nu.IntRef.slot()


PRICES = nu.Dict({"apple": 3, "pear": 5, "fig": 11})

each = nu.ForEachDo(
    Order.goods,
    lambda item: Order.lines.append(nu.Str(item).upper())
    >> Order.total.set(Order.total + PRICES[item]),
)
numbered = nu.ForRangeDo(0, Order.goods.len(), lambda i: Order.lines.append(nu.str(i)))


def out():
    seed = Order.goods.set(["apple", "pear", "fig"]) >> Order.lines.set([]) >> Order.total.set(0)
    return nu.Provide(dict, {}, seed >> each >> numbered)
```

- `items` can be a list Ref (`Order.goods`), a stream (`Order.goods.iter().filter(...)`), or a Python list as is.
- The element Ref is an untyped `Object`: operators, `[k]`, `.len()` and keys work as is (`x + 1`, `PRICES[item]`, `Shelf.movies[item]`). Type it for a type's methods: `nu.Str(item).upper()`.
- Nested lambdas each get their own name, so an inner body can still read the outer element.
- The named form is equivalent: a body that reads `nu.Attr("item")`, with `item="item"` on `ForEachDo` (`index="index"` on `ForRangeDo`, `key="item"` on `.map`/`.filter`). The name is a context attr bound for one body run, released after. Use it when the body is built elsewhere or two loops must share a name.

`nu.ForEachParAsync(items, body)` runs every element's body at once on the event loop, each with its own binding; it needs `arun`.

## Streams and reductions

A stream starts from a container's `.iter()` (`nu.List(value).iter()` for a value), chains `.filter(f)` and `.map(f)`, stream in, stream out, pulled lazily, reorders with `.sort_by(f)`, `.unique()`, `.enumerate()`, `.zip(ys)`, `.flatten()`, and leaves through `.to_list()`, `.to_set()`, `.first()` or a fold: `.count()`, `.sum()`, `.min()`, `.max()`, `.last()`, `.any()`, `.all()`.

```python run
import nu


class Shop(nu.Shape):
    prices = nu.ListRef.slot(int)
    cheap = nu.ListRef.slot(int)
    summary = nu.DictRef.slot(int)


cheap = Shop.prices.iter().filter(lambda p: p < 10)


def out():
    return nu.Provide(
        dict,
        {"prices": [3, 12, 5, 30]},
        Shop.cheap.set(cheap.map(lambda p: p * 2).to_list())
        >> Shop.summary.set(
            nu.Dict.of(
                count=Shop.prices.iter().filter(lambda p: p >= 10).count(),
                top=Shop.prices.iter().max(),
            )
        ),
    )
```

Cardinality is checked. A scalar consumer fed a stream is refused (`scalar_stream_refused`: `nu.Add(xs.iter().map(f), 1)`), and a Reduction fed a plain list is refused (`reduction_takes_stream`: `nu.Sum(Shop.prices)`; write `Shop.prices.iter().sum()`). `nu.Sorted(list_value)` is the exception that takes a scalar list and yields a list, like Python's `sorted`.

Several counts over one source belong in one `nu.Dict.of(...)` row, each its own walk, as above. Rows are dicts built in the program, never a Python loop over pulled results.

## Scratch state: let and Frame

A value one body computes and reads again (a counter, an accumulator) lives in a scoped mem store, not in Python variables and not in a Shape bound for the whole app.

```python run
import nu


class Stats(nu.Shape):
    xs = nu.ListRef.slot(int)
    mean = nu.FloatRef.slot()


class Acc(nu.Shape):
    count = nu.IntRef.slot()
    total = nu.IntRef.slot()


step = lambda x: Acc.count.inc() >> Acc.total.set(Acc.total + x)
mean = nu.Frame(
    Acc,
    nu.ForEachDo(Stats.xs, step) >> Stats.mean.set(Acc.total / Acc.count),
    count=0,
    total=0,
)
steps = nu.let(0, lambda n: nu.WhileDo(n < 3, n.set(n + 1)) >> nu.print("turns:", n))


def out():
    return nu.Provide(dict, {"xs": [1, 2, 6]}, mean >> steps)
```

- `nu.Frame(Shape, body, **initial)` binds a fresh dict for `Shape` around `body`, writes the initial values, and drops it on exit. Every run, every parallel arm and every nested entry gets its own dict.
- `nu.let(value, lambda ref: body)` is the one-slot frame. `value` (a literal or any term, eg a read or a host call) is evaluated once on entry and held; the body reads it through the ref as often as it likes, so one reading feeds several places. This is how a value crosses from one bracket or step to the next. The ref is an untyped `ObjectRef`: operators work as is (`n + 1`); type it for a type's methods (`nu.Str(n).strip()`).
- Both yield whatever the body yields, so `nu.let(5, lambda n: n * 2)` yields 10 and fits a value slot.
- State that must outlive one call (a cursor across loop turns) needs the frame around the loop, not inside it.
