"""Assemble the built skills under ``skills/`` from corpus pieces plus a header.

Each skill in :data:`nuskills.skills.SKILLS` becomes a directory in Claude
Code's skill layout (progressive disclosure)::

    skills/<name>/
      SKILL.md                     header + reference list + the inline pieces
      reference/<group>/<name>.md  one per reference piece, read on demand

Piece frontmatter is dropped. Inline pieces have their headings pushed down
one level so they sit under the skill's own title. A mention of another piece
by id (``nustd/ui-refs``) becomes a link to wherever that piece landed.

Run from the repo root::

    python -m nuskills.build            # write skills/
    python -m nuskills.build --check    # exit 1 if skills/ is out of date
"""

from __future__ import annotations

import argparse
import re
import sys
from importlib import resources
from pathlib import Path

import nuskills
from nuskills.skills import SKILLS, Skill


__all__ = ["build", "main", "render", "render_all", "stale"]


_BANNER = "<!-- Built by nuskills.build from the nuskills corpus. Do not edit by hand. -->"
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_HEADING = re.compile(r"^(#{1,5}) ")
# A piece id standing on its own: not part of a longer path (`nu/examples/x.py`,
# `nustackdev/nu/...`), optionally in backticks.
_MENTION = re.compile(r"(?<![\w/.-])(`?)((?:nu|nustd|nuspace)/[a-z][a-z0-9-]*)\1(?![\w/-])")


def render(skill: Skill) -> dict[str, str]:
    """``{path relative to skills/<name>: text}`` for one skill."""
    placed = dict.fromkeys(skill.inline, "inline") | dict.fromkeys(skill.reference, "reference")
    if len(placed) != len(skill.inline) + len(skill.reference):
        msg = f"skill {skill.name!r} lists a piece twice"
        raise ValueError(msg)
    loaded = {pid: nuskills.load(pid) for pid in placed}
    anchors = _anchors([loaded[pid] for pid in skill.inline])

    def link(pid: str, here: str) -> str:
        """Where ``pid`` is, seen from the file ``here`` (relative to the skill root)."""
        if pid not in placed:
            msg = f"skill {skill.name!r}: a piece mentions {pid!r}, which the skill does not carry"
            raise ValueError(msg)
        up = "../" * here.count("/")
        if placed[pid] == "inline":
            return ("" if here == "SKILL.md" else up + "SKILL.md") + "#" + anchors[pid]
        return up + _reference_path(pid)

    files: dict[str, str] = {}
    for pid in skill.reference:
        path = _reference_path(pid)
        body = _rewrite(loaded[pid].body, lambda target, p=path: link(target, p), demote=False)
        files[path] = f"{_BANNER}\n\n{body.strip()}\n"

    meta, intro = _header(skill.name)
    parts = [meta, _BANNER, intro.strip()]
    if skill.reference:
        rows = [
            f"| [{pid}]({_reference_path(pid)}) | {loaded[pid].summary} |"
            for pid in skill.reference
        ]
        parts.append(
            "## Reference\n\n"
            "Open a file when the task needs its topic. A piece id in the text "
            "(`nu/control`) names one of these or a section below.\n\n"
            "| File | What it covers |\n| --- | --- |\n" + "\n".join(rows)
        )
    for pid in skill.inline:
        parts.append(
            _rewrite(loaded[pid].body, lambda target: link(target, "SKILL.md"), demote=True).strip()
        )
    files["SKILL.md"] = "\n\n".join(parts) + "\n"
    return files


def render_all() -> dict[str, str]:
    """``{path relative to skills/: text}`` for every skill."""
    return {
        f"{skill.name}/{path}": text for skill in SKILLS for path, text in render(skill).items()
    }


def stale(out: Path) -> list[str]:
    """Paths under ``out`` that differ from a fresh build: changed, missing or extra."""
    want = render_all()
    have = {p.relative_to(out).as_posix(): p for p in out.rglob("*") if p.is_file()}
    diff = [
        path
        for path, text in want.items()
        if path not in have or have[path].read_text("utf-8") != text
    ]
    diff += [path for path in have if path not in want]
    return sorted(diff)


def build(out: Path) -> list[str]:
    """Write every skill under ``out``, removing files no skill produces. Returns what changed."""
    changed = stale(out)
    want = render_all()
    for path in changed:
        target = out / path
        if path in want:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(want[path], "utf-8")
        else:
            target.unlink()
    for folder in sorted((p for p in out.rglob("*") if p.is_dir()), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    return changed


def main(argv: list[str] | None = None) -> int:
    """``python -m nuskills.build [--out skills] [--check]``."""
    parser = argparse.ArgumentParser(
        prog="python -m nuskills.build", description=__doc__.splitlines()[0]
    )
    parser.add_argument(
        "--out", type=Path, default=Path("skills"), help="the skills directory (default: ./skills)"
    )
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if out of date")
    args = parser.parse_args(argv)
    if args.check:
        diff = stale(args.out)
        for path in diff:
            print(f"out of date: {args.out / path}")  # noqa: T201
        if diff:
            print("run: python -m nuskills.build")  # noqa: T201
        return 1 if diff else 0
    args.out.mkdir(parents=True, exist_ok=True)
    for path in build(args.out):
        print(f"wrote {args.out / path}")  # noqa: T201
    return 0


def _reference_path(pid: str) -> str:
    return f"reference/{pid}.md"


def _header(name: str) -> tuple[str, str]:
    """``(frontmatter block, body)`` of ``headers/<name>.md``, frontmatter kept verbatim."""
    text = resources.files(__package__).joinpath("headers", name + ".md").read_text("utf-8")
    _, sep, rest = text.partition("---\n")
    meta, sep2, body = rest.partition("\n---\n")
    if sep != "---\n" or not text.startswith("---") or not sep2:
        msg = f"header {name!r} needs a --- frontmatter block"
        raise ValueError(msg)
    return f"---\n{meta}\n---", body


def _anchors(pieces: list[nuskills.Piece]) -> dict[str, str]:
    """GitHub style anchors of each inline piece's title, suffixed when one repeats."""
    seen: dict[str, int] = {}
    found = {}
    for piece in pieces:
        title = piece.title or piece.id
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        found[piece.id] = slug if not count else f"{slug}-{count}"
    return found


def _rewrite(body: str, link: object, *, demote: bool) -> str:
    """Outside fences: link piece mentions, and push headings down one level when ``demote``."""
    out = []
    fence = ""
    for line in body.splitlines():
        opened = _FENCE.match(line)
        if fence:
            if (
                opened
                and opened[1][0] == fence[0]
                and len(opened[1]) >= len(fence)
                and not line.strip().strip(fence[0])
            ):
                fence = ""
            out.append(line)
            continue
        if opened:
            fence = opened[1]
            out.append(line)
            continue
        if demote:
            line = _HEADING.sub(lambda m: "#" + m[1] + " ", line)
        line = _MENTION.sub(lambda m: f"[{m[1]}{m[2]}{m[1]}]({link(m[2])})", line)
        out.append(line)
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
