"""AEAP Composition Boundary Adapter for CrewAI.

The Composition Boundary primitive from AEAP §9, realized against CrewAI's
tool-invocation surface. A CrewAI tool is a subclass of `crewai.tools.BaseTool`
that implements `_run` (and optionally `_arun`); this adapter wraps those
methods so the AEAP Runtime Decision Point evaluates an Intent before the
underlying tool logic executes.

Multi-agent crew composition is a textbook case where
`"may this crew member perform this class of action?"` ≠
`"should this specific action execute right now?"` — the first is agent
delegation / role assignment; the second is AEAP's territory.

Usage
-----

    from crewai.tools import BaseTool
    from aiyoplane_mcp_authz import create_aiyo_mcp_authz, create_local_rdp
    from aiyoplane_crewai import wrap_tool

    class TransferFundsTool(BaseTool):
        name: str = "transfer_funds"
        description: str = "Transfer funds between accounts."

        def _run(self, amount: int, to_account: str) -> str:
            return actually_transfer(amount, to_account)

    authz = create_aiyo_mcp_authz(
        rdp=create_local_rdp(policy=my_policy),
        tool_config={
            "transfer_funds": {"aiyo_gated": True, "action": {"type": "payment"}},
        },
    )

    guarded_transfer = wrap_tool(
        TransferFundsTool(),
        authz=authz,
        intent_builder=lambda kwargs: {
            "type": "payment",
            "amount": kwargs["amount"],
            "target": kwargs["to_account"],
        },
    )

    # Attach to a crew member the usual way:
    #   agent = Agent(role="banker", tools=[guarded_transfer], ...)

Fail-closed semantics
---------------------

Every ambiguous condition — missing intent_builder, missing tool_config
entry, RDP unreachable, non-dict Intent — results in BlockedByPolicy.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Dict, Iterable, List, Optional

try:
    from crewai.tools import BaseTool
except ImportError as _import_err:  # pragma: no cover
    raise ImportError(
        "aiyoplane-crewai requires crewai (crewai.tools). Install with "
        "`pip install crewai`."
    ) from _import_err

from aiyoplane_crewai.errors import (
    AdapterConfigError,
    BlockedByPolicy,
    EscalationRequired,
)

# Signature: (tool_kwargs: Dict[str, Any]) -> Dict[str, Any]
IntentBuilder = Callable[[Dict[str, Any]], Dict[str, Any]]


class AiyoCrewAITool(BaseTool):
    """A CrewAI tool wrapped with an AEAP Composition Boundary.

    The wrapped tool preserves the inner tool's `name`, `description`,
    and args_schema so crew members see no behavioral change at interface time.
    The only visible change: a non-ALLOW RDP verdict raises the appropriate
    exception instead of returning a result.
    """

    name: str
    description: str
    inner_tool: Any
    authz: Any
    intent_builder: IntentBuilder
    tool_name_for_authz: str
    return_receipt: bool = False

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        *,
        inner_tool: BaseTool,
        authz: Any,
        intent_builder: IntentBuilder,
        tool_name_for_authz: Optional[str] = None,
        return_receipt: bool = False,
    ) -> None:
        resolved = tool_name_for_authz or inner_tool.name
        super().__init__(
            name=inner_tool.name,
            description=inner_tool.description,
            inner_tool=inner_tool,
            authz=authz,
            intent_builder=intent_builder,
            tool_name_for_authz=resolved,
            return_receipt=return_receipt,
        )
        if getattr(inner_tool, "args_schema", None) is not None:
            self.args_schema = inner_tool.args_schema

    def _build_intent(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if not callable(self.intent_builder):
            raise AdapterConfigError(
                f"intent_builder for tool '{self.name}' is not callable"
            )
        try:
            intent = self.intent_builder(kwargs)
        except Exception as exc:
            raise BlockedByPolicy(
                f"intent_builder for tool '{self.name}' raised: {exc!r}",
                reason_code="INTENT_BUILD_FAILED",
            ) from exc
        if not isinstance(intent, dict):
            raise BlockedByPolicy(
                f"intent_builder for tool '{self.name}' did not return a dict",
                reason_code="INTENT_SHAPE_INVALID",
            )
        return intent

    async def _evaluate(self, kwargs: Dict[str, Any]) -> Any:
        intent = self._build_intent(kwargs)
        wrap = self.authz.wrap(self.tool_name_for_authz)

        async def _passthrough(args: Dict[str, Any], ctx: Any) -> Any:
            return ctx

        wrapped = wrap(_passthrough)

        try:
            if inspect.iscoroutinefunction(wrapped):
                ctx = await wrapped(dict(kwargs), None)
            else:
                ctx = wrapped(dict(kwargs), None)
                if inspect.isawaitable(ctx):
                    ctx = await ctx
        except Exception as exc:
            msg = str(exc)
            if "escalat" in msg.lower() or "ESCALATE" in msg:
                raise EscalationRequired(
                    f"AEAP ESCALATE verdict for tool '{self.name}' "
                    f"(intent={intent!r}): {msg}",
                    extra={"inner_exception": type(exc).__name__, "intent": intent},
                ) from exc
            raise BlockedByPolicy(
                f"AEAP non-ALLOW verdict for tool '{self.name}' "
                f"(intent={intent!r}): {msg}",
                reason_code=type(exc).__name__,
                extra={"inner_exception": type(exc).__name__, "intent": intent},
            ) from exc

        return ctx

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        tool_args = dict(kwargs) if kwargs else (args[0] if args and isinstance(args[0], dict) else {})
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio  # type: ignore
                nest_asyncio.apply()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        ctx = loop.run_until_complete(self._evaluate(tool_args))
        result = self.inner_tool._run(*args, **kwargs)
        if self.return_receipt:
            return {"result": result, "aeap_receipt": getattr(ctx, "receipt", None)}
        return result

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        tool_args = dict(kwargs) if kwargs else (args[0] if args and isinstance(args[0], dict) else {})
        ctx = await self._evaluate(tool_args)
        if hasattr(self.inner_tool, "_arun"):
            result = await self.inner_tool._arun(*args, **kwargs)
        else:
            result = self.inner_tool._run(*args, **kwargs)
        if self.return_receipt:
            return {"result": result, "aeap_receipt": getattr(ctx, "receipt", None)}
        return result


def wrap_tool(
    tool: BaseTool,
    *,
    authz: Any,
    intent_builder: IntentBuilder,
    tool_name_for_authz: Optional[str] = None,
    return_receipt: bool = False,
) -> AiyoCrewAITool:
    """Wrap a single CrewAI tool with an AEAP Composition Boundary."""
    if not isinstance(tool, BaseTool):
        raise AdapterConfigError(
            f"wrap_tool expected a crewai.tools.BaseTool, got {type(tool).__name__}"
        )
    if not callable(intent_builder):
        raise AdapterConfigError(
            "wrap_tool requires an intent_builder callable"
        )
    return AiyoCrewAITool(
        inner_tool=tool,
        authz=authz,
        intent_builder=intent_builder,
        tool_name_for_authz=tool_name_for_authz,
        return_receipt=return_receipt,
    )


def wrap_tools(
    tools: Iterable[BaseTool],
    *,
    authz: Any,
    intent_builders: Dict[str, IntentBuilder],
    return_receipt: bool = False,
) -> List[BaseTool]:
    """Wrap a collection of CrewAI tools. Tools whose name is not a key in
    `intent_builders` pass through unchanged (explicit opt-in to AEAP gating)."""
    out: List[BaseTool] = []
    for t in tools:
        builder = intent_builders.get(t.name)
        if builder is None:
            out.append(t)
            continue
        out.append(wrap_tool(t, authz=authz, intent_builder=builder, return_receipt=return_receipt))
    return out
