<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Worked programs

Each program is a whole module. `out()` returns the term; whatever hosts it (a script, a test, a space) runs it. As a script, end with `nu.run(out())`, or `asyncio.run(nu.arun(out()))` when the program has async-only atoms.

## 1. State, a loop, a branch

```python run
import nu


class Cart(nu.Shape):
    goods = nu.ListRef.slot(str)
    total = nu.IntRef.slot()
    label = nu.StrRef.slot()


PRICES = {"apple": 3, "pear": 5, "fig": 11}

checkout = (
    Cart.goods.init([])
    >> Cart.total.init(0)
    >> nu.ForEachDo(
        nu.Iter(["apple", "pear", "fig"]),
        lambda item: Cart.goods.append(item)
        >> Cart.total.set(Cart.total + nu.GetItem(PRICES, item)),
    )
    >> nu.IfDo(Cart.total > 10, Cart.label.set("big"), Cart.label.set("small"))
    >> nu.WhileDo(Cart.total < 50, Cart.total.set(Cart.total * 2))
)


def out():
    return nu.Provide(dict, {}, checkout)
```

Final state: `{'goods': ['apple', 'pear', 'fig'], 'total': 76, 'label': 'big'}`.

- `.init(v)` seeds a missing slot. Without it the first `append` reads `EMPTY` and raises `ValueError: cannot write with an EMPTY operand`.
- The loop lambda runs once, at construct time. `item` is a Ref to the current element, not a string: it composes (`nu.GetItem(PRICES, item)`) but Python cannot inspect it.
- A plain Python list or dict in a value slot becomes a literal: `nu.Iter([...])`, `PRICES`.
- `Cart.total + x` and `Cart.total > 10` build terms, not numbers and bools; `nu.IfDo` and `nu.WhileDo` decide at run time. A Python `if` here would run once and leave no trace in the program.
- To see the state from Python, bind the dict from outside: `state = {}; nu.run(checkout, nu.Context().bind(dict, state))`.

## 2. Storage plus a service

A payment stub behind a Service, orders in kv, settled idempotently: run it twice and nobody is charged twice.

```python run
import nu
import nustd


class Gateway:
    """Stand-in for a payment client."""

    def __init__(self) -> None:
        self.charges: list[tuple[str, int]] = []

    def charge(self, customer: str, cents: int) -> str:
        self.charges.append((customer, cents))
        return f"rcpt-{len(self.charges)}"


class Pay(nu.Service):
    charge = nustd.service.ActionRef.method()


class Order(nu.Shape):
    customer = nustd.kv.StrRef.slot()
    cents = nustd.kv.IntRef.slot()
    receipt = nustd.kv.StrRef.slot()


class Book(nu.Shape):
    orders = nustd.kv.DictRef.slot(Order)
    revenue = nustd.kv.IntRef.slot()
    summary = nustd.kv.PrimitiveDictRef.slot()


seed = nu.IfDo(
    Book.revenue.missing(),
    Book.revenue.set(0)
    >> Book.orders["o1"].set({"customer": "ada", "cents": 1200})
    >> Book.orders["o2"].set({"customer": "bo", "cents": 450})
    >> Book.orders["o3"].set({"customer": "cy", "cents": 980, "receipt": "rcpt-old"}),
)


def settle(oid: nu.Nu) -> nu.Nu:
    order = Book.orders[oid]
    return nu.IfDo(
        order.receipt.missing(),
        order.receipt.set(Pay.charge(customer=order.customer, cents=order.cents))
        >> Book.revenue.set(Book.revenue + order.cents),
    )


report = Book.summary.set(nu.Dict.of(orders=nu.Len(Book.orders), revenue=Book.revenue))

program = seed >> nu.ForEachDo(nu.Iter(Book.orders.keys()), settle) >> report


def out():
    return nu.With(
        nustd.kv.memory_navigator(),
        nustd.service.bind(Pay, target=Gateway()),
        body=nustd.kv.auto_flow_atomic(program),
    )
```

Final state: `Book.summary` is `{'orders': 3, 'revenue': 1650}`; the gateway saw two charges, `ada` and `bo`.

- `settle` is an ordinary Python function that builds a term. As the loop body it is called once with the element Ref, like a lambda; `Book.orders[oid]` is then an address computed at run time.
- `Pay.charge` mutates the gateway and yields the receipt, so it is an `ActionRef`, and its value sinks straight into `order.receipt.set(...)`.
- The `missing()` guards make the program idempotent: seed only an empty store, charge only an order with no receipt.
- `auto_flow_atomic` brackets each step: a `Snapshot` for reading the keys, a `Transaction` per loop turn. One order's failure does not undo the others.
- `nu.With` stacks both fabrics in one head; each call finds its own by tag.

## 3. A host function, a frame, a report

```python run
import nu


@nu.host
def words_of(text: str) -> list:
    return text.lower().split()


class Tally(nu.Shape):
    words = nu.IntRef.slot()
    longest = nu.StrRef.slot()


class Report(nu.Shape):
    stats = nu.DictRef.slot(int)


TEXT = "the quick brown fox jumps over the lazy dog"

count = nu.Frame(
    Tally,
    nu.ForEachDo(
        nu.Iter(words_of(TEXT)),
        lambda w: Tally.words.inc()
        >> nu.IfDo(nu.Gt(nu.Len(w), nu.Len(Tally.longest)), Tally.longest.set(w)),
    )
    >> Report.stats.set(nu.Dict.of(words=Tally.words, longest_len=nu.Len(Tally.longest))),
    words=0,
    longest="",
)


def out():
    return nu.Provide(dict, {}, count, tag=Report)
```

Final state: `{'stats': {'words': 9, 'longest_len': 5}}`.

- `@nu.host` makes `words_of` an atom. It runs when the program runs, on the resolved value of its argument.
- `nu.Frame(Tally, body, words=0, longest="")` gives the body a fresh private dict for `Tally`, seeded from the keywords, dropped at the end. Scratch counters live there, not in Python globals or the app's state.
- `Report` is bound separately (`tag=Report`), so only the result outlives the run.
- `nu.Len(...)` is a bare atom with no Form, so the comparison is spelled `nu.Gt(a, b)`. Refs and Forms (`Tally.words`, `ref.len()`) overload `>` directly.
