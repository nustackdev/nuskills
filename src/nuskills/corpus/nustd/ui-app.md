---
title: A UI app
summary: Serving a plain Nu program in the browser: Page, Index, nustd.ui.serve, one program per tab, and the keyed list over a store with per-row actions.
---

# A UI app

A plain Nu app draws in the browser through `nustd.ui.serve`. You declare the pages as Shapes, write one ui program, and serve the two. Leaves are in nustd/ui-refs, containers in nustd/ui-layout.

## Pages and the Index

- A **Page** is a Section with a route: subclass `nustd.ui.Page` and declare its slots like any Shape (leaves, Rows, Grids, Cards, ...).
- The **Index** is the app: subclass `nustd.ui.Index`, one slot per page, `Home.slot("/")`. `slot(route, label=, icon=)` names the page in the sidebar. The sidebar shows only with more than one page; `sidebar = False` on the Index turns it off.
- Structural Refs sit on the Index and draw nothing in the body: `TitleRef.slot(default="My app")` is the document title, `NavRef` is the browser history (`set(uri)`, `replace(uri)`, `back()`, `on_change()`).
- Addresses run from the Index slot down: `App.home.stats.users` is `("home", "stats", "users")`, so two pages can each declare a `stats`. A lone Page can be served without an Index; its Refs then start at their own slot names.
- At boot every slot the pages declare is drawn with its slot props, in declaration order, before the program writes anything. Keyed children and Refs built alone still appear on first write.

## serve

```text
nustd.ui.serve(index, program, *, host="127.0.0.1", port=8080, open_browser=True, static="nudle", routes=())
```

- It is a term: run it with `asyncio.run(nu.arun(app))`. Every `nustd.ui` atom is async-only.
- `index` is the Index, or one Page. `program` is the ui program.
- **The program runs once per open tab**, with that tab's Session bound. Two tabs are two runs of it, each drawing on its own tab. What tabs share lives in a store, never in the ui: a click in one tab writes the store, and every tab's program redraws from the store's `on_change()`.
- serve prepends the boot, so the program can write at once. When it returns, that tab stops reacting; a raise is printed and stops that tab only. Programs that wait on clicks or changes never return.
- serve never returns either. Work that is not per tab (a ticker, a job) is a sibling arm: `nu.ParallelAsync(nustd.ui.serve(App, ui), tick)`. serve goes in a `body=`, never in a `nu.With` spec slot.
- `open_browser=False` serves without opening a tab (a server box, a test). `static=None` serves the websocket alone (headless, or a separate vite dev server); `routes` adds Starlette routes.
- To check an app without serving it: `nu.validate(nu.compile(out()))` raises on a term that is not a valid program.

The shape of the program is: write every Ref once (seed), then one `nu.ParallelAsync` arm per thing that keeps going (a `ReactForever` per button, a redraw per store change).

## A tab-only app

No store: what one tab types, that tab shows.

```python
import asyncio

import nu
import nustd.ui


class Ask(nustd.ui.Row):
    name = nustd.ui.InputRef.slot(placeholder="Your name")
    go = nustd.ui.ButtonRef.slot(label="Greet", icon="send")


class Home(nustd.ui.Page):
    title = nustd.ui.HeadingRef.slot(label="Hello")
    ask = Ask.slot(gap=2)
    said = nustd.ui.TextRef.slot()


class App(nustd.ui.Index):
    title = nustd.ui.TitleRef.slot(default="Hello")
    home = Home.slot("/")


h = App.home
greet = nu.IfDo(nu.Str(h.ask.name) != "", h.said.set(nu.Str("Hello, ") + nu.Str(h.ask.name)))
ui = h.said.set("") >> nu.ReactForever(h.ask.go.on_click(), greet)


def out():
    return nustd.ui.serve(App, ui)


if __name__ == "__main__":
    asyncio.run(nu.arun(out()))
```

## Shared state: a store and a ticker

State every tab sees lives in a store bound around the whole program. The ui program follows it, a sibling arm changes it.

```python
import asyncio

import nu
import nustd.kv
import nustd.ui


class Counter(nu.Shape):
    value = nustd.kv.IntRef.slot()


class Controls(nustd.ui.Row):
    count = nustd.ui.StatRef.slot(label="Count")
    reset = nustd.ui.ButtonRef.slot(label="Reset", variant="secondary", icon="rotate-ccw")


class Dashboard(nustd.ui.Page):
    controls = Controls.slot(gap=3)


class App(nustd.ui.Index):
    home = Dashboard.slot("/")


c = App.home.controls

#: Per tab: the stat follows the count; a click resets it for everyone.
ui = nu.ParallelAsync(
    nu.ReconcileReactive(Counter.value.on_change(), c.count.set_value(nu.str(Counter.value.fallback(0)))),
    nu.ReactForever(c.reset.on_click(), Counter.value.set(0)),
)

#: Once for the app: tick the count up every second.
tick = Counter.value.init(0) >> nu.ForeverDo(Counter.value.inc() >> nu.Delay(1.0))

app = nu.With(
    nustd.kv.rocksdb_navigator(".counter"),
    body=nu.ParallelAsync(
        nustd.ui.serve(App, nustd.kv.auto_flow_atomic(ui)),
        nustd.kv.auto_flow_atomic(tick),
    ),
)


def out():
    return app


if __name__ == "__main__":
    asyncio.run(nu.arun(app))
```

- `nustd.kv.auto_flow_atomic(...)` brackets each step of the program in its own snapshot or transaction, so no bracket is held across a wait. How kv brackets work is nustd/kv.
- The stat is a level view: `ReconcileReactive` draws it right after subscribing, on every change and on re-checks, so it needs no seed write and a missed notification is drawn late, never lost. Clicks are events: `ReactForever` (nu/reactive).
- The click writes the store, not the stat. Every tab's reconcile arm then redraws its own stat, the clicking tab included.
- Keep per-tab view state (a picked filter, a selected row) in the ui Refs themselves and read them back with `nu.Str(ref)`. Only state that tabs share goes in the store.

## A keyed list over a store

A todo list: rows added and removed by anyone, each row with its own checkbox and delete button. One live arm per row, so a change touches only its row and nothing is erased except a row that is gone.

```python
import asyncio
import time

import nu
import nustd.kv
import nustd.ui


class Todo(nu.Shape):
    text = nustd.kv.StrRef.slot()
    done = nustd.kv.BoolRef.slot()


class Todos(nu.Shape):
    entries = nustd.kv.DictRef.slot(Todo)


class Entry(nustd.ui.Row):
    done = nustd.ui.CheckboxRef.slot()
    text = nustd.ui.TextRef.slot()
    drop = nustd.ui.ButtonRef.slot(icon="trash-2", tooltip="Delete", variant="ghost")


class AddBar(nustd.ui.Row):
    text = nustd.ui.InputRef.slot(placeholder="What needs doing?")
    add = nustd.ui.ButtonRef.slot(label="Add", icon="plus")


class Home(nustd.ui.Page):
    bar = AddBar.slot(gap=2)
    left = nustd.ui.TextRef.slot()
    rows = nustd.ui.Column.slot(Entry, gap=1)


class App(nustd.ui.Index):
    home = Home.slot("/")


h = App.home


@nu.host
def new_id():
    """Minted per click; ids that sort by time keep rows in the order they were added."""
    return f"t{time.time_ns():020d}"


def add(typed):
    todo = nu.Dict.of(text=typed, done=False)
    return nu.IfDo(nu.Str(typed) != "", Todos.entries[new_id()].set(todo) >> h.bar.text.set(""))


def row(key):
    """One live arm per todo: draw the row, keep it in step, handle its clicks, erase it when cancelled."""
    one, todo = h.rows[key], Todos.entries[key]
    draw = nu.IfDo(Todos.entries.contains(key), one.done.set(todo.done) >> one.text.set(todo.text))
    return nu.TryCatch(
        one.drop.set_label("")
        >> nu.ParallelAsync(
            nu.ReconcileReactive(todo.on_change(), draw),
            nu.ReactForever(one.done.on_change(), todo.done.set(nu.Bool(one.done))),
            nu.ReactForever(one.drop.on_click(), Todos.entries.del_item(key)),
        ),
        finally_=one.erase(),
    )


left = nu.Count(nu.Filter(nu.Iter(Todos.entries.values()), lambda t: nu.Bool(t["done"]).not_()))

ui = nu.ParallelAsync(
    nu.ReactForever(h.bar.add.on_click(), nu.let(nu.Str(h.bar.text).strip(), add)),
    nu.ReconcileReactive(Todos.entries.on_change(), h.left.set(nu.str(left) + " left")),
    nu.ForEachParReactive(nu.list(Todos.entries.keys()), Todos.entries.on_children_change(), row),
)


def out():
    return nu.With(
        nustd.kv.rocksdb_navigator(".todos"),
        body=nustd.ui.serve(App, nustd.kv.auto_flow_atomic(ui)),
    )


if __name__ == "__main__":
    asyncio.run(nu.arun(out()))
```

- `ForEachParReactive(items, change, row)` keeps one arm per key. It reads `items` after subscribing, on every change and on re-checks: a new key starts an arm, a gone key cancels its arm, every other arm keeps running untouched. Its change is `on_children_change()`, which fires when a key is added or removed and not on a field write (which change fires on what: nustd/kv).
- `nu.list(Todos.entries.keys())`: the key list leaves its bracket to reach the arms, so it must be plain. A bare `.keys()` fails with `StorageClosedError` (nustd/kv).
- Each arm writes its row, keeps it in step with `todo.on_change()` (any write under that entry), and handles that row's events. Re-check passes rewrite the same values; nothing is erased, so nothing flickers.
- `nu.TryCatch(arm, finally_=one.erase())`: a cancelled arm erases its own row. A delete in one tab writes the store; every tab's `ForEachParReactive` sees the key gone and cancels that row's arm, which erases the row in that tab.
- The `IfDo(contains(key), ...)` guard skips the draw when a pass lands between the delete and the cancel.
- Clicks write the store, never the rows. The toggle stores what the checkbox now shows (`nu.Bool(one.done)`), so a second tab clicking at once lands the same value.
- Rows appear in the order first written, and a kv dict lists its keys sorted, not in insertion order. Mint keys that sort by creation time (`new_id`) or rows come up shuffled; ids are in nustd/kv.
- A subscription belongs to an address, not to a node. `one.drop.on_click()` matches clicks by the Ref's path, so it still fires after the row is erased and drawn again at the same id. A node erased and not drawn again has nothing to click.
- `drop.set_label("")` is the button's first write: a keyed child exists only once written (nustd/ui-refs).
