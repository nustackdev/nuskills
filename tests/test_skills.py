"""The built skills under ``skills/`` match the corpus, and the plugin around them is well formed."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import nuskills
from nuskills import build
from nuskills.skills import SKILLS


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
PLUGIN = ROOT / ".claude-plugin"


def test_skills_are_up_to_date():
    """``skills/`` is committed output: a corpus or header edit needs a rebuild."""
    diff = build.stale(SKILLS_DIR)
    assert not diff, f"skills/ is out of date, run `uv run python -m nuskills.build`: {diff}"


def test_every_piece_is_in_a_skill():
    """A new piece no skill lists would be tested and shipped to nobody outside nuagent."""
    used = {pid for skill in SKILLS for pid in skill.inline + skill.reference}
    assert set(nuskills.pieces()) <= used, sorted(set(nuskills.pieces()) - used)


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_skill_md(skill):
    text = build.render(skill)["SKILL.md"]
    # Claude Code's guideline: SKILL.md stays in context once loaded, keep it under 500 lines.
    assert len(text.splitlines()) < 500
    head = text.split("---", 2)[1]
    meta = dict(line.split(": ", 1) for line in head.strip().splitlines())
    assert meta["name"] == skill.name
    assert 0 < len(meta["description"]) <= 1024
    assert "<" not in meta["description"] and ">" not in meta["description"]


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_header_holds_no_program(skill):
    """Headers are not run through the block harness, so they carry no python blocks."""
    text = (ROOT / "src/nuskills/headers" / f"{skill.name}.md").read_text("utf-8")
    assert "```python" not in text


# The links the build writes: to a reference file, to SKILL.md, or to an anchor in it.
LINK = re.compile(r"\]\(((?:\.\./)*(?:reference/[\w/-]+\.md|SKILL\.md)|)(?:#([\w-]+))?\)")


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_links_resolve(skill):
    """Every link the build wrote points at a file the skill ships, and an anchor in SKILL.md."""
    files = build.render(skill)
    anchors = {
        re.sub(r"[^\w\- ]", "", line.lstrip("#").strip().lower()).replace(" ", "-")
        for line in files["SKILL.md"].splitlines()
        if line.startswith("## ")
    }
    for path, text in files.items():
        for target, anchor in LINK.findall(text):
            parts: list[str] = []
            for part in (Path(path).parent / (target or path)).as_posix().split("/"):
                if part == "..":
                    parts.pop()
                elif part != ".":
                    parts.append(part)
            assert "/".join(parts) in files, f"{skill.name}/{path} links to missing {target}"
            if anchor:
                assert anchor in anchors, f"{skill.name}/{path} links to missing #{anchor}"


def test_plugin_manifests():
    plugin = json.loads((PLUGIN / "plugin.json").read_text("utf-8"))
    market = json.loads((PLUGIN / "marketplace.json").read_text("utf-8"))
    version = re.search(
        r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text("utf-8"), re.M
    )[1]
    assert plugin["name"] == "nuskills"
    assert plugin["version"] == version, "plugin.json and pyproject.toml versions move together"
    assert [p["name"] for p in market["plugins"]] == [plugin["name"]]
    assert market["plugins"][0]["source"] == "./"
    assert sorted(p.name for p in SKILLS_DIR.iterdir()) == sorted(s.name for s in SKILLS)
