# Changelog

## 1.0.0 (2026-10-05)

- Initial release.
- AEAP Composition Boundary Adapter for CrewAI.
- Wraps `crewai.tools.BaseTool` subclass instances with the AEAP RDP via `aiyoplane-mcp-authz`.
- Entry points: `wrap_tool`, `wrap_tools`.
- Fail-closed defaults per AEAP §2.2 invariant 5.
- Apache 2.0.
