"""
LangChain Tool wrapper for RustChain Staking SDK

Usage:
    from langchain.tools import Tool
    from langchain_tool import RustChainStakingTool
    
    tool = RustChainStakingTool(api_key="your_key")
    # Use with LangChain agent
    agent = initialize_agent([tool.as_langchain_tool()], llm, ...)
"""

from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, Field
from staking_client import (
    StakingClient, StakingConfig, StakeRequest, 
    SubmitRequest, PollResponse
)


class StakeAndAcquireInput(BaseModel):
    """Input schema for stake_and_acquire tool."""
    skill: str = Field(
        description="Skill or domain identifier to stake on (e.g., 'code-review', 'bug-hunting')"
    )
    bond_rtc: float = Field(
        description="Amount of RTC to bond as stake",
        gt=0
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="Optional agent/wallet identifier"
    )


class RustChainStakingTool:
    """
    LangChain Tool for RustChain staked self-improvement.
    
    Wraps the staking gate protocol:
    1. Stake RTC on a skill
    2. Submit results for verification
    3. Poll for verdict
    4. Return verified attestation
    
    Fail-safe: if gate is unavailable, stake is returned to the caller.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://gate.rustchain.org",
        gate_pubkey: Optional[str] = None,
    ):
        self.client = StakingClient(StakingConfig(
            base_url=base_url,
            api_key=api_key,
            gate_pubkey=gate_pubkey,
        ))
    
    def stake_and_acquire(self, skill: str, bond_rtc: float, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Stake RTC on a skill and acquire self-improvement verification.
        
        Args:
            skill: Skill/domain to stake on
            bond_rtc: RTC amount to bond
            agent_id: Optional agent identifier
            
        Returns:
            Dict with task_id, status, and staking details
            
        Fail-safe: If gate is unavailable, returns stake_refunded=True
        """
        try:
            response = self.client.stake(StakeRequest(
                skill=skill,
                bond_rtc=bond_rtc,
                agent_id=agent_id,
            ))
            return {
                "task_id": response.task_id,
                "status": response.status,
                "bonded_rtc": response.bonded_rtc,
                "created_at": response.created_at,
                "stake_refunded": False,
            }
        except Exception as e:
            # Fail-safe: gate unavailable → stake returned
            return {
                "error": str(e),
                "stake_refunded": True,
                "message": "Gate unavailable. Stake returned to caller."
            }
    
    def submit_result(self, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit results for a staked task.
        
        Args:
            task_id: Task ID from stake_and_acquire
            result: Result payload (freeform, depends on skill)
            
        Returns:
            Dict with submission status and verdict
        """
        try:
            response = self.client.submit(SubmitRequest(
                task_id=task_id,
                result=result,
            ))
            return {
                "task_id": response.task_id,
                "status": response.status,
                "verdict": response.verdict,
            }
        except Exception as e:
            return {"error": str(e), "stake_refunded": True}
    
    def poll_verdict(self, task_id: str) -> Dict[str, Any]:
        """
        Poll for verdict on a staked task.
        
        Args:
            task_id: Task ID to poll
            
        Returns:
            Dict with verdict status and attestation
        """
        try:
            response = self.client.poll(task_id)
            return {
                "task_id": response.task_id,
                "status": response.status,
                "verdict": response.verdict,
                "attestation": response.attestation,
                "error": response.error,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def as_langchain_tool(self):
        """Return as a LangChain Tool object."""
        try:
            from langchain.tools import Tool
        except ImportError:
            try:
                from langchain_core.tools import Tool
            except ImportError:
                raise ImportError("langchain or langchain-core not installed. Install with: pip install langchain")
        
        return Tool(
            name="stake_and_acquire",
            description=(
                "Stake RTC on a skill for self-improvement verification. "
                "Returns task_id for tracking. If gate is unavailable, stake is refunded. "
                "Use submit_result to provide work, then poll_verdict for the verdict."
            ),
            func=lambda skill, bond_rtc, agent_id=None: self.stake_and_acquire(skill, bond_rtc, agent_id),
            args_schema=StakeAndAcquireInput,
        )
