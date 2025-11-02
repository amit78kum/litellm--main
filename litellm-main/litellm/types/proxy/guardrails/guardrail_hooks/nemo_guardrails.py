from typing import Optional

from pydantic import Field

from .base import GuardrailConfigModel


class NemoGuardrailsConfigModel(GuardrailConfigModel):
    """Configuration model for NeMo Guardrails"""
    
    config_path: Optional[str] = Field(
        default=None,
        description="Path to the NeMo Guardrails configuration directory containing config.yml, rails.co, and actions.py. If not provided, defaults to './nemo_config'.",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description="The LLM model to use for NeMo Guardrails (e.g., 'gemini/gemini-2.5-flash-lite'). If not provided, uses the model specified in config.yml.",
    )
    llm_api_key: Optional[str] = Field(
        default=None,
        description="API key for the LLM model. Can be provided directly or via environment variables.",
    )
    
    @staticmethod
    def ui_friendly_name() -> str:
        return "NeMo Guardrails"