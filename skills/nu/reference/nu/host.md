<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Host functions

Some work has no atom: hashing, formatting a timestamp, parsing a string, minting an id. Write it as an ordinary Python function and decorate it with `@nu.host`. The decorator returns a Nu atom class, a `ScalarQuery` by default, named after the function in CamelCase (`slug_of` becomes `SlugOf`). Calling it builds a term; nothing runs until the program runs.

```python run
import time

import nu


@nu.host
def now_ms() -> int:
    return time.time_ns() // 1_000_000


@nu.host
def slug_of(title: str, at: int) -> str:
    return f"{title.lower().replace(' ', '-')}-{at}"


class Post(nu.Shape):
    title = nu.StrRef.slot()
    created = nu.IntRef.slot()
    slug = nu.StrRef.slot()


# One clock read, held for the body: created and slug agree to the millisecond.
publish = Post.title.set("Hello World") >> nu.let(
    now_ms(),
    lambda at: Post.created.set(at) >> Post.slug.set(slug_of(Post.title, at)),
)


def out():
    return nu.Provide(dict, {}, publish)
```

## What the function receives

- Children resolve first, then the function runs on their values. A Ref passed in arrives as the value it holds (`Post.title` arrives as `"Hello World"`), a literal arrives as itself. Positional children land as positional args, keyword children as kwargs.
- The function never sees a Context, a Ref or a term. It cannot read the store on its own or write anything. Reads and writes stay at Refs in the program; the host function only turns values into a value.
- It runs every time its atom is evaluated. There is no caching and no folding, so a clock or an id minter is fresh on each loop turn and each run.
- An `EMPTY` child stops the call and the atom yields `EMPTY` (an unset slot reads `EMPTY`). Writing that on with `.set(...)` raises `ValueError: cannot store EMPTY`. Seed the slot first, or give a default with `nu.Fallback(slug_of(Post.title, 0), "untitled")`. Pass `propagate_sentinels=False` to let `EMPTY` reach the function instead.
- An `async def` becomes an async-only atom: the program must run under `nu.arun`.
- Extra keywords declare attributes on the atom class. There is no purity or caching flag: `@nu.host(deterministic=True)` is accepted and read by nothing.
- A lambda has no usable name, so wrap it with one: `Twice = nu.host(lambda x: x * 2, name="Twice")`.

## Construct time vs eval time

Python at module level, and inside a function that builds a term, runs once, at construct time. Its result is baked in as a literal.

```python fragment
stamp = int(time.time())          # read once, at import
stale = Post.created.set(stamp)   # every run writes that same number
fresh = Post.created.set(now_ms())  # an atom: the clock is read each run
```

The same holds for ids, random draws and anything else that must differ per run: mint them in a host function inside the program, never in Python before it.

## Capture once, derive

Two calls to the same host atom at two places in a program fire at two moments. When several slots need the same eval-time value (a key and its timestamp, a row and its slug), read it once with `nu.let(value, lambda ref: body)`: `value` is evaluated once on entry and the body reads it through the ref, as `publish` does with `at`. Calling `now_ms()` twice would give `created` and `slug` two clocks. `let` and `nu.Frame` are also where per-run scratch belongs ([nu/control](../../reference/nu/control.md)), never Python globals, which every run and every parallel arm shares.

## Effects are not host functions

`@nu.host(base=nu.Command)` builds a Command, but a Command must declare which of its slots it writes, and validation rejects one that declares none (`command_has_write`). A host function only receives values, so it has no Ref to write. When the work is a side effect on a Python object (send, store, reset), expose the object through `nustd.service` and pick `CommandRef` or `ActionRef` for the method. When it is state, it is a Ref.

Do not subclass `ScalarQuery` to reach the runtime Context or to call `nu.run` from inside an atom: that hides reads and writes from the effect analysis. A value is a host function, a read is a Query over Refs, a mutation that also yields is an Action on a fabric.

To format rows, compose a host function into the row expression (`nu.Dict.of(when=fmt_ts(row["ts"]), ...)` inside a `nu.Map`), never pull rows out to Python and loop.
