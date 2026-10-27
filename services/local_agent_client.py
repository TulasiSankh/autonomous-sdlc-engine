"""Client for communicating securely with the Windows Local Agent service."""

import logging
import os
from typing import Any, Dict, List, Optional
import httpx

from local_agent.config import DEFAULT_HOST, DEFAULT_PORT, get_or_create_token

logger = logging.getLogger("services.local_agent_client")


class LocalAgentOfflineError(Exception):
    """Raised when the Orbit AI Windows Local Agent service is not running or unreachable."""
    pass


class LocalAgentAuthError(Exception):
    """Raised when communication with the local agent fails authentication."""
    pass


class LocalAgentExecutionError(Exception):
    """Raised when a local action fails execution."""
    pass


class LocalAgentClient:
    """REST client connecting the Orbit AI backend to the Windows Local Agent."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        host = os.getenv("ORBIT_AGENT_HOST", DEFAULT_HOST)
        port = os.getenv("ORBIT_AGENT_PORT", str(DEFAULT_PORT))
        self.base_url = (base_url or f"http://{host}:{port}").rstrip("/")
        self.token = token or get_or_create_token()
        self.timeout = timeout_seconds

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Orbit-Agent-Token": self.token,
            "Content-Type": "application/json",
            "User-Agent": "Orbit-AI-Backend/1.0",
        }

    def is_online(self) -> bool:
        """Checks if the local agent service is responding to health pings."""
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(f"{self.base_url}/health")
                if res.status_code == 200:
                    data = res.json()
                    return data.get("status") == "online"
        except Exception:
            pass
        return False

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Retrieves lightweight status and environment metadata from local agent."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/health")
                if res.status_code == 200:
                    return res.json()
        except Exception as e:
            logger.debug(f"Local agent not responding to health check: {e}")
        return None

    def discover_app(self, app_name: str) -> Dict[str, Any]:
        """Requests application discovery from the local agent."""
        if not self.is_online():
            raise LocalAgentOfflineError(
                "Orbit AI Windows Local Agent is offline. "
                "Please start the service using 'python start_local_agent.py'."
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(
                    f"{self.base_url}/apps/discover",
                    json={"app_name": app_name},
                    headers=self._headers(),
                )
                if res.status_code == 401:
                    raise LocalAgentAuthError("Local agent rejected pairing token.")
                res.raise_for_status()
                return res.json()
        except httpx.RequestError as exc:
            raise LocalAgentOfflineError(f"Could not reach local agent: {exc}") from exc

    def check_app_running(self, app_name: str) -> Dict[str, Any]:
        """Checks if an application is active in the Windows process table."""
        if not self.is_online():
            raise LocalAgentOfflineError(
                "Orbit AI Windows Local Agent is offline. "
                "Please start the service using 'python start_local_agent.py'."
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(
                    f"{self.base_url}/apps/running",
                    json={"app_name": app_name},
                    headers=self._headers(),
                )
                if res.status_code == 401:
                    raise LocalAgentAuthError("Local agent rejected pairing token.")
                res.raise_for_status()
                return res.json()
        except httpx.RequestError as exc:
            raise LocalAgentOfflineError(f"Could not reach local agent: {exc}") from exc

    def execute_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a controlled action via the local Windows agent."""
        if not self.is_online():
            raise LocalAgentOfflineError(
                "Orbit AI Windows Local Agent is offline. "
                "Please start the service using 'python start_local_agent.py'."
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(
                    f"{self.base_url}/actions/execute",
                    json={"action": action, "parameters": parameters},
                    headers=self._headers(),
                )
                if res.status_code == 401:
                    raise LocalAgentAuthError("Local agent rejected pairing token.")
                res.raise_for_status()
                return res.json()
        except httpx.RequestError as exc:
            raise LocalAgentOfflineError(f"Failed to communicate with local agent: {exc}") from exc


_client_instance: Optional[LocalAgentClient] = None


def get_local_agent_client() -> LocalAgentClient:
    """Returns singleton LocalAgentClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = LocalAgentClient()
    return _client_instance
