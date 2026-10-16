"""Shared fixtures: an in-memory space for nuspace blocks to be stored and run in."""

from __future__ import annotations

import pytest_asyncio
from _support.space import open_space


@pytest_asyncio.fixture
async def space():
    """A ctx with an empty in-memory Space and States store and one plane, ``PLANE``."""
    async for ctx in open_space():
        yield ctx
