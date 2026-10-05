"""Tests for the AEAP Composition Boundary Adapter for CrewAI."""

from __future__ import annotations

import pytest
from crewai.tools import BaseTool

from aiyoplane_crewai import (
    AdapterConfigError,
    BlockedByPolicy,
    EscalationRequired,
    wrap_tool,
    wrap_tools,
)


class TransferTool(BaseTool):
    name: str = "transfer"
    description: str = "Transfer funds."

    def _run(self, amount: int, to_account: str) -> str:
        return f"Transferred ${amount} to {to_account}"


class SearchTool(BaseTool):
    name: str = "search"
    description: str = "Search docs."

    def _run(self, query: str) -> str:
        return f"Results for '{query}'"


def _make_authz(rules):
    from aiyoplane_mcp_authz import create_aiyo_mcp_authz, create_local_rdp
    return create_aiyo_mcp_authz(
        rdp=create_local_rdp(policy={"rules": rules}),
        tool_config={"transfer": {"aiyo_gated": True, "action": {"type": "payment"}}},
    )


def test_allow_runs_the_inner_tool():
    authz = _make_authz([{"action_type": "payment", "effect": "allow"}])
    gated = wrap_tool(
        TransferTool(),
        authz=authz,
        intent_builder=lambda kw: {"type": "payment", "amount": kw["amount"]},
    )
    result = gated._run(amount=500, to_account="acct_A")
    assert "Transferred $500" in result


def test_block_prevents_execution():
    authz = _make_authz([{"action_type": "payment", "effect": "block"}])
    gated = wrap_tool(
        TransferTool(),
        authz=authz,
        intent_builder=lambda kw: {"type": "payment"},
    )
    with pytest.raises(BlockedByPolicy):
        gated._run(amount=500, to_account="acct_A")


def test_escalate_raises():
    authz = _make_authz([{"action_type": "payment", "effect": "escalate"}])
    gated = wrap_tool(
        TransferTool(),
        authz=authz,
        intent_builder=lambda kw: {"type": "payment"},
    )
    with pytest.raises((EscalationRequired, BlockedByPolicy)):
        gated._run(amount=500, to_account="acct_A")


def test_broken_intent_builder_blocks():
    authz = _make_authz([{"action_type": "payment", "effect": "allow"}])

    def _broken(kw):
        raise ValueError("broken")

    gated = wrap_tool(TransferTool(), authz=authz, intent_builder=_broken)
    with pytest.raises(BlockedByPolicy):
        gated._run(amount=500, to_account="acct_A")


def test_non_dict_intent_blocks():
    authz = _make_authz([{"action_type": "payment", "effect": "allow"}])
    gated = wrap_tool(
        TransferTool(),
        authz=authz,
        intent_builder=lambda kw: "not a dict",
    )
    with pytest.raises(BlockedByPolicy):
        gated._run(amount=500, to_account="acct_A")


def test_non_basetool_raises_config_error():
    authz = _make_authz([{"action_type": "payment", "effect": "allow"}])
    with pytest.raises(AdapterConfigError):
        wrap_tool("not a tool", authz=authz, intent_builder=lambda kw: {"type": "payment"})


def test_wrap_tools_passes_through_without_builder():
    authz = _make_authz([{"action_type": "payment", "effect": "allow"}])
    transfer = TransferTool()
    search = SearchTool()
    wrapped = wrap_tools(
        [transfer, search],
        authz=authz,
        intent_builders={"transfer": lambda kw: {"type": "payment"}},
    )
    assert len(wrapped) == 2
    search_wrapped = next(t for t in wrapped if t.name == "search")
    transfer_wrapped = next(t for t in wrapped if t.name == "transfer")
    assert search_wrapped is search
    assert transfer_wrapped is not transfer
