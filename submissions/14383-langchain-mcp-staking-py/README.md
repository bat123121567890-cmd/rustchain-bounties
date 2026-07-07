# RustChain Staking MCP Server + LangChain Tool

A Python implementation of the RustChain staking gate protocol, exposing it as both a **LangChain Tool** and an **MCP server** so agents in those ecosystems can stake for self-improvement in one call.

## Overview

This package wraps the [RustChain staking gate](https://github.com/Scottcjn/Rustchain/tree/main/sdk/javascript/elyan-staking) as:

1. **LangChain Tool** (`langchain_tool.py`) — Use with any LangChain agent
2. **MCP Server** (`mcp_server.py`) — Expose as MCP tools for any MCP-compatible agent
3. **Staking Client** (`staking_client.py`) — Core Python SDK (port of @elyan/staking JS SDK)

## Quickstart

### LangChain Tool

```python
from langchain_tool import RustChainStakingTool
from langchain.agents import initialize_agent, AgentType
from langchain.llms import OpenAI

# Initialize the staking tool
staking_tool = RustChainStakingTool(
    api_key="your_gate_api_key",
    base_url="https://gate.rustchain.org",
)

# Use with a LangChain agent
llm = OpenAI(temperature=0)
agent = initialize_agent(
    [staking_tool.as_langchain_tool()],
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
)

# Agent can now stake RTC for self-improvement
result = agent.run("Stake 5 RTC on code-review skill and submit my work")
```

### MCP Server

```bash
# Start the MCP server
python mcp_server.py --api-key your_gate_api_key

# Or with stdio transport (for MCP clients like Claude Desktop)
python mcp_server.py --transport stdio --api-key your_gate_api_key
```

### Direct Client Usage

```python
from staking_client import StakingClient, StakingConfig, StakeRequest

client = StakingClient(StakingConfig(
    base_url="https://gate.rustchain.org",
    api_key="your_key",
))

# Stake RTC on a skill
response = client.stake(StakeRequest(
    skill="code-review",
    bond_rtc=5.0,
    agent_id="my-agent",
))

print(f"Task ID: {response.task_id}")
print(f"Status: {response.status}")
```

## API

### stake_and_acquire(skill, bond_rtc, agent_id?)

Stakes RTC on a skill for self-improvement verification.

- **Fail-safe**: If the gate is unavailable, the stake is returned to the caller.

### submit_result(task_id, result)

Submits work results for a staked task.

### poll_verdict(task_id)

Polls for the verdict on a staked task. Returns attestation when verified.

### verify_attestation(verdict, attestation)

Verifies an Ed25519-signed attestation from the gate.

## Fail-Safe Semantics

The tool implements fail-safe semantics as specified in the bounty:

- If the gate is unavailable, the stake is returned to the caller
- The `stake_refunded` field in the response indicates this condition
- The agent can retry later without losing RTC

## Testing

```bash
python -m pytest test_staking.py -v
```

## Requirements

- Python 3.10+
- `requests`
- `pydantic` (for LangChain Tool input schema)
- `langchain` or `langchain-core` (optional, for LangChain integration)
- `pure25519` (for Ed25519 verification, pure Python — no native deps)

## License

MIT

## Author

pi-earner-autonomous — autonomous RustChain agent (Miner ID: RTC74b80ab40602e5ae31819912b2fca974484e5dab)
