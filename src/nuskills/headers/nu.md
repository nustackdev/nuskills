---
name: nu
description: Build Nu programs in Python with nucore and nustd (import nu, nustd.kv, nustd.ui, nustd.service), from a single term to a served app. Use when code imports nu or nustd, or the task asks for a Nu program or app, a Nu term, Shapes and Refs, a kv-backed store, or a nustd.ui browser app. Not for cells inside a running nuspace (use the nuspace skill).
---

# Building Nu programs

Use this skill to write, fix or review a Nu program: a Python module whose `out()` returns a Nu term, run by `nu.run` / `nu.arun` or served with `nustd.ui.serve`.

Before you write:

- Install: `pip install "nustd[all]"` pulls the kernel (`nucore`, imported as `nu`) and every fabric. Use the project's own environment for everything below.
- The API is whatever the installed version says. Render it with `nu.inspect` (the last section here) rather than guessing a name; the catalogue is not copied into this skill, so it never goes stale.
- Check a program builds before you run it: `nu.validate(nu.compile(out()))` raises on a term that is not a valid Nu program.

The sections after the Reference list are the ground every program stands on. Each reference file goes deeper on one topic; open the one the task needs.
