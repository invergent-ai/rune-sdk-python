# Contributing

Open an issue or pull request in this Rune SDK repository. Keep changes compatible with
the Rune public API and preserve the upstream MIT license and attribution.

Run `uv sync --dev`, `uv run pytest -m "not integration"`, `uv run ruff check .` and
`uv build` before submitting. Live integration tests require an API key in the environment;
never put one in code or test fixtures. Add transport tests for changed API behavior.

Package publication is separate from merging code and requires registry configuration.
