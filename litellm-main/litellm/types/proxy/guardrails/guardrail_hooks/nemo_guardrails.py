from typing import Optional

from pydantic import Field

from .base import GuardrailConfigModel


class NemoGuardrailsConfigModel(GuardrailConfigModel):
    """Configuration model for NeMo Guardrails API integration"""
    
    guardrails_url: Optional[str] = Field(
        default="http://localhost:8000",
        description="URL of the NeMo Guardrails API server (default: http://localhost:8000)",
    )
    config_id: Optional[str] = Field(
        default=None,
        description="Configuration ID to use from the guardrails server. If not provided, uses the first available config.",
    )
    timeout: Optional[int] = Field(
        default=30,
        description="Request timeout in seconds for API calls (default: 30)",
    )
    
    @staticmethod
    def ui_friendly_name() -> str:
        return "NeMo Guardrails"