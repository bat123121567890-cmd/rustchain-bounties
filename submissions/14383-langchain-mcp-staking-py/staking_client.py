"""
RustChain Staking Client — Python port of @elyan/staking SDK

Implements the staking gate protocol: stake RTC, submit results,
poll for verdicts, and verify Ed25519-signed attestations.
"""

import requests
import json
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class StakingConfig:
    base_url: str = "https://gate.rustchain.org"
    api_key: Optional[str] = None
    gate_pubkey: Optional[str] = None
    timeout_ms: int = 30000


@dataclass
class StakeRequest:
    skill: str
    bond_rtc: float
    agent_id: Optional[str] = None


@dataclass
class StakeResponse:
    task_id: str
    status: str  # "pending" | "accepted" | "rejected"
    bonded_rtc: float
    created_at: str
    expires_at: Optional[str] = None


@dataclass
class SubmitRequest:
    task_id: str
    result: Dict[str, Any]


@dataclass
class SubmitResponse:
    task_id: str
    status: str  # "submitted" | "verified" | "rejected"
    verdict: Optional[str] = None


@dataclass
class PollResponse:
    task_id: str
    status: str  # "pending" | "processing" | "verified" | "rejected" | "expired"
    verdict: Optional[str] = None
    attestation: Optional[str] = None
    error: Optional[str] = None


@dataclass
class VerifyResult:
    valid: bool
    signer: Optional[str] = None
    error: Optional[str] = None


class StakingError(Exception):
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class StakingAuthError(StakingError):
    def __init__(self, message: str = "Authentication failed — check apiKey"):
        super().__init__(message, "AUTH_ERROR")


class StakingValidationError(StakingError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class StakingClient:
    """RustChain Staking Gate Client"""
    
    def __init__(self, config: Optional[StakingConfig] = None):
        self.config = config or StakingConfig()
        if self.config.api_key:
            self._headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
        else:
            self._headers = {"Content-Type": "application/json"}
    
    def stake(self, request: StakeRequest) -> StakeResponse:
        """Stake RTC for self-improvement on a skill."""
        data = {
            "skill": request.skill,
            "bond_rtc": request.bond_rtc,
        }
        if request.agent_id:
            data["agent_id"] = request.agent_id
        
        result = self._post("/v1/stake", data)
        return StakeResponse(
            task_id=result["task_id"],
            status=result["status"],
            bonded_rtc=result["bonded_rtc"],
            created_at=result["created_at"],
            expires_at=result.get("expires_at"),
        )
    
    def submit(self, request: SubmitRequest) -> SubmitResponse:
        """Submit results for a staked task."""
        result = self._post(f"/v1/tasks/{request.task_id}/submit", {"result": request.result})
        return SubmitResponse(
            task_id=result["task_id"],
            status=result["status"],
            verdict=result.get("verdict"),
        )
    
    def poll(self, task_id: str) -> PollResponse:
        """Poll for verdict on a staked task."""
        result = self._get(f"/v1/tasks/{task_id}")
        return PollResponse(
            task_id=result["task_id"],
            status=result["status"],
            verdict=result.get("verdict"),
            attestation=result.get("attestation"),
            error=result.get("error"),
        )
    
    def verify(self, verdict: str, attestation: str) -> VerifyResult:
        """Verify an Ed25519-signed verdict from the gate."""
        try:
            # Use pure25519 for verification (Termux-compatible)
            from pure25519 import ed25519
            
            # Decode hex strings
            message = bytes.fromhex(verdict)
            signature_bytes = bytes.fromhex(attestation.get("signature", ""))
            pubkey_bytes = bytes.fromhex(self.config.gate_pubkey or "")
            
            valid = ed25519.verify(pubkey_bytes, message, signature_bytes)
            return VerifyResult(valid=valid, signer=self.config.gate_pubkey)
        except Exception as e:
            return VerifyResult(valid=False, error=str(e))
    
    def _get(self, path: str) -> Dict[str, Any]:
        """Make authenticated GET request."""
        url = f"{self.config.base_url.rstrip('/')}{path}"
        r = requests.get(url, headers=self._headers, timeout=self.config.timeout_ms / 1000)
        return self._handle_response(r)
    
    def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated POST request."""
        url = f"{self.config.base_url.rstrip('/')}{path}"
        r = requests.post(url, headers=self._headers, json=data, timeout=self.config.timeout_ms / 1000)
        return self._handle_response(r)
    
    def _handle_response(self, r: requests.Response) -> Dict[str, Any]:
        """Handle HTTP response with error checking."""
        if r.status_code == 401:
            raise StakingAuthError()
        if r.status_code == 422:
            raise StakingValidationError(r.text)
        if not r.ok:
            raise StakingError(f"HTTP {r.status_code}: {r.text}")
        return r.json()
