---
title: Looking things up
summary: How to read the API of any Nu module, atom, fabric or app Shape with nu.inspect instead of guessing.
---

# Looking things up

Nu documents itself from its own code. `nu.inspect` reads a module, an atom, a Ref, a method, or a Shape or Service you wrote, and renders it as text: summary, args, notes, what it yields, worked examples, and for a Ref every method it carries. Read the surface before writing against it: a guessed name or argument is the most common way a program fails.

There are two doors to the same text.

**From Python, outside a program:** `nu.inspect.render(path)` returns the text as a `str`, or `""` when the path names nothing it can describe. From a shell, in the project's environment:

```bash
python -c "import nu; print(nu.inspect.render('nustd.kv'))"
```

**Inside a program:** `nu.inspect.Inspect(path)` is a Query atom that yields the same text, or `EMPTY` when the path names nothing. Make it the program's yield; `nu.print` around it only writes to the process's stdout.

```python run
import nu


def out():
    return nu.inspect.Inspect("nu.mem")
```

## Paths

`path` is one dotted string. Resolution imports the longest module prefix and walks the rest.

| Path | Renders |
| --- | --- |
| a module: `nu.mem`, `nustd.kv`, `nu.core.flows`, `myapp.shapes` | its docstring, then one line per Shape, Service, Form, Ref, Interaction and function it holds |
| a flat or qualified subject: `nu.ForEachDo`, `nu.core.flows.WhileDo`, `nustd.kv.Snapshot` | the full record: call form, args, notes, yields, examples |
| a Ref class: `nu.IntRef`, `nustd.kv.DictRef`, `nustd.ui.ButtonRef` | its record plus one line per method and operator it supports |
| a method: `nustd.ui.ButtonRef.set` | its signature and arguments |
| your own Shape or Service: `myapp.shapes.Task` | its prose and one line per slot or endpoint |
| one entry of it: `myapp.shapes.Task.title`, `myapp.shapes.Task.owner.email` | that slot's Ref record, walking nested Shapes |

## How to use it

- **Module first, then exact names.** Render the module (`nustd.kv`, `nustd.service`, `nustd.ui`), take the exact name off its list, then render that subject. Never guess a subject path: a wrong one gives back nothing, and an atom you invent does not exist.
- **Every fabric outside the kernel is under `nustd`.** The kernel and the memory fabric are `nu` (flat names like `nu.IntRef`, `nu.ForEachDo` resolve); everything else (`nustd.kv`, `nustd.service`, `nustd.ui`, `nustd.http`, `nustd.llm`, `nustd.uuid`, ...) needs its `nustd.` path.
- **Ref records list the verbs.** The methods table of a Ref is the authoritative list of what `.set`, `.append`, `.on_change`, `.range` and the operators accept on that slot type. Same-named Refs in different fabrics (`nu.IntRef` and `nustd.kv.IntRef`) carry different surfaces; render the one you declare.
- **Examples are tested.** An example line ending in `-> value` is a doctest that passes against the installed version, so copy its form.
- **The text is whole.** Nothing is truncated; a fabric module runs to several thousand characters. Read it through.
