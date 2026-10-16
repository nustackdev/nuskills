---
title: UI Refs
summary: nustd.ui leaves: writing to a widget, reading it back, reacting to it, and the kit.
---

# UI Refs

`nustd.ui` is a fabric whose store is a browser tab. Each widget is a Ref: writing it draws it, reading an input Ref asks the tab for its live value, `on_click()` / `on_change()` subscribe to what the person does. Every name is flat on `nustd.ui` (`nustd.ui.TextRef`, `nustd.ui.Row`, `nustd.ui.serve`).

The fabric is async-only: a program that touches it runs with `nu.arun`. The Session it draws on is bound by a host: `nustd.ui.serve` for a plain app (see nustd/ui-app), the space for a nuspace cell.

There are two kinds of Ref. A **leaf** draws one thing from its own props and never holds children: building a Ref with `parent_ref=` a leaf raises `TypeError: ButtonRef is a leaf and holds no children`. A **container** (Column, Row, Grid, Card, ...) holds open-ended children; those are in nustd/ui-layout. This piece is the leaves.

## Writing

A Ref is built from an id: `nustd.ui.TextRef("status")`. The id is its address under its parent, so it must be unique among its siblings. It can be a term too, which is how one id per item gets computed (nustd/ui-layout).

- A leaf with one primary value has `set(value, **rest)`: `TextRef.set(text)`, `StatRef.set(value, label=..., delta=..., trend=...)`. Everything it can drive also has its own `set_*` (`set_label`, `set_variant`, ...). `set()` sends only the keyword arguments you pass.
- Arguments are Python values or Nu terms, mixed freely: `.set("ready")`, `.set(nu.str(Counter.n))`.
- A write is a Command: it yields nothing and chains with `>>`.
- `ref.erase()` drops the node and everything under it. The next write brings it back.

**A Ref nobody writes is not there.** A write ships the Ref's whole chain (each level's id, kind and props) and the browser makes any node on that chain that is missing. Nothing else creates a node, with one exception: a served Page draws every slot it declares at boot. A Ref built alone, or a keyed child, or anything in a nuspace cell, exists from its first write. A `ButtonRef` with only `on_click()` is a button nobody can press, and a table meant to fill on the next change is empty until that change. Write every Ref once on the way in.

**Props.** What a Ref looks like before any write (a button's variant, a table's columns) is its props. Declared on a Shape they go in `.slot(**props)`; on a Ref built alone they go in `props=`. Both go through the Ref class's own `slot()`, so the defaults are the same and an unknown prop raises `TypeError` at build time.

```python
import nu
import nustd.ui


page = nustd.ui.ColumnRef("page")
title = nustd.ui.HeadingRef("title", parent_ref=page)
stat = nustd.ui.StatRef("jobs", parent_ref=page, props={"label": "Jobs"})
go = nustd.ui.ButtonRef("go", parent_ref=page, props={"variant": "secondary", "icon": "play"})


def out():
    return (
        title.set("Queue", level=2)
        >> stat.set("12", delta="+3", trend="up")
        >> go.set_label("Run all")
    )
```

## Reading and reacting

Input Refs belong to the tab: the person changes the value, the program reads it.

- Read the live value by wrapping the Ref in a form: `nu.Str(name)` for text, select, radio and date; `nu.Bool(flag)` for checkbox, switch and toggle; `nu.float(slider)` for slider and number input; `nu.List(tags)` for tag input. Each read is a round trip to the tab, made when the term evaluates.
- `button.on_click()` and `input.on_change()` are subscriptions. `nu.ReactForever(sub, body)` runs `body` once per event, forever. `body` is a term, or a lambda over the event payload (`lambda ev: ... ev["key"] ...`).
- A Ref with several kinds of event names them: `TableRef.on_edit()` gives `{key, row_index, column, value, previous}`, `on_row_click()` gives `{row_index, key}`, `on_select()` gives `{keys, row_indexes}`. Each needs its prop (`editable=True`, `clickable_rows=True`, `selection="single"`).
- Two reactions that each run forever are two arms of `nu.ParallelAsync`, never `>>` (nu/reactive).

```python
import nu
import nustd.ui


name = nustd.ui.InputRef("name", props={"placeholder": "Your name"})
loud = nustd.ui.SwitchRef("loud", props={"label": "Shout"})
greet = nustd.ui.ButtonRef("greet")
said = nustd.ui.TextRef("said")


def out():
    text = nu.Str("Hello, ") + nu.Str(name)
    shout = nu.IfDo(nu.Bool(loud), said.set(text.upper()), said.set(text))
    return (
        name.set("")
        >> loud.set(False)
        >> greet.set("Greet")
        >> said.set("")
        >> nu.ReactForever(greet.on_click(), nu.IfDo(nu.Str(name) != "", shout))
    )
```

## The kit

Every name is `nustd.ui.<Name>`. Signatures are `set`'s; the `set_*` methods and the `slot()` props carry the same names.

Text and content:

```text
TextRef            set(value)                                  one line of plain text
MarkdownRef        set(value), set_editable(flag)              prose; editable on request, read with nu.Str
HeadingRef         set(label, level=, align=)                  level 1 to 6
CodeRef            set(value), set_language(name), set_editable(flag)
LinkRef            set(href=, label=, target=, external=)
ImageRef           set(src, alt=, fit=, width=, height=, rounded=)
JsonViewerRef      set(value, expand_depth=, ...)              any structure, foldable
ListRef            set(items, variant="bullet"|"number"), append(item), clear()
```

Status and numbers. Tones and variants come from `neutral info ok warn danger`:

```text
AlertRef           set(title, body=, variant=, dismissible=)   on_dismiss()
BadgeRef           set(label, variant=)
StatusPillRef      set(label, tone=)                           icon + label, readable without color
StatusDotRef       set(tone, label=, pulse=)
StatRef            set(value, label=, delta=, trend=)          trend: up | down | flat
ProgressRef        set(value, caption=, indeterminate=)        value 0.0 to 1.0
GaugeRef           set(value, caption=, variant=)
SpinnerRef         set(label), set_size(name)                  busy with no known progress
SkeletonRef        set_lines(n), set_shape(name)               placeholder while loading
EmptyStateRef      set(label, description=)
AvatarRef          set(src, name=, size=)                      image or initials
BreadcrumbRef      set(items)                                  strings or {label, href}
DividerRef         set(label, align=)                          vertical inside a Row
KbdRef, ShortcutRef  set(label) / set(keys)                    key caps
```

Inputs (read and subscribe as above):

```text
ButtonRef          set(label, variant=, disabled=, icon=, tooltip=), on_click()
InputRef           set(value), on_change()                     one line; slot: label, placeholder, type
TextAreaRef        set(value), on_change()                     slot: rows, placeholder
NumberInputRef     set(value, min=, max=, step=, label=)
SliderRef          set(value, min=, max=, step=, label=, show_value=)
SelectRef          set(value), set_options([...]), set_searchable(flag)
RadioGroupRef      set(value), set_options([...])
CheckboxRef        set(flag)          SwitchRef  set(flag)          ToggleRef  set(pressed)
TagInputRef        set([...])
DatePickerRef      set("2026-01-31")
SketchRef          set(elements), clear()                      a drawing pad
```

Button variants are `primary secondary ghost soft danger`; `icon` is a lucide name in kebab case (`plus`, `trash-2`, `refresh-cw`), and an empty label draws an icon button named by `tooltip`. Options are strings or `{"value", "label"}` dicts.

Collections:

- `TableRef`: `slot(columns=[...], row_key=, editable=, selection=, clickable_rows=, dense=, max_rows=, ...)`. Columns are strings or `{key, label, kind, options, editable, width, align}` with `kind` in `text number bool select`. Rows are lists (by column position) or dicts (by key). Write with `set_rows(rows)`, or `set({"columns": ..., "rows": ...})` to change both in one frame; one row at a time with `append(row)`, `set_row(key, row)`, `insert_row(i, row)`, `remove_rows(keys)`. The table never edits itself: an edit, add or delete arrives as an event and the program writes the rows back.
- `TreeRef`: a foldable tree. `set(nodes)` with nodes `{key, parent, label, icon?, badge?}`, flat; `on_select()`, `on_open()`, `on_rename()`, `on_move()`.

### Charts

`nustd.ui.Chart` is the chart: one browser node that draws whatever ECharts option it holds. Every series type, axis, component and setting ECharts has is reachable through it. `Chart.slot(option={...}, height=256, max_points=500)` declares one with its option, given as a plain dict exactly as ECharts takes it; a Chart built alone takes the same in `props={"option": ...}`.

Every chart has the same writes, defined once on `Chart`:

- `set(option={...})` replaces the whole option and draws it from scratch.
- `merge({...})` sends a partial option, merged the way ECharts' `setOption` merges: objects key by key, a list of series item by item (same `id`, else same `name`, else position). Use it to change data, an axis or a style live.
- `set(data)` replaces series data only: a list is the first series' data, a mapping `{series name: data}` fills those series and empties every declared series it leaves out. To change one series alone, `merge` it.
- `append(points, series=0)` pushes points onto one series (by position or name), keeping the newest `max_points`; `clear(series=None)` empties one or all.
- `on_click()` gives `{event, series, series_index, name, index, value}` for a data item clicked.

The typed charts are conveniences over `Chart`, not other widgets: each is a Python builder whose `slot()` turns a few settings into an option and whose `set(data)` takes the data in a friendlier shape, and each draws on the same browser node. `LineChart`, `AreaChart`, `BarChart`, `ScatterChart`, `Histogram`, `CandlestickChart`, `BoxplotChart`, `HeatmapChart`, `PieChart`, `FunnelChart`, `TreemapChart`, `SunburstChart`, `SankeyChart`, `RadarChart`, `GaugeChart`, `Sparkline`. Settings go on the slot (`LineChart.slot(["cpu", "mem"], title=, x_type="time", y_format="{value} ms", height=)`). `LineChart.set` takes `{series: [[x, y], ...]}` or `[[x, y], ...]` for the first series; `PieChart.set` takes `[[name, value], ...]` or `{name: value}`; `Sparkline.set` takes bare y values. Whatever a builder does not expose (a log axis, a second y axis, mark lines) goes in its `option=`, merged over what it builds, or later through `merge`. Reach for `Chart` itself when no builder fits or the option is already written.

```python
import nu
import nustd.ui


#: Any ECharts option, as ECharts takes it: here bars and a line on two y axes.
MIX = {
    "tooltip": {"trigger": "axis"},
    "legend": {},
    "xAxis": {"type": "category", "data": ["Mon", "Tue", "Wed"]},
    "yAxis": [{"type": "value", "name": "jobs"}, {"type": "value", "name": "ms"}],
    "series": [
        {"name": "jobs", "type": "bar", "data": [12, 30, 18]},
        {"name": "latency", "type": "line", "yAxisIndex": 1, "data": [80, 120, 95]},
    ],
}


class View(nustd.ui.Column):
    mix = nustd.ui.Chart.slot(option=MIX, height=280)
    cpu = nustd.ui.LineChart.slot(
        ["cpu"], title="CPU", x_type="time", y_format="{value} %", option={"yAxis": {"max": 100}}
    )


def out():
    return (
        View.mix.merge({"series": [{"name": "latency", "data": [70, 110, 90]}]})
        >> View.mix.set({"jobs": [14, 28, 20]})
        >> View.cpu.set([[1760000000000, 41], [1760000060000, 47]])
        >> View.cpu.append([[1760000120000, 52]], "cpu")
        >> View.cpu.merge({"yAxis": {"min": 0}})
        >> View.mix.set(option={**MIX, "series": MIX["series"][:1]})
    )
```

Formatters are ECharts template strings (`"{value} ms"`, `"{b}: {d}%"`, `"{HH}:{mm}"` on a time axis), never code. A color may be a kit token, `"var(--chart-3)"`, resolved per theme.

`nu.inspect.Inspect("nustd.ui")` lists every name; `Inspect("nustd.ui.TableRef")` gives one in full.
