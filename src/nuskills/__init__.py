"""nuskills: tested prompt pieces about Nu and nuspace.

The corpus is plain markdown under ``nuskills/corpus/<group>/<name>.md``. A
piece is named by its path without the suffix, eg ``"nu/crashcourse"``. Each
consumer picks the pieces it needs and decides their order::

    import nuskills

    nuskills.pieces("nu")              # ["nu/crashcourse", ...]
    nuskills.read("nu/crashcourse")    # the markdown, frontmatter stripped
    nuskills.load("nu/crashcourse")    # Piece(id, title, summary, body)
"""

from __future__ import annotations

from importlib import resources
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version
from typing import NamedTuple


try:
    __version__ = _version("nuskills")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"
del _version, PackageNotFoundError


__all__ = ["Piece", "__version__", "load", "pieces", "read"]


_CORPUS = resources.files(__package__).joinpath("corpus")
_SUFFIX = ".md"
_FENCE = "---"


class Piece(NamedTuple):
    """One corpus piece: its id, its optional frontmatter, its markdown body."""

    id: str
    title: str
    summary: str
    body: str


def pieces(group: str | None = None) -> list[str]:
    """Every piece id, sorted, or only those in ``group`` (``"nu"``, ``"nustd"``, ``"nuspace"``).

    Args:
        group: A top level corpus directory. All of them when absent.
    """
    groups = [group] if group else sorted(g.name for g in _CORPUS.iterdir() if g.is_dir())
    found = []
    for name in groups:
        folder = _CORPUS.joinpath(name)
        if not folder.is_dir():
            msg = f"no corpus group {name!r}"
            raise KeyError(msg)
        found += [
            f"{name}/{f.name[: -len(_SUFFIX)]}"
            for f in folder.iterdir()
            if f.name.endswith(_SUFFIX)
        ]
    return sorted(found)


def load(piece_id: str) -> Piece:
    """The piece ``piece_id`` (eg ``"nu/crashcourse"``), frontmatter parsed off its body.

    Args:
        piece_id: ``<group>/<name>``.
    """
    text = _text(piece_id)
    meta, body = _split(text)
    return Piece(piece_id, meta.get("title", ""), meta.get("summary", ""), body)


def read(piece_id: str) -> str:
    """The markdown of ``piece_id``, frontmatter stripped."""
    return load(piece_id).body


def _text(piece_id: str) -> str:
    group, _, name = piece_id.partition("/")
    path = _CORPUS.joinpath(group, name + _SUFFIX)
    if not name or not path.is_file():
        msg = f"no piece {piece_id!r}"
        raise KeyError(msg)
    return path.read_text("utf-8")


def _split(text: str) -> tuple[dict[str, str], str]:
    """``(frontmatter, body)``. Frontmatter is flat ``key: value`` lines between ``---``."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FENCE:
        return {}, text
    for end, line in enumerate(lines[1:], start=1):
        if line.strip() == _FENCE:
            meta = {}
            for entry in lines[1:end]:
                key, sep, value = entry.partition(":")
                if sep and key.strip():
                    meta[key.strip()] = value.strip().strip("\"'")
            return meta, "".join(lines[end + 1 :]).lstrip("\n")
    return {}, text
