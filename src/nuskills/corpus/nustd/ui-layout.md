---
title: UI layout
summary: nustd.ui containers: Column, Row, Grid, Line and the chrome boxes, as Shapes or as Refs alone, with keyed children.
---

# UI layout

A container holds open-ended children: whatever you put in it. Fixed parts of one widget (a button's label and icon) are props on a leaf, not children. Every container has its own Ref, and a Shape over it of the same name without `Ref`:

| Shape | Ref | What | Props (`slot()` / `props=`) |
| --- | --- | --- | --- |
| `Column` | `ColumnRef` | children stacked | `gap=4, align, justify, padding` |
| `Row` | `RowRef` | children side by side | `gap=4, align="center", justify, wrap=False, padding, min_width=240` |
| `Grid` | `GridRef` | equal cells, row after row | `columns=0, min_width=240, gap=4, align="stretch", padding` |
| `Line` | `LineRef` | inline runs, like words in a sentence | `align, wrap=True` |
| `Card` | `CardRef` | titled card | `title, subtitle, footer` |
| `Box` | `BoxRef` | plain styled box | `title, padding, border, background, shadow, gap` |
| `Tabs` | `TabsRef` | tab strip, one body per tab | `tabs=[{"id", "label"}], active` |
| `Accordion` | `AccordionRef` | folding sections | `sections=[{"id", "label"}], open=[ids], multi=True` |
| `Collapsible` | `CollapsibleRef` | one titled region that folds | `title, open=False` |
| `Modal` | `ModalRef` | dialog over the page | `open=False, title, dismissible=True` |
| `Sheet` | `SheetRef` | drawer from an edge | `open=False, title, side="right", size="md", dismissible=True` |
| `Form` | `FormRef` | form wrapper | `title, gap, padding, align` |
| `Fieldset` | `FieldsetRef` | grouped fields, a legend | `legend, gap, disabled` |
| `Field` | `FieldRef` | label, exactly one input, help, error | `label, help, error, required` |
| `List` | `ListRef` | bulleted or numbered, any node per item | `items, variant="bullet", start=1` |

`gap` and `padding` are steps on the spacing ladder, `min_width` is px.

## How children display

The parent's layout decides, never the child. The same Badge is a block in a Column, a cell in a Grid and a run of text in a Line.

- **Row**: a child with no width of its own (chart, table, input, card) fills, and the fill children share the free width. Everything else (text, button, badge) keeps its size. With `wrap=True` fill children wrap at `min_width`. There is no per-child width prop.
- **Grid**: every child is one equal cell. `columns=0` fits as many as `min_width` allows; `columns=N` caps a row at N and still stacks on a narrow screen. Use it for stat tiles, galleries, walls of charts.
- **Line**: for the sentence that mixes a value or a control into words (text, link, badge, status dot, keys). Plain text is still a `TextRef`; prose is a `MarkdownRef`.

## Shapes: declare the layout

Subclass a Shape and declare its children as slots. Props go on `.slot(...)` where the Shape is used. Nest Shapes to any depth; a cell of a Grid or a Row can be a Row, a Card or another Grid.

```python
import nu
import nustd.ui


class Tile(nustd.ui.Card):
    stat = nustd.ui.StatRef.slot()
    trend = nustd.ui.Sparkline.slot(height=32)


class Tiles(nustd.ui.Grid):
    users = Tile.slot(title="Users")
    errors = Tile.slot(title="Errors")


class Toolbar(nustd.ui.Row):
    status = nustd.ui.StatusPillRef.slot(tone="ok", label="Live")
    details = nustd.ui.ButtonRef.slot(label="Details", variant="ghost", icon="eye")


class Log(nustd.ui.Collapsible):
    table = nustd.ui.TableRef.slot(columns=["time", "event"], row_key="time", dense=True)


class Details(nustd.ui.Sheet):
    body = nustd.ui.MarkdownRef.slot()
    close = nustd.ui.ButtonRef.slot(label="Close", variant="secondary")


class View(nustd.ui.Column):
    toolbar = Toolbar.slot(gap=2, justify="between")
    tiles = Tiles.slot(columns=2, min_width=160, gap=3)
    log = Log.slot(title="Event log")
    details = Details.slot(title="Details", side="right")


def out():
    v = View
    draw = (
        v.toolbar.status.set("Live", tone="ok")
        >> v.toolbar.details.set("Details", variant="ghost", icon="eye")
        >> v.tiles.users.stat.set("1,204", label="today", trend="up")
        >> v.tiles.users.trend.set([3, 5, 4, 8, 9])
        >> v.tiles.errors.stat.set("3", label="today", trend="down")
        >> v.tiles.errors.trend.set([9, 6, 4, 3, 3])
        >> v.log.table.set_rows([{"time": "09:12", "event": "deploy"}])
        >> v.details.body.set("Two hosts, one region.")
    )
    return draw >> nu.ParallelAsync(
        nu.ReactForever(v.toolbar.details.on_click(), v.details.set(open=True)),
        nu.ReactForever(v.details.close.on_click(), v.details.set(open=False)),
    )
```

- Attribute access walks the slots: `View.tiles.users.stat` is a Ref. Off the class, the address starts at the slot, so `View.toolbar` is `("toolbar",)`; the class name is not part of it.
- Chrome is driven off the bound Ref: `View.log.set_title(...)`, `View.details.set(open=True)`. A class has no mount point, so the same Shape can sit under many parents.
- A container has no `set()`. The exceptions carry one value of their own: `Modal`, `Sheet` and `Collapsible` take `set(open=, title=)` and `set_open(flag)`, and `ListRef` keeps `set(items)` for plain string items. Card has `set_title`, `set_subtitle`, `set_footer`; Grid `set_columns(n)`; Tabs `set_tabs(tabs)` and `set_active(id)`; Field `set_label`, `set_help`, `set_error`.
- `on_change()` on Tabs, Accordion, Collapsible, Modal and Sheet reports what the person did (a tab picked, a section folded, a sheet dismissed). Modal and Sheet stay open until the program writes `open=False`.
- A `Tabs` or `Accordion` body is the child whose id is the tab or section id: declare a slot with that name.
- A `Field` declares exactly one slot (two raise `RuntimeError` at class creation).
- A slot named like a Ref method (`clear`, `items`, `keys`, `values`, `set`) raises `TypeError` at class creation. Pick another name (`wipe`, `entries`).

## Refs alone, and keyed children

Anything a Shape declares can be built from Refs: `parent_ref=` places a child, `props=` carries what `.slot()` would. The id is a term, so a computed id makes one child per item with nothing declared up front.

A container slot can also carry an **item template**: `Grid.slot(Item)` makes `grid[key]` an `Item` under that key, the way `nustd.kv.DictRef.slot(Order)` answers `orders["o1"]` with an Order. Column, Row, Grid, Card, Box, Tabs, Accordion, Collapsible, Modal, Sheet, Form and Fieldset take children by key (a str or a str term); `Line` and `List` by index (an int or an int term, drawn in index order). Declared slots and keyed children mix. Without a template, `ref[key]` raises `TypeError` and says to declare one or use `parent_ref=`.

```python
import nu
import nustd.ui


SPECIES = [
    {"key": "lion", "name": "Lion", "count": "1,240", "iucn": "VU"},
    {"key": "zebra", "name": "Plains zebra", "count": "3,120", "iucn": "NT"},
]


class Meta(nustd.ui.Line):
    iucn = nustd.ui.BadgeRef.slot(variant="warn")
    note = nustd.ui.TextRef.slot()


class SpeciesCard(nustd.ui.Card):
    count = nustd.ui.StatRef.slot(label="counted")
    meta = Meta.slot()


class View(nustd.ui.Column):
    atlas = nustd.ui.Grid.slot(SpeciesCard, min_width=200, gap=3)


def card(s):
    one = View.atlas[nu.Str(s["key"])]
    return (
        one.set_title(s["name"])
        >> one.count.set_value(s["count"])
        >> one.meta.iucn.set_label(s["iucn"])
        >> one.meta.note.set("on the red list")
    )


#: A header built from Refs alone: no Shape, ids and props given here.
head = nustd.ui.RowRef("head", props={"gap": 2})
title = nustd.ui.HeadingRef("title", parent_ref=head)
total = nustd.ui.BadgeRef("total", parent_ref=head)


def out():
    return (
        title.set("Atlas", level=3)
        >> total.set(str(len(SPECIES)), variant="info")
        >> nu.ForEachDo(SPECIES, card)
    )
```

- `nu.ForEachDo(items, lambda item: ...)` draws one child per item at run time; a Python `for` while building works too, for items known then.
- A keyed child exists from its first write (see "A Ref nobody writes is not there" in nustd/ui-refs), and siblings that are not declared on a booted Page appear in the order they were first written.
- `View.atlas[key].erase()` drops one child. Erasing the container and drawing everything again also clears what an earlier pass drew, but redraws every child on every pass. A list that follows a store, with per-row buttons, keeps one arm per row instead: nustd/ui-app.
- Event subscriptions are by address. A child's `on_click()` keeps firing after the child is erased and written again at the same id.
- Ids are unique per parent, not globally: two Cards may each hold a `stat`.
