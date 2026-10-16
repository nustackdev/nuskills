"""Every piece on disk loads through the public loader, with only the frontmatter it may carry."""

from __future__ import annotations

import pytest
from _support.blocks import corpus_files

import nuskills


FILES = corpus_files()
ALLOWED = {"title", "summary"}


def test_every_file_is_a_piece():
    """A file nested too deep, or misnamed, would be in the repo and in no prompt."""
    assert sorted(FILES) == nuskills.pieces()


def test_groups():
    assert {p.partition("/")[0] for p in nuskills.pieces()} <= {"nu", "nustd", "nuspace"}
    for group in ("nu", "nustd", "nuspace"):
        assert all(p.startswith(group + "/") for p in nuskills.pieces(group))


@pytest.mark.parametrize("piece", sorted(FILES))
def test_piece_loads(piece):
    loaded = nuskills.load(piece)
    assert loaded.id == piece
    assert loaded.body.strip()
    assert not loaded.body.startswith("---")
    assert nuskills.read(piece) == loaded.body


@pytest.mark.parametrize("piece", sorted(FILES))
def test_frontmatter_keys(piece):
    text = FILES[piece]
    if not text.startswith("---"):
        return
    head = text.split("---", 2)[1]
    keys = {line.partition(":")[0].strip() for line in head.splitlines() if line.strip()}
    assert keys <= ALLOWED, f"frontmatter may only carry {sorted(ALLOWED)}, got {sorted(keys)}"


def test_unknown_piece():
    with pytest.raises(KeyError):
        nuskills.load("nu/no-such-piece")
