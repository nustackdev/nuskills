<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->

# Services

A `nu.Service` class declares endpoints over a plain Python object: a client, a cache, a model, a device. Each endpoint is a method Ref. Calling it with kwargs builds an interaction; nothing reaches the object until the program runs inside a bracket that binds it. This is how Python with effects enters a Nu program: as a fabric with declared effects, not hidden calls.

```python run
import nu
import nustd


class Mailer:
    """Any Python object: here a stub that records what it sends."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def render(self, name: str, greeting: str) -> str:
        return f"{greeting}, {name}!"

    def send(self, to: str, body: str) -> int:
        self.sent.append(f"{to}: {body}")
        return len(self.sent)

    def flush(self) -> None:
        self.sent.clear()

    def outbox(self):
        yield from self.sent


class Mail(nu.Service):
    render = nustd.service.QueryRef.method(greeting="Hello")  # pure: yields, mutates nothing
    send = nustd.service.ActionRef.method()  # mutates the object and yields
    clear = nustd.service.CommandRef.method(name="flush")  # mutates, yields nothing
    outbox = nustd.service.StreamQueryRef.method()  # a generator: yields a stream


class Run(nu.Shape):
    sent = nu.IntRef.slot()
    log = nu.ListRef.slot(str)


program = (
    Mail.clear()
    >> Run.sent.set(Mail.send(to="ada", body=Mail.render(name="Ada")))
    >> Run.sent.set(Mail.send(to="bo", body=Mail.render(name="Bo", greeting="Hi")))
    >> Run.log.set(nu.Collect(Mail.outbox()))
)


def out():
    return nu.With(
        nustd.service.bind(Mail, target=Mailer()),
        nu.Provide(dict, {}),
        body=program,
    )
```

After the run `Run.sent` is `2` and `Run.log` is `['ada: Hello, Ada!', 'bo: Hi, Bo!']`.

## Pick the Ref by effect

| Ref | Kind | The method |
| --- | --- | --- |
| `QueryRef` | ScalarQuery | returns a value, changes nothing |
| `ActionRef` | ScalarAction | changes the object and returns a value |
| `CommandRef` | Command | changes the object; any return value is dropped |
| `StreamQueryRef` | StreamQuery | returns an iterable or generator, changes nothing |
| `StreamActionRef` | StreamAction | yields items and changes the object while doing so |

The kind is a declaration, not something read off the object, and the effect analysis trusts it. Declaring a mutating method as `QueryRef` is the common error: brackets, retries and ordering then treat a write as a read. When the value of a mutating call matters, use `ActionRef`; when it does not, `CommandRef`.

The kind also decides where a call may sit, by the usual composition rules:

- A `CommandRef` call yields nothing, so it may stand in a `>>` chain but not in a value slot: `Run.sent.set(Mail.clear())` fails validation with `scalar_command cannot hold scalar_command`.
- A `QueryRef` call yields a value nobody consumes when placed bare in a `>>` chain, which validation refuses (`flow_body_is_mutator`). Sink it: `Run.sent.set(Mail.render(name="Ada"))`.
- An `ActionRef` call is both, so it may stand alone in a chain or feed a slot.
- A stream needs a reduction to become one value: `nu.Collect(...)`, `nu.Sum(...)`, `nu.First(...)`, or a loop (`nu.ForEachDo(Mail.outbox(), lambda line: ...)`).

## Declaring and calling

- `<Ref>.method(name=None, **defaults)`. `name=` picks the attribute on the target when it differs from the slot name (`clear` calls `flush`). `**defaults` are kwargs baked into the endpoint; a kwarg at the call site overrides one (`greeting="Hi"` above).
- Calls take kwargs only. Each value may be a plain value or any Nu term (a Ref, another call, an arithmetic term), evaluated when the call runs.
- The Service class is never instantiated, and neither is anything on it. The target object is.
- The attribute is looked up on the target when the call runs, so a misspelled method fails at run time with `AttributeError`, not at build time.
- An `async def` method works under `nu.arun`. Under `nu.run` it raises `RuntimeError: Service scalar '<name>' returned an awaitable under nu.run; use nu.arun`.

## Binding

`nustd.service.bind(Mail, target=obj)` returns a `Provide` tagged by the Service class, with no body. Put it in a `nu.With(..., body=...)` head next to the other brackets the body needs. Calls outside it raise `LookupError: No binding for: ServiceFabric[Mail]`.

- The tag is the class, so several Services over several objects live side by side in one program, and two Services never see each other's target.
- The target is captured at bind time and lives as long as the caller keeps it. The fabric opens and closes nothing around it.
- Swapping the target swaps the world: a stub in tests, the real client in production, one program.

Other fabrics reuse the same declaration shape with their own Refs and bind helpers: `nustd.http` (`GETRef.method("/repos/{owner}/{name}")`, `nustd.http.bind(Svc, base_url=...)`) and `nustd.llm` (`ChatRef.method(...)`, `nustd.llm.ollama(Svc, model=...)`, `nustd.llm.openai(...)`). Render their modules with `nu.inspect` before using them.
