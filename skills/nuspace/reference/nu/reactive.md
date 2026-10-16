<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Reactive Flows

A reactive Flow binds a change subscription once and runs a body against it. The subscription comes from a Ref whose fabric publishes changes:

- `ref.on_change()` on a `nustd.kv` slot (leaf or container) and on a `nustd.ui` widget value.
- `ref.on_children_change()` and `ref.on_descendants_change(*pattern)` on kv containers, for "a key under here moved". Which one fires on a field written inside an entry: [nustd/kv](../../reference/nustd/kv.md).
- `button.on_click()`, `table.on_row_click()` and the other ui events.

`nu.mem` Refs publish nothing and have no `on_change` (`AttributeError`). State something must react to lives in kv or in the ui.

Every reactive Flow is async-only: run the program with `nu.arun`.

## Two kinds

**Event** Flows hand the body the key that changed and run on real notifications only. Delivery is at most once, so they are for reacting to what happened: a click, a submitted form, a message.

| Flow | Runs the body |
| --- | --- |
| `nu.React(change, body)` | once, on the first notification, then returns |
| `nu.ReactWhile(change, cond, body)` | on each notification while `cond` (read after it) holds |
| `nu.ReactForever(change, body)` | on every notification, never returns |
| `nu.ReactLatest(change, body)` | on every notification, cancelling the run still going |

The body is a term, or a lambda over the changed key: `nu.ReactForever(Box.ok.on_click(), lambda key: ...)`.

**Level** Flows give the body no key. The body reads the state as it is now and makes things right, so running it twice with nothing changed does nothing new. The flow runs it right after subscribing, on every change, and again on a re-check schedule (`after=`, `every=`), so a notification that went missing makes the body late, never wrong. Changes landing during a pass merge into one more pass.

| Flow | Does |
| --- | --- |
| `nu.ReconcileReactive(change, body)` | keeps derived state or a view in step with the store, forever |
| `nu.WaitReactive(change, cond)` | returns once `cond` reads true; returns at once if it already does |
| `nu.ForEachParReactive(items, change, body)` | one live arm per element of `items`, started and cancelled as the set changes |

Pick by what the body needs. Mirroring state (a table that shows the store, a total that follows its parts) is level: `ReconcileReactive`. Waiting for the store to reach a point is level: `WaitReactive`. Handling a click is event: `ReactForever`. A list whose rows each carry their own handlers is level too: `ForEachParReactive`, one arm per row ([nustd/ui-app](../../reference/nustd/ui-app.md)).

```python run
import nu
import nustd


class Job(nu.Shape):
    done = nustd.kv.IntRef.slot()
    shown = nustd.kv.StrRef.slot()


# Five steps of work, one write each.
work = nu.ForRangeDo(0, 5, lambda i: nu.Delay(0.01) >> Job.done.set(i + 1))

# Level: whatever the count is now, the label says so.
label = nu.ReconcileReactive(Job.done.on_change(), Job.shown.set(nu.str(Job.done) + " of 5"))

# Level: returns once the store reaches 5, however many notifications that took.
finished = nu.WaitReactive(Job.done.on_change(), Job.done >= 5)

program = Job.done.set(0) >> nu.Race(label, nu.ParallelAsync(work, finished))


def out():
    return nu.With(nustd.kv.memory_navigator(), body=nustd.kv.auto_flow_atomic(program))
```

## Composing forever things

- Two Flows that both run forever are two arms of `nu.ParallelAsync(a, b)`, never `a >> b`: sequenced, `b` never starts.
- `nu.ParallelAsync` returns when every arm has. `nu.Race(a, b)` returns when the first arm does and cancels the rest, which is how a forever arm (`label` above) is bounded by a finite one.
- The usual app shape is seed, then hydrate, then the arms: `seed >> hydrate >> nu.ParallelAsync(on_add, on_delete, keep_table)`.

## Brackets

On kv, opening a subscription reads the store, so the subscription needs a snapshot around it and the body its own `Snapshot` or `Transaction`. `nustd.kv.auto_flow_atomic(term)` places all of them (as above); by hand: `nu.WaitReactive(nustd.kv.Snapshot(Job.done.on_change()), nustd.kv.Snapshot(Job.done >= 5))`. Never hold one bracket around a whole forever Flow ([nustd/kv](../../reference/nustd/kv.md)).

## Do not poll

- No `nu.ForeverDo(read >> nu.Delay(n))` loop to refresh a view: use `ReconcileReactive` on the slot's `on_change()`.
- No `nu.WhileDo(cond.not_(), nu.Delay(n))` to wait for the store: use `WaitReactive`.
- No `nu.Retry(..., max_attempts=huge)` as a wait. Retry is for attempts that failed, not for state that has not arrived.
- A level body that writes into what it watches wakes itself once more; that pass must find nothing to do. A body that always writes something new loops forever.
- Bursts: `nu.Debounce(delay, body, pending=ref)` runs only the last call in a burst, `nu.Throttle(interval, body, last=ref)` drops runs closer than `interval`. Both keep their state in a mem ref, so put the `nu.let` or `nu.Frame` that holds it around the reaction, not inside it.
