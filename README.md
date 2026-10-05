# aiyoplane-crewai

**AEAP Composition Boundary Adapter for CrewAI.**

A thin wrapper that attaches the AEAP Runtime Decision Point (RDP) to CrewAI's tool invocation surface. Consequential tool executions by any crew member produce independently verifiable Execution Receipts. The adapter composes with CrewAI's Flow, Crew, Agent, and Task primitives — it does not replace any of them.

```bash
pip install aiyoplane-crewai
```

## Why this matters for multi-agent crews

CrewAI's architecture is deliberately about multiple specialized agents coordinating on a workflow:

```
Research agent → Analysis agent → Purchasing agent → Payment agent → Fulfillment agent
```

Each agent has a role, a goal, and tools. Role assignment answers *"may this crew member perform this class of action?"* — identity and delegation. AEAP answers a different question at the tool-invocation moment: *"should this specific action execute right now, under the Protected Party's current Policy, against the specific Intent being formed?"* The two layers compose; AEAP sits beneath the crew structure.

See the [AEAP specification](https://github.com/aiyoplane/aeap) §9 for the Composition Boundary primitive this adapter realizes.

## Minimal usage

```python
from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from aiyoplane_mcp_authz import create_aiyo_mcp_authz, create_local_rdp
from aiyoplane_crewai import wrap_tool

class TransferFundsTool(BaseTool):
    name: str = "transfer_funds"
    description: str = "Transfer funds between accounts."

    def _run(self, amount: int, to_account: str) -> str:
        return actually_transfer(amount, to_account)

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

guarded_transfer = wrap_tool(
    TransferFundsTool(),
    authz=authz,
    intent_builder=lambda kwargs: {
        "type": "payment",
        "amount": kwargs["amount"],
        "target": kwargs["to_account"],
    },
)

# Attach the gated tool to a crew member the usual way:
banker = Agent(
    role="Banker",
    goal="Execute payment transactions for the user.",
    backstory="A senior banker focused on correct and policy-compliant transfers.",
    tools=[guarded_transfer],
)
```

## Wrapping a whole tool list

```python
from aiyoplane_crewai import wrap_tools

all_tools = [SearchDocsTool(), ReadUserTool(), TransferFundsTool(), DeleteAccountTool()]

guarded_tools = wrap_tools(
    all_tools,
    authz=authz,
    intent_builders={
        "transfer_funds": lambda kw: {"type": "payment", "amount": kw["amount"]},
        "delete_account": lambda kw: {"type": "destructive", "target": kw["user_id"]},
    },
)
```

Tools whose name is not a key in `intent_builders` pass through unchanged.

## Composition Boundary — what the adapter actually does

For each wrapped tool invocation:

1. **Intent construction.** `intent_builder(tool_kwargs)` produces an AEAP Intent payload.
2. **RDP evaluation.** Via `aiyoplane-mcp-authz`'s AiyoAuthz middleware.
3. **Verdict composition.**
   - **ALLOW** → inner tool `_run`/`_arun` executes with the original arguments.
   - **ESCALATE** → `EscalationRequired` is raised; the crew's error handling decides routing.
   - **BLOCK** → `BlockedByPolicy` is raised; the tool never executes.
4. **Fail-closed default** on every ambiguous condition.

## Local vs. hosted RDP

```python
from aiyoplane_mcp_authz import create_local_rdp, create_hosted_rdp

# Development:
authz = create_aiyo_mcp_authz(rdp=create_local_rdp(policy=policy), tool_config={...})

# Production:
authz = create_aiyo_mcp_authz(
    rdp=create_hosted_rdp(api_key="aiyo_live_..."),
    tool_config={...},
)
```

## API reference

### `wrap_tool(tool, *, authz, intent_builder, tool_name_for_authz=None, return_receipt=False)`

Wrap a single CrewAI tool. Returns an `AiyoCrewAITool` (also a `BaseTool`).

### `wrap_tools(tools, *, authz, intent_builders, return_receipt=False)`

Wrap a collection. Explicit opt-in via `intent_builders` keys.

### Exceptions

- `AiyoCrewAIError` — base class
- `AdapterConfigError` — adapter configuration is invalid
- `BlockedByPolicy` — RDP returned BLOCK
- `EscalationRequired` — RDP returned ESCALATE

## License

Apache License 2.0.

## Links

- **AEAP specification:** https://github.com/aiyoplane/aeap
- **Underlying implementation:** [`aiyoplane-mcp-authz`](https://pypi.org/project/aiyoplane-mcp-authz/)
- **Trust surface:** https://aiyoplane.com/trust
- **Issues:** https://github.com/aiyoplane/crewai/issues

CrewAI is a trademark of its respective owners. This package is an independent AEAP Composition Boundary Adapter and is not affiliated with or endorsed by the CrewAI team.

**Verify First. Execute Second.**
