#!/usr/bin/env python3
"""
MCP Server for RustChain Staking Gate

Exposes the staking protocol as MCP tools:
- stake_and_acquire: Stake RTC on a skill
- submit_result: Submit work for a staked task
- poll_verdict: Check verdict status
- verify_attestation: Verify Ed25519-signed attestation

Usage:
    python mcp_server.py
    # Or with stdio transport (for MCP clients):
    python mcp_server.py --transport stdio
"""

import json
import sys
import argparse
from typing import Any, Dict, Optional
from staking_client import StakingClient, StakingConfig, StakeRequest, SubmitRequest
from langchain_tool import RustChainStakingTool


class RustChainStakingMCPServer:
    """MCP Server exposing RustChain staking tools."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.tool = RustChainStakingTool(api_key=api_key)
        self.tools = [
            {
                "name": "stake_and_acquire",
                "description": (
                    "Stake RTC on a skill for self-improvement verification. "
                    "Returns task_id for tracking. Fail-safe: if gate unavailable, "
                    "stake is returned to caller."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "skill": {
                            "type": "string",
                            "description": "Skill/domain to stake on (e.g., 'code-review')"
                        },
                        "bond_rtc": {
                            "type": "number",
                            "description": "RTC amount to bond",
                            "exclusiveMinimum": 0
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Optional agent/wallet identifier"
                        }
                    },
                    "required": ["skill", "bond_rtc"]
                }
            },
            {
                "name": "submit_result",
                "description": "Submit work results for a staked task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID from stake_and_acquire"},
                        "result": {"type": "object", "description": "Result payload (skill-dependent)"}
                    },
                    "required": ["task_id", "result"]
                }
            },
            {
                "name": "poll_verdict",
                "description": "Poll for verdict on a staked task. Returns attestation when verified.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID to poll"}
                    },
                    "required": ["task_id"]
                }
            },
            {
                "name": "verify_attestation",
                "description": "Verify an Ed25519-signed attestation from the gate.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "verdict": {"type": "string", "description": "Verdict hex string"},
                        "attestation": {"type": "object", "description": "Attestation object with signature"}
                    },
                    "required": ["verdict", "attestation"]
                }
            }
        ]
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an MCP request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "rustchain-staking-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.tools}
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            
            if tool_name == "stake_and_acquire":
                result = self.tool.stake_and_acquire(
                    skill=args["skill"],
                    bond_rtc=args["bond_rtc"],
                    agent_id=args.get("agent_id"),
                )
            elif tool_name == "submit_result":
                result = self.tool.submit_result(
                    task_id=args["task_id"],
                    result=args["result"],
                )
            elif tool_name == "poll_verdict":
                result = self.tool.poll_verdict(task_id=args["task_id"])
            elif tool_name == "verify_attestation":
                result = self.tool.client.verify(
                    verdict=args["verdict"],
                    attestation=args["attestation"],
                )
                result = {"valid": result.valid, "signer": result.signer, "error": result.error}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                }
            
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }]
                }
            }
        
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"}
        }
    
    def run_stdio(self):
        """Run MCP server with stdio transport."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                pass


def main():
    parser = argparse.ArgumentParser(description="RustChain Staking MCP Server")
    parser.add_argument("--transport", choices=["stdio"], default="stdio")
    parser.add_argument("--api-key", default=None, help="Gate API key")
    args = parser.parse_args()
    
    server = RustChainStakingMCPServer(api_key=args.api_key)
    server.run_stdio()


if __name__ == "__main__":
    main()
