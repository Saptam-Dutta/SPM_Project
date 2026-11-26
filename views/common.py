"""Shared helpers for every page."""
from dataclasses import dataclass


@dataclass
class AIConfig:
    provider: str
    api_key: str
    model: str
    base_url: str = ""

    @property
    def ready(self) -> bool:
        return bool(self.api_key.strip() and self.model.strip())

    def missing_message(self) -> str:
        return f"Enter your {self.provider} API key (and a model) in the sidebar first."
