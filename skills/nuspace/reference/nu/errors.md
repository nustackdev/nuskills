<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Errors

## EMPTY

A slot never written reads as the `EMPTY` sentinel, and so does an attr nothing bound. It is not `None` and not an exception. It spreads: arithmetic, concatenation and most Queries over an `EMPTY` operand yield `EMPTY`. Writes refuse it:

- `.set(x)` where `x` is `EMPTY` raises `ValueError: cannot store EMPTY`.
- `.append(...)` and other writes that combine an `EMPTY` operand raise `ValueError: cannot write with an EMPTY operand`.

So `Cart.total.set(Cart.total + 1)` on a fresh store fails with `cannot store EMPTY`, and `Cart.goods.append("x")` on an unset list fails with `cannot write with an EMPTY operand`. Seed or guard:

```python run
import nu


class Cart(nu.Shape):
    total = nu.IntRef.slot()
    goods = nu.ListRef.slot(str)


seeded = Cart.goods.init([]) >> Cart.goods.append("book")
guarded = nu.IfDo(Cart.goods.exists(), Cart.goods.append("pen"))
defaulted = Cart.total.set(Cart.total.fallback(0) + 1)


def out():
    return nu.Provide(dict, {}, seeded >> guarded >> defaulted)
```

- `.init(v)` writes only when the slot is missing: the usual seed step at the start of a program.
- `.exists()`, `.missing()`, `.is_empty()`, `.not_empty()` test for it and always yield a plain bool.
- `x.fallback(a, b)` (the atom `nu.Fallback`) yields the first operand that is not `EMPTY`. It checks presence, not truthiness: `0` and `""` are kept.
- `IfDo`, `WhileDo` and `.filter` treat an `EMPTY` condition as false.

## When errors surface

Constructing a term never fails on composition. `nu.run` and `nu.arun` compile and validate first, then evaluate, so errors arrive in this order:

| Error | When | Meaning |
| --- | --- | --- |
| `TypeError` | construct time, in your module | Python on a term (`if term`, `len(term)`), a slot named like a Ref method |
| `ValidationError` | run, before any effect | the program breaks a law |
| `RuntimeError: eval: program contains an async-only atom (...)` | `nu.run`, before any effect | the program needs `nu.arun` |
| `LookupError: No binding for: dict[Cart]` | run, at the first Ref | no fabric for that Ref was provided around it |
| `ValueError: cannot store EMPTY` and friends | run | a write met `EMPTY` |
| anything a fabric or host function raises | run | real failure, handle it in the program |

`ValidationError` subclasses `ValueError` and lists every broken law with where it broke:

```text
ValidationError: invalid program:
  [flow_body_is_mutator] a Flow body slot is not a mutating child: scalar_query
      at Sequential  path=(0,)  chain=Provide > Sequential
```

The laws:

| Law | Cause |
| --- | --- |
| `composition` | a child kind its parent cannot hold, e.g. a Command inside a Query |
| `flow_body_is_mutator` | a Ref or Query as a step in `>>`, a branch or a loop body |
| `control_param_is_yielder` | a Command in a `cond`, `items` or other parameter slot |
| `ref_slots` | a Command whose target is not a Ref |
| `scalar_stream_refused` | a stream where one value is wanted; drain it first (`.to_list()`, `.first()`) |
| `reduction_takes_stream` | a Reduction over a plain list; open it with `.iter()` |
| `async_atom_needs_loop` | an async-only atom off the event loop |
| `program_mutates` | warning only: the program writes nothing |

`LookupError` also appears when a Shape is read outside the `nu.Frame` that binds it, and from fabrics whose binding is missing (`nustd.kv`, a Service). The fix is a bracket around the body, not a change to the Ref.

## Handling failures in the program

Failures that belong to the program are handled by Spans in the program. Spans are transparent, so a guarded Query still yields and a guarded Command still writes.

```python run
import nu


class Job(nu.Shape):
    result = nu.FloatRef.slot()
    note = nu.StrRef.slot()
    log = nu.ListRef.slot(str)


risky = Job.result.set(nu.Int(1) / 0)

guarded = nu.TryCatch(
    risky,
    catch=lambda err: Job.note.set("failed: " + err),
    finally_=Job.log.append("tried"),
    errors=ZeroDivisionError,
)

retried = nu.Retry(
    risky,
    max_attempts=3,
    delay=0.01,
    backoff=2.0,
    jitter=0.1,
    on_attempt_fail=lambda err, attempt: Job.log.append("attempt " + nu.str(attempt)),
    on_fail=lambda err, attempt: Job.note.set("gave up: " + err),
)


def out():
    return nu.Provide(dict, {"log": []}, guarded >> retried)
```

- `nu.TryCatch(body, catch=None, finally_=None, errors=None)`. `catch` runs in place of the body on a matching error: a term, a lambda over the error, or a term reading `nu.Attr("error")`. Around a value, `catch` is the fallback value: `Job.result.set(nu.TryCatch(nu.Int(1) / 0, catch=0.0))`. `errors=` narrows which exception types it catches; anything else propagates. `finally_` runs either way and never stops the error.
- `nu.Retry(body, max_attempts=3, ...)` re-runs the body on failure. Under `nu.run` it is a bare retry (`max_attempts`, `errors` only). Under `nu.arun` it adds `delay`, `backoff`, `jitter` and the hooks `on_attempt_fail(err, attempt)`, `on_success(attempt)`, `on_fail(err, attempt)`. Without `on_fail` the last error re-raises. Use jitter when many workers retry the same thing.
- Retry is for failed attempts, not for waiting until something becomes true; that is a reactive wait ([`nu/reactive`](../../reference/nu/reactive.md)).
- `nu.Timeout(seconds, body, on_timeout=None)` bounds a body by wall-clock time, async only. Without `on_timeout` it raises `TimeoutError`.
- `nu.raise_(ValueError, msg)` raises from inside the program; gate it with `IfDo`: `nu.IfDo(Cart.total > 100, nu.raise_(ValueError, "too big: " + nu.str(Cart.total)))`.
- **`nu.Noop()` swallows nothing.** In `catch`, `on_timeout` and `on_fail`, a `Noop` counts as absent, so `TryCatch(body, catch=nu.Noop())` re-raises and `Timeout(s, body, on_timeout=nu.Noop())` still raises `TimeoutError`. Swallowing says what happened: `catch=Log.lines.append("skipped")`, `on_timeout=Job.note.set("late")`, `catch=nu.print("skipped")`, or a fallback value around a Query.
- Do not wrap `nu.run(...)` in a Python `try` as the app's error handling. The run aborts at the first unhandled error, after whatever writes already landed; put the policy in the program where it can retry, fall back or record.
