"""The skills built from the corpus: which pieces each one carries, and in what order.

This is the one place piece order lives for the built skills. Each skill is a
header (``headers/<name>.md``: the SKILL.md frontmatter plus a few lines of
when-to-use) followed by two ordered lists of piece ids:

- ``inline``: concatenated into ``SKILL.md`` itself, in this order. These are
  what every task needs, so they load with the skill. Keep the total under
  Claude Code's 500 line guideline; ``tests/test_skills.py`` enforces it.
- ``reference``: written next to it as ``reference/<group>/<name>.md`` and
  listed in ``SKILL.md`` with their summaries. The agent opens one when the
  task needs it, so they cost nothing until then.

A piece that mentions another by id (``nustd/ui-refs``) gets a link to it, so
every piece a skill's pieces mention must be in the skill too. The build
fails otherwise.
"""

from __future__ import annotations

from typing import NamedTuple


__all__ = ["SKILLS", "Skill"]


class Skill(NamedTuple):
    """One built skill: its name (its directory and header), and its pieces in order."""

    name: str
    inline: tuple[str, ...]
    reference: tuple[str, ...]


SKILLS: tuple[Skill, ...] = (
    Skill(
        name="nu",
        inline=(
            "nu/thesis",
            "nu/crashcourse",
            "nu/composition",
            "nu/pitfalls",
            "nu/inspect",
        ),
        reference=(
            "nu/control",
            "nu/reactive",
            "nu/errors",
            "nu/host",
            "nu/examples",
            "nustd/fabrics",
            "nustd/kv",
            "nustd/service",
            "nustd/ui-refs",
            "nustd/ui-layout",
            "nustd/ui-app",
        ),
    ),
    Skill(
        name="nuspace",
        inline=(
            "nu/crashcourse",
            "nuspace/model",
            "nuspace/brackets",
        ),
        reference=(
            "nu/inspect",
            "nuspace/ops",
            "nuspace/snippets",
            "nuspace/drawing",
            "nu/thesis",
            "nu/composition",
            "nu/pitfalls",
            "nu/control",
            "nu/reactive",
            "nu/errors",
            "nu/host",
            "nu/examples",
            "nustd/fabrics",
            "nustd/kv",
            "nustd/service",
            "nustd/ui-refs",
            "nustd/ui-layout",
            "nustd/ui-app",
        ),
    ),
)
