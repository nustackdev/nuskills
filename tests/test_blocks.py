"""Every fenced python block in the corpus builds against the current stack.

One test per block, id ``<piece>:<line>`` (the opening fence's line), so a
failure names the exact block. To check one piece::

    uv run pytest -k nuspace/model
    uv run pytest -k "nu/crashcourse:42"     # one block

What each fence gets (see README "Fences"):

- ``python``: a whole program. Loaded with ``nu.prog``'s own loader (the
  module runs, ``out`` is called with what it asks for), then
  ``nu.validate(nu.compile(term))``.
- ``python run``: the same, then evaluated with ``nu.arun``. Keep it for
  programs that finish quickly and touch nothing outside memory.
- ``python fragment``: only parsed by python.

Pieces under ``nuspace/`` are cell programs: the block is stored as a cell
on a plane in an in-memory space and loaded the way the kernel loads it, so
``out(plane, cell)`` gets the ids and ``CellState`` lands under the cell. A
``run`` runs inside the cell's ``Here`` frame against that space. Pieces
anywhere else are plain Nu programs: ``out()`` gets nothing.

A string in a block that holds ``def out(`` is the source of another
program (a cell a block adds, a program it loads), and is built the same way.
"""

from __future__ import annotations

import ast
import asyncio

import pytest
from _support import space as sp
from _support.blocks import MARKERS, Block, blocks

import nu
from nu.prog.diagnostics import ConstructionError, Diagnostic
from nu.prog.source import construct


#: How long a ``run`` block may take.
RUN_SECONDS = 10.0

BLOCKS = blocks()


def _embedded(source: str) -> list[str]:
    """Every string literal in ``source`` that is a program of its own."""
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "def out(" in node.value
    ]


def _check(where: str, built: nu.Nu | Diagnostic) -> nu.Nu:
    if isinstance(built, Diagnostic):
        hint = ""
        if "defines no entry point" in built.message:
            hint = "\n(a block without `out` is a fragment: open it with ```python fragment)"
        pytest.fail(f"{where}: {built.message}{hint}\n{built.traceback or ''}", pytrace=False)
    nu.validate(nu.compile(built))
    return built


async def _ran(where: str, running: object) -> None:
    try:
        await asyncio.wait_for(running, RUN_SECONDS)
    except asyncio.TimeoutError:
        pytest.fail(
            f"{where}: still running after {RUN_SECONDS}s; a `run` block must finish "
            "(drop `run` for a program that waits or loops)",
            pytrace=False,
        )


async def _plain(block: Block, source: str, where: str) -> None:
    term = _check(where, construct(source, filename=f"<{where}>"))
    if "run" in block.markers:
        await _ran(where, nu.arun(term))


async def _cell(block: Block, source: str, where: str, cell: str) -> None:
    async for ctx in sp.open_space():
        await sp.add_cell(ctx, source, cell)
        try:
            loaded = await sp.load_cell(ctx, cell)
        except ConstructionError as err:
            loaded = err.diagnostic
        term = _check(where, loaded)
        if "run" in block.markers:
            await _ran(where, sp.run_cell(ctx, term, cell))


@pytest.mark.parametrize("block", BLOCKS, ids=[b.id for b in BLOCKS])
async def test_block_builds(block: Block):
    unknown = block.markers - MARKERS
    assert not unknown, f"unknown fence marker {sorted(unknown)}, known: {sorted(MARKERS)}"
    assert block.markers != MARKERS, "a block is a fragment or it runs, not both"

    if "fragment" in block.markers:
        compile(
            block.source,
            f"<{block.id}>",
            "exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            dont_inherit=True,
        )
        return

    sources = [(block.id, block.source)]
    sources += [(f"{block.id}:str{i}", s) for i, s in enumerate(_embedded(block.source))]
    for i, (where, source) in enumerate(sources):
        if block.group == "nuspace":
            await _cell(block, source, where, f"{sp.CELL}_{i}")
        else:
            await _plain(block, source, where)


def test_the_corpus_has_programs():
    """An empty or unparsed corpus passes every per-block test by having none."""
    assert any(not b.markers & {"fragment"} for b in BLOCKS)
