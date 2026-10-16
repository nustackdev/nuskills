"""Every fenced block in the corpus, with where it sits and what kind it is.

The info string after the opening fence says what the harness does with a
block::

    ```python            a whole program: built and validated
    ```python run        a whole program: built, validated, and run
    ```python fragment   a piece of one: only parsed by python
    ```text  (any other) not checked

A marker the harness does not know is a failure, not a skip, so a typo
cannot quietly turn a program into prose.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from importlib import resources


__all__ = ["MARKERS", "Block", "blocks", "corpus_files"]


#: The markers a ``python`` fence may carry.
MARKERS = frozenset({"run", "fragment"})

_OPEN = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")


@dataclass(frozen=True)
class Block:
    """One fenced python block: its piece, its line, its markers, its source."""

    piece: str
    line: int
    markers: frozenset[str]
    source: str

    @property
    def id(self) -> str:
        """``<piece>:<line>``, the line of the opening fence, 1 based."""
        return f"{self.piece}:{self.line}"

    @property
    def group(self) -> str:
        """The piece's corpus group: ``nu``, ``nustd``, ``nuspace``."""
        return self.piece.partition("/")[0]


def corpus_files() -> dict[str, str]:
    """``{piece id: raw text}`` for every ``.md`` anywhere under the corpus."""
    root = resources.files("nuskills").joinpath("corpus")
    found: dict[str, str] = {}

    def walk(folder: object, prefix: str) -> None:
        for entry in folder.iterdir():
            if entry.is_dir():
                walk(entry, f"{prefix}{entry.name}/")
            elif entry.name.endswith(".md"):
                found[prefix + entry.name[:-3]] = entry.read_text("utf-8")

    walk(root, "")
    return dict(sorted(found.items()))


def _fenced(text: str) -> list[tuple[int, str, str]]:
    """``(line, info, source)`` for every fenced block in ``text``, CommonMark style."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        opened = _OPEN.match(lines[i])
        if not opened or (opened["fence"][0] == "`" and "`" in opened["info"]):
            i += 1
            continue
        fence, indent = opened["fence"], opened["indent"]
        closing = re.compile(rf"^[ \t]*{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$")
        start = i
        i += 1
        body = []
        while i < len(lines) and not closing.match(lines[i]):
            body.append(lines[i])
            i += 1
        i += 1
        source = textwrap.dedent("\n".join(body)) if indent else "\n".join(body)
        out.append((start + 1, opened["info"].strip(), source + "\n"))
    return out


def blocks() -> list[Block]:
    """Every ``python`` block in the corpus, in piece then line order."""
    found = []
    for piece, text in corpus_files().items():
        for line, info, source in _fenced(text):
            words = info.split()
            if not words or words[0] != "python":
                continue
            found.append(Block(piece, line, frozenset(words[1:]), source))
    return found
