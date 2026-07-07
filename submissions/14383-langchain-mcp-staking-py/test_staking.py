"""
Tests for RustChain Staking Client and LangChain Tool
"""

import unittest
from unittest.mock import patch, MagicMock
from staking_client import StakingClient, StakingConfig, StakeRequest, SubmitRequest
from langchain_tool import RustChainStakingTool


class TestStakingClient(unittest.TestCase):
    """Test the StakingClient."""
    
    def setUp(self):
        self.config = StakingConfig(
            base_url="https://gate.rustchain.org",
            api_key="test_key",
            gate_pubkey="test_pubkey",
        )
        self.client = StakingClient(self.config)
    
    def test_config_defaults(self):
        """Test default config values."""
        config = StakingConfig()
        self.assertEqual(config.base_url, "https://gate.rustchain.org")
        self.assertEqual(config.timeout_ms, 30000)
    
    def test_stake_request(self):
        """Test stake request structure."""
        req = StakeRequest(skill="code-review", bond_rtc=5.0, agent_id="agent1")
        self.assertEqual(req.skill, "code-review")
        self.assertEqual(req.bond_rtc, 5.0)
        self.assertEqual(req.agent_id, "agent1")
    
    @patch('staking_client.requests.post')
    def test_stake_success(self, mock_post):
        """Test successful stake."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "task_id": "task_123",
            "status": "accepted",
            "bonded_rtc": 5.0,
            "created_at": "2026-07-07T00:00:00Z",
        }
        mock_post.return_value = mock_response
        
        result = self.client.stake(StakeRequest(skill="test", bond_rtc=5.0))
        self.assertEqual(result.task_id, "task_123")
        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.bonded_rtc, 5.0)
    
    @patch('staking_client.requests.post')
    def test_stake_fail_safe(self, mock_post):
        """Test fail-safe when gate is unavailable."""
        mock_post.side_effect = Exception("Connection refused")
        
        tool = RustChainStakingTool(api_key="test")
        result = tool.stake_and_acquire(skill="test", bond_rtc=1.0)
        
        self.assertTrue(result["stake_refunded"])
        self.assertIn("error", result)


class TestRustChainStakingTool(unittest.TestCase):
    """Test the LangChain Tool wrapper."""
    
    def test_as_langchain_tool(self):
        """Test conversion to LangChain Tool."""
        try:
            tool = RustChainStakingTool(api_key="test")
            lc_tool = tool.as_langchain_tool()
            self.assertEqual(lc_tool.name, "stake_and_acquire")
        except ImportError:
            pass  # langchain not installed in test env
    
    @patch('staking_client.requests.post')
    def test_submit_result(self, mock_post):
        """Test submitting results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "task_id": "task_123",
            "status": "submitted",
        }
        mock_post.return_value = mock_response
        
        tool = RustChainStakingTool(api_key="test")
        result = tool.submit_result(task_id="task_123", result={"quality": 0.95})
        
        self.assertEqual(result["status"], "submitted")


class TestMCPServer(unittest.TestCase):
    """Test the MCP Server."""
    
    def test_tools_list(self):
        """Test tools/list response."""
        from mcp_server import RustChainStakingMCPServer
        server = RustChainStakingMCPServer()
        
        response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        })
        
        tools = response["result"]["tools"]
        self.assertEqual(len(tools), 4)
        self.assertIn("stake_and_acquire", [t["name"] for t in tools])
    
    def test_initialize(self):
        """Test initialize response."""
        from mcp_server import RustChainStakingMCPServer
        server = RustChainStakingMCPServer()
        
        response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
        })
        
        self.assertEqual(response["result"]["serverInfo"]["name"], "rustchain-staking-mcp")


if __name__ == "__main__":
    unittest.main()
