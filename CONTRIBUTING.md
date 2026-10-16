# Contributing to TextToSolid

Thanks for your interest in improving TextToSolid! Contributions of all kinds
are welcome: bug reports, feature requests, documentation, and code.

## Ways to contribute

- **Report bugs** — open an Issue with a minimal reproducible example (a small
  `.t2s` snippet or JSON spec) and the observed vs. expected output.
- **Propose features** — open an Issue describing the use case before writing
  large changes, so we can align on design.
- **Submit code** — open a Pull Request against the `main` branch.

## Local setup

TextToSolid is **zero-dependency** (pure Python standard library), so there is
nothing to install:

```bash
git clone https://github.com/gitstq/TextToSolid.git
cd TextToSolid
python -m unittest discover -s tests -v
```

Python 3.9+ is required.

## Commit convention

This project follows the [Angular commit convention](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`.

Examples:

```
feat(dsl): add torus primitive with tube segment control
fix(csg): correct winding after mirrored subtraction
docs(readme): add Traditional Chinese version
```

## Pull request rules

1. Keep PRs focused — one logical change per PR.
2. All code must pass `python -m compileall -q texttosolid tests` and the full
   unit test suite (these run in CI on every PR).
3. Add or update unit tests for behavior changes.
4. Update documentation (README) when public behavior changes.
5. Do not commit build artifacts, caches, or secrets. See `.gitignore`.

## Code style

- Pure standard library only — no third-party dependencies.
- Public functions carry type hints and docstrings.
- Prefer editing existing modules over adding new ones.
- Keep the DSL and the Agent JSON protocol feature-parity where practical.

## Security

Never commit tokens or credentials. If you believe you have found a security
issue, please report it privately to the maintainers.
