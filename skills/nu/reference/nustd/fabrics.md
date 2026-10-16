<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Fabrics

A Ref is resolvable only through the fabric that owns its address. Each fabric ships its own Ref types, so a slot picks its fabric by the Ref it is declared with: `nu.IntRef` lives in a Python dict, `nustd.kv.IntRef` in a key-value store, `nustd.ui.InputRef` in a browser. The program around the slot does not change.

Only `nu.mem` ships with the kernel. Every other fabric, and the standard library, is in `nustd`, a separate distribution and a separate import. A module that declares or calls anything under `nustd` needs `import nustd` beside `import nu`. The fabrics load on first attribute access, so `import nustd` stays cheap.

```python run
import nu
import nustd


class Greeter:
    def hello(self, name: str) -> str:
        return f"hello, {name}"


class Greet(nu.Service):
    hello = nustd.service.QueryRef.method()


class Visit(nu.Shape):  # nu.mem: a plain dict
    id = nu.StrRef.slot()
    at = nu.StrRef.slot()
    said = nu.StrRef.slot()


class Seen(nu.Shape):  # nustd.kv: transactional storage
    count = nustd.kv.IntRef.slot()


program = (
    Visit.id.set(nu.str(nustd.uuid.uuid4()))
    >> Visit.at.set(nustd.datetime.datetime.now().isoformat())
    >> Visit.said.set(Greet.hello(name="ada"))
    >> nustd.kv.Transaction(Seen.count.init(0) >> Seen.count.inc(), scope=Seen)
)


def out():
    # One head binds every fabric the body touches; the order is the nesting order.
    return nu.With(
        nu.Provide(dict, {}),
        nustd.kv.memory_navigator(),
        nustd.service.bind(Greet, target=Greeter()),
        body=program,
    )
```

## The map

| Fabric | What a Ref addresses | Bind with |
| --- | --- | --- |
| `nu.mem` (Refs flat on `nu`: `nu.IntRef`, `nu.ListRef`, `nu.DictRef`, `nu.ShapeRef`, ...) | a key path in a plain Python dict, in process | `nu.Provide(dict, initial, body)`, `nu.Context().bind(dict, d)`, or `nu.let` / `nu.Frame` for scratch |
| `nustd.kv` | a key in transactional storage: memory, RocksDB, LMDB, SQLite, text; change notifications | `nustd.kv.memory_navigator()`, `nustd.kv.rocksdb_navigator(path)`, ... plus `Snapshot`/`Transaction` around each access |
| `nustd.service` | a method on a plain Python object | `nustd.service.bind(Svc, target=obj)` |
| `nustd.http` | an http endpoint, declared on a Service | `nustd.http.bind(Svc, base_url=...)` |
| `nustd.llm` | an OpenAI-compatible chat endpoint (ollama, openai, openrouter, groq, cerebras, vllm, xai) | `nustd.llm.ollama(Svc, model=...)`, `nustd.llm.openai(...)`, `nustd.llm.bind(...)` |
| `nustd.ui` | a widget or container in a served page | `nustd.ui.serve(index, program)` |
| `nustd.mp`, `nustd.mp_pool` | a worker process that runs a Nu term (`Teleport`) | `Provide(MpWorker, ...)`, `nustd.mp_pool.WorkerPool` |
| `nustd.cluster` | a Ray actor that runs a Nu term (needs the ray extra) | `Provide(RayCluster, ...)` with `RayService` |
| `nustd.proxy` | another fabric, over the wire | `InvisiblesServer` / `InvisiblesProxy` |
| `nustd.cc` | a Claude Code session | `nustd.cc.bind(...)` |

Beside the fabrics, `nustd` mirrors Python's standard library module by module as pure Nu terms that need no binding: `nustd.uuid.uuid4()`, `nustd.datetime.datetime.now()`, `nustd.math.sqrt(x)`, `nustd.pathlib`, `nustd.decimal`, `nustd.random` and the rest. Call them like the stdlib; each call is an atom evaluated when the program runs, not at construct time. `nustd.logging` is the logging mirror: `nustd.logging.getLogger(name).info("msg %s", value)` builds a Command.

## Binding

- Nothing in a program reaches a fabric that was not provided around it. A Ref with no binding raises `LookupError: No binding for: ...` naming the fabric and the Shape (`dict[Visit]`, `SnapshotProtocol[Seen]`, `ServiceFabric[Greet]`).
- Every fabric helper returns a `Provide` or a `With`. Stack them in one `nu.With(a, b, c, body=...)` head: each later bracket nests inside the earlier ones and sees their bindings, and they close in reverse. A fabric another depends on goes first. Your own preset is a function returning a `With` or `Provide`.
- `nu.mem` addresses by slot path, so two Shapes sharing a slot name collide under one untagged dict. Bind a dict per Shape (`nu.Provide(dict, {}, body, tag=Visit)`) to keep them apart.
- Keep the binding out of reusable code: a function returns the raw term, and the app's top level wraps it once in the `With` that names the real backends ([nu/composition](../../SKILL.md#composition)).

Before writing against any fabric, render it: `nu.inspect.render("nustd.kv")` lists every Ref and Interaction it ships, and each Ref's record lists its verbs.
