"""An in-memory space, and a cell's program loaded the way the kernel loads it.

A nuspace piece's program is stored as a real cell on a real plane, then
read back through ``Space.cells[cell].prog.load`` with the kernel's
``Reroot(plane, cell)`` rewrite. So ``out(plane, cell)`` is bound exactly as
in a running space: ``plane`` and ``cell`` are the ids, plain ``str``, and
``CellState`` / ``PlaneState`` chains land under them. Running it wraps it in
the ``ops.Here`` frame, as the kernel's body does.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.shapes import Reroot, Space, States


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable


__all__ = ["CELL", "PLANE", "add_cell", "load_cell", "open_space", "run_cell"]


#: The plane and cell every nuspace block runs as.
PLANE = "p_skill"
CELL = "c_skill"


class _Hold(ScalarQuery):
    """Hands the ctx it runs in to ``opened``, then waits for ``done``.

    Inside ``nu.With`` of the two navigators that ctx has both stores bound
    until ``done`` is set, so many terms can run against one in-memory space.
    """

    def __init__(self, opened: asyncio.Future, done: asyncio.Event) -> None:
        super().__init__()
        self._payload = {"opened": opened, "done": done}

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        opened, done = self._payload["opened"], self._payload["done"]

        async def athunk(rt: object) -> object:
            opened.set_result(rt.ctx)
            await done.wait()

        return athunk


async def open_space() -> AsyncIterator[nu.Context]:
    """A ctx with an empty in-memory Space and States store bound, and one async plane."""
    loop = asyncio.get_running_loop()
    opened, done = loop.create_future(), asyncio.Event()
    stores = (
        nustd.kv.memory_navigator(tags=(Space,)),
        nustd.kv.memory_navigator(tags=(States,)),
    )
    held = asyncio.create_task(nu.arun(nu.With(*stores, body=_Hold(opened, done))))
    ctx = await opened
    await nu.arun(ops.add_plane(PLANE, backend="async", name="skill"), ctx)
    try:
        yield ctx
    finally:
        done.set()
        await held


async def add_cell(ctx: nu.Context, source: str, cell: str = CELL) -> None:
    """Store ``source`` as cell ``cell`` on :data:`PLANE`."""
    await nu.arun(ops.add_cell(PLANE, source, cell_id=cell), ctx)


async def load_cell(ctx: nu.Context, cell: str = CELL) -> nu.Nu:
    """The cell's program as the kernel loads it: scope bound, state rerooted."""
    load = Space.cells[cell].prog.load(
        scope={"plane": PLANE, "cell": cell}, rewrite=Reroot(PLANE, cell)
    )
    term, _ = await nu.arun(nustd.kv.Snapshot(load, scope=Space), ctx)
    return term


async def run_cell(ctx: nu.Context, term: nu.Nu, cell: str = CELL) -> object:
    """Run a loaded program inside its ``Here`` frame, the way a cell run does."""
    value, _ = await nu.arun(nu.Frame(ops.Here, term, plane=PLANE, cell=cell), ctx)
    return value
