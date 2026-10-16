# tests

- `test_blocks.py`: every fenced `python` block in the corpus builds against the current stack. One test per block, id `<piece>:<line>`.
- `test_pieces.py`: every file under `corpus/` loads through the public loader, with only `title` and `summary` frontmatter.
- `_lib/_support/blocks.py`: fence extraction. `_lib/_support/space.py`: the in-memory space nuspace blocks run in.

To verify a piece you wrote: `uv run pytest -k <group>/<name>`. Fence rules are in the repo README, "Fences".
