"""Minimal example of aiyoplane-crewai.

Shows the AEAP gate against a CrewAI tool. Runs in-process; no network,
no credentials, no live LLM call. Demonstrates the three verdicts.

Run: python examples/minimal.py
"""

from __future__ import annotations

from crewai.tools import BaseTool
from aiyoplane_mcp_authz import create_aiyo_mcp_authz, create_local_rdp
from aiyoplane_crewai import (
    BlockedByPolicy,
    EscalationRequired,
    wrap_tool,
)


class TransferFundsTool(BaseTool):
    name: str = "transfer_funds"
    description: str = "Transfer funds between accounts."

    def _run(self, amount: int, to_account: str) -> str:
        return f"Transferred ${amount} to {to_account}"


def main() -> None:
    policy = {
        "rules": [
            {"action_type": "payment", "amount_max": 1_000, "effect": "allow"},
            {"action_type": "payment", "amount_max": 10_000, "effect": "escalate"},
            {"action_type": "payment", "effect": "block"},
        ]
    }

    authz = create_aiyo_mcp_authz(
        rdp=create_local_rdp(policy=policy),
        tool_config={
            "transfer_funds": {"aiyo_gated": True, "action": {"type": "payment"}},
        },
    )

    guarded = wrap_tool(
        TransferFundsTool(),
        authz=authz,
        intent_builder=lambda kw: {
            "type": "payment",
            "amount": kw["amount"],
            "target": kw["to_account"],
        },
    )

    print("ALLOW ($500):")
    print("  ", guarded._run(amount=500, to_account="acct_A"))

    print("\nESCALATE ($5,000):")
    try:
        guarded._run(amount=5_000, to_account="acct_B")
    except EscalationRequired as exc:
        print("  Held:", exc)

    print("\nBLOCK ($50,000):")
    try:
        guarded._run(amount=50_000, to_account="acct_C")
    except BlockedByPolicy as exc:
        print("  Blocked:", exc)


if __name__ == "__main__":
    main()
