---
name: nuspace
description: Program a running nuspace: write a cell's prog, read and change planes, cells and state through nuspace.ops, keep CellState and PlaneState, draw a cell with nustd.ui, insert snippets. Use when code imports nuspace or nuspace.ops, or the task is about a space, a plane, a cell or a snippet.
---

# Programming a nuspace

Use this skill to write a cell's program (its prog) or any program that reads and changes a space through `nuspace.ops`. A cell's prog is a Nu program like any other, loaded and bound by the space, so the Nu ground below applies in full.

Before you write:

- Install: `pip install nuspace` (it pulls nucore and the fabrics a space runs on; `nuspace[all]` adds every other fabric). `nuspace run [PATH]` opens a space in the browser; a cell's prog is the source you put in a cell there.
- The API is whatever the installed version says. Render it with `nu.inspect` rather than guessing a name, eg `python -c "import nu; print(nu.inspect.render('nuspace.ops'))"` (module first, then the exact subject; the `nu/inspect` reference file has the rest). The catalogue is not copied into this skill, so it never goes stale.
- Check a prog builds before you store it: `nu.validate(nu.compile(out()))` raises on a term that is not a valid Nu program.
- The space binds its stores and runs the program for you. Never bind them yourself, and bracket every store access (both are below).

The sections after the Reference list are what every cell needs. Each reference file goes deeper on one topic; open the one the task needs (ops before changing structure, drawing before a cell draws or keeps a list of rows).
