# Changelog

## 1.0.2 (2026-10-05)

- Fix `__version__` constant drift. `src/aiyoplane_crewai/__init__.py` had `__version__ = "1.0.0"` while `pyproject.toml` said `1.0.1`. Programmatic version checks via `aiyoplane_crewai.__version__` were returning the stale value. No behavior change.
- v1.0.1 yanked.

## 1.0.1 (2026-10-05) — YANKED

- Dependency metadata correction. No behavior change.
- `requires-python` bumped from `>=3.9` to `>=3.10` to match CrewAI's own minimum (every CrewAI version from 0.10 onwards requires Python 3.10+).
- `crewai` dependency range loosened from `>=0.70,<0.90` to `>=0.70` (no upper bound). The original constraint was too narrow — CrewAI moved far past 0.90 before this adapter shipped. The adapter's integration surface targets `crewai.tools.BaseTool`, which has remained API-stable since v0.70.
- v1.0.0 yanked to prevent broken installs.

## 1.0.0 (2026-10-05) — YANKED

- Initial release — yanked due to incorrect `requires-python` constraint and overly narrow `crewai` dependency pin. Replaced by v1.0.1.
- AEAP Composition Boundary Adapter for CrewAI.
- Wraps `crewai.tools.BaseTool` subclass instances with the AEAP RDP via `aiyoplane-mcp-authz`.
- Entry points: `wrap_tool`, `wrap_tools`.
- Fail-closed defaults per AEAP §2.2 invariant 5.
- Apache 2.0.
