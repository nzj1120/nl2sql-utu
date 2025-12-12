"""
LLM gateway abstraction with a stub implementation for offline runs.
"""

from typing import Any


class LLMClient:
    """
    Base LLM client interface. Replace with your own gateway implementation.
    """

    def chat(self, prompt: str, **kwargs: Any) -> str:
        """
        Send a prompt and return the raw string response.
        """
        raise NotImplementedError("chat must be implemented by subclasses")


class EchoLLMClient(LLMClient):
    """
    Simple LLM stub that echoes instructions or produces deterministic defaults.
    """

    def chat(self, prompt: str, **kwargs: Any) -> str:
        """
        Produce a predictable response for testing without external LLMs.
        """
        if "Allowed actions" in prompt:
            return '[{"type": "stop_action"}]'
        return "SELECT 1;"
