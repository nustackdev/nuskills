<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Drawing a cell

A cell draws with the same `nustd.ui` Refs a plain app uses ([nustd/ui-refs](../../reference/nustd/ui-refs.md) for leaves and charts, [nustd/ui-layout](../../reference/nustd/ui-layout.md) for containers). The host differs: the space binds the browser, places the drawing, and runs the program again whenever the plane is opened.

## Where a cell draws

- A cell's program names its ui Refs bare: `nustd.ui.MarkdownRef("about")`, or a Shape off its class, `View.table`. The space lands every bare ui chain under the cell's own node on the plane, so ids only need to be unique inside one cell. Two cells can each have a `table`.
- The cell's node is a Column. Refs written at the top level stack in the order they are first written; anything else is laid out by containers, nested as deep as needed. The usual cell declares one `class View(nustd.ui.Column)` with its slots and writes through `View.<slot>`.
- A cell has no boot. Every node, declared or not, appears on its first write, carrying its slot props. Write each Ref once on the way in, even if only with `""`.
- Each run starts by erasing what the last run drew, so a reload or an edit (Cmd+Enter in the cell's editor) redraws from nothing.
- Store Refs are not moved under the cell: `Space.planes[...]` reads the space, and `CellState` / `PlaneState` slots land under this cell and plane ([nuspace/model](../../SKILL.md#the-space-model)).
- `out` gets `plane` and `cell` as plain `str` ids if it asks for them, so they work in f-strings at construct time and as terms.

## The rules

**A cell draws, it never acts on the way in.** Every open tab runs the plane, and the plane runs again each time someone opens it, next week, with nobody asking. So the program writes to the ui and reads from the store, and writes to the store only when a person clicks: a click acts because a person asked for it right then. Mutations go through ops or a `CellState` write in that click's body.

**Bracket every store access.** Nothing brackets a cell for it: wrap what `out` returns in `ops.bracketed(...)`, or bracket by hand, `ops.snapshot(read)` for a read (subscriptions included), `ops.atomic_state(write)` for a `CellState` / `PlaneState` write. Ops bracket themselves. Never hold a bracket across a wait or a loop ([nuspace/brackets](../../SKILL.md#brackets)).

**Follow state, do not poll.** A drawing of the store is a level view: `nu.ReconcileReactive(ops.snapshot(ref.on_change()), draw)` draws right after subscribing, on every change and on re-checks; its body reads what is there now and draws all of it. `nu.ReactForever` is for clicks and other ui events. Never loop over a `Delay` to watch the store ([nu/reactive](../../reference/nu/reactive.md)).

**Two things that go on forever are two arms of `nu.ParallelAsync`**, never `>>`.

**Park when there is nothing left to do.** A cell whose program returns ends its run, and a plane run ends once none of its cells is running. A cell that only draws ends with `nu.ForeverDo(nu.Delay(3600.0))`, which is what `nuspace.system.utils.park()` returns. Cells that follow the store or wait on clicks never return anyway.

**State goes in the store, not the ui.** Whatever must survive a reload or be the same in every tab is `CellState` (this cell) or `PlaneState` (shared by the plane's cells). The ui is redrawn from it.

## A cell that only draws

```python
import nu
import nustd.ui


TEXT = """\
### Reading list

Books we mean to read, and what we thought of the ones we did.
Every block on this page is a small program: open its code to change it.
"""


class Links(nustd.ui.Line):
    lead = nustd.ui.TextRef.slot()
    archive = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    links = Links.slot()


def out(plane):
    return (
        View.about.set(TEXT)
        >> View.links.lead.set("Share this list with a")
        >> View.links.archive.set(href=f"/{plane}", label="link to this page")
        >> nu.ForeverDo(nu.Delay(3600.0))
    )
```

## A live list and an op on click

The pages under this plane, kept in step with the store, and a form that adds one. The add is an op: it brackets itself and commits on its own.

```python
import nu
import nustd.ui
import nuspace
from nuspace import ops


class Add(nustd.ui.Row):
    name = nustd.ui.InputRef.slot(placeholder="Name of the new page")
    add = nustd.ui.ButtonRef.slot(label="Add page", icon="plus")


class View(nustd.ui.Column):
    pages = nustd.ui.TableRef.slot(columns=["name", "id"], row_key="id", label="Pages", dense=True)
    add = Add.slot(gap=2)


@nu.host
def rows(ids, names):
    return [{"id": i, "name": n} for i, n in zip(ids, names)]


def out(plane):
    kids = ops.children(plane)
    names = kids.iter().map(lambda p: ops.plane_title(nu.Str(p))).to_list()
    draw = View.pages.set_rows(ops.snapshot(rows(kids, names)))

    def add(typed):
        made = ops.add_plane(backend="async", name=nu.Str(typed), parent=plane, ui=True)
        return nu.IfDo(typed != "", made >> View.add.name.set(""))

    return (
        View.add.name.set("")
        >> View.add.add.set("Add page", icon="plus")
        >> nu.ParallelAsync(
            nu.ReconcileReactive(ops.snapshot(nuspace.Space.planes[plane].children.on_change()), draw),
            nu.ReactForever(View.add.add.on_click(), nu.let(nu.Str(View.add.name).strip(), add)),
        )
    )
```

- The table is written by its first `ReconcileReactive` pass, right after the subscription opens, so it is never left undrawn.
- `nu.let(value, fn)` reads the input once per click and hands it to `fn`; reading `nu.Str(View.add.name)` twice would be two round trips that can disagree.
- A `@nu.host` function shapes rows in Python at run time. A Python `for` over a store read in `out` would run once, at construct time, over a term.

## State the cell keeps: a keyed list

The cell's notes, kept in `CellState`, so they outlive reloads and are the same in every tab. Each note is a row with its own delete button. One live arm per row, so adding or deleting a note touches only its row; nothing is erased but a row that is gone.

```python
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


class Notes(nuspace.CellState):
    texts = nustd.kv.DictRef.slot(str)


class Note(nustd.ui.Row):
    text = nustd.ui.TextRef.slot()
    drop = nustd.ui.ButtonRef.slot(icon="trash-2", tooltip="Delete", variant="ghost")


class Add(nustd.ui.Row):
    text = nustd.ui.InputRef.slot(placeholder="A note")
    add = nustd.ui.ButtonRef.slot(label="Add", icon="plus")


class View(nustd.ui.Column):
    add = Add.slot(gap=2)
    notes = nustd.ui.Column.slot(Note, gap=1)


@nu.host
def new_id():
    """Minted per click. ops.mint_ordered_id alone runs once, when the module loads."""
    return ops.mint_ordered_id("n")


def add(typed):
    note = nu.Str(typed)
    write = ops.atomic_state(Notes.texts[new_id()].set(note))
    return nu.IfDo(note != "", write >> View.add.text.set(""))


def row(key):
    one = View.notes[key]
    draw = one.text.set(ops.snapshot(Notes.texts[key].fallback("")))
    return nu.TryCatch(
        one.drop.set_label("")
        >> nu.ParallelAsync(
            nu.ReconcileReactive(ops.snapshot(Notes.texts.on_child_change(key)), draw),
            nu.ReactForever(one.drop.on_click(), ops.atomic_state(Notes.texts.del_item(key))),
        ),
        finally_=one.erase(),
    )


def out():
    keys = ops.snapshot(nu.list(Notes.texts.keys()))
    return (
        View.add.text.set("")
        >> View.add.add.set("Add", icon="plus")
        >> nu.ParallelAsync(
            nu.ReactForever(View.add.add.on_click(), nu.let(nu.Str(View.add.text).strip(), add)),
            nu.ForEachParReactive(keys, ops.snapshot(Notes.texts.on_children_change()), row),
        )
    )
```

- `ForEachParReactive(keys, change, row)` keeps one arm per key, read after subscribing, on every change and on re-checks: a new key starts an arm, a gone key cancels its arm, the rest keep running. `on_children_change()` fires when a key is added or removed; which change fires on what is in [nustd/kv](../../reference/nustd/kv.md).
- `ops.snapshot(nu.list(...keys()))`: the keys leave the snapshot to reach the arms, so they are made plain inside it. A bare `.keys()` fails with `StorageClosedError` ([nuspace/brackets](../../SKILL.md#brackets)).
- Each arm writes its row, keeps the text in step with its own key, and handles that row's click. `nu.TryCatch(..., finally_=one.erase())` erases the row when its arm is cancelled, in every tab.
- A click writes the state in its own `ops.atomic_state`, never the rows. Every tab's arms follow the state.
- A dict lists its keys sorted, and rows appear in the order first written, so keys are minted ordered by time, one per click: `ops.mint_ordered_id` inside a `@nu.host` function.
- A subscription belongs to an address, not a node: a row's `on_click()` still fires after the row is erased and drawn again at the same id.
- Swap `CellState` for `PlaneState` and every cell on the plane declaring it shares the list.
- `nuspace.system.utils.redraws(changes, read, draw)` redraws a whole view only when it differs from the last draw ([nuspace/snippets](../../reference/nuspace/snippets.md)); right for a table or a total, not for rows with their own buttons.
