"""aiyoplane-crewai.

AEAP Composition Boundary Adapter for CrewAI.

A thin wrapper that attaches the AEAP Runtime Decision Point (via
aiyoplane-mcp-authz) to the CrewAI tool invocation surface. Consequential
tool executions by any crew member produce independently verifiable
Execution Receipts.

Aiyoplane, Inc. - Apache 2.0 licensed.
https://aiyoplane.com

Specification: https://github.com/aiyoplane/aeap
"""

from aiyoplane_crewai.adapter import (
    AiyoCrewAITool,
    IntentBuilder,
    wrap_tool,
    wrap_tools,
)
from aiyoplane_crewai.errors import (
    AdapterConfigError,
    AiyoCrewAIError,
    BlockedByPolicy,
    EscalationRequired,
)

__version__ = "1.0.2"

__all__ = [
    "AiyoCrewAITool",
    "IntentBuilder",
    "wrap_tool",
    "wrap_tools",
    "AiyoCrewAIError",
    "AdapterConfigError",
    "BlockedByPolicy",
    "EscalationRequired",
    "__version__",
]
