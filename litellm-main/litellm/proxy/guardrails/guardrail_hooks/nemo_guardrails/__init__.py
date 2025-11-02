from typing import TYPE_CHECKING

from litellm.types.guardrails import SupportedGuardrailIntegrations

from .nemo_guardrails import NemoGuardrailsGuardrail

if TYPE_CHECKING:
    from litellm.types.guardrails import Guardrail, LitellmParams


def initialize_guardrail(litellm_params: "LitellmParams", guardrail: "Guardrail"):
    """
    Initialize NeMo Guardrails guardrail.
    
    Args:
        litellm_params: Parameters for the guardrail
        guardrail: Guardrail configuration dictionary
    
    Returns:
        Initialized NemoGuardrailsGuardrail instance
    """
    import litellm

    _nemo_callback = NemoGuardrailsGuardrail(
        config_path=getattr(litellm_params, "config_path", None),
        llm_model=getattr(litellm_params, "llm_model", None),
        llm_api_key=getattr(litellm_params, "llm_api_key", None),
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=litellm_params.mode,
        default_on=litellm_params.default_on,
    )
    litellm.logging_callback_manager.add_litellm_callback(_nemo_callback)

    return _nemo_callback


# Register this guardrail
guardrail_initializer_registry = {
    "nemo_guardrails": initialize_guardrail,
}

# Register the guardrail class for config model discovery
guardrail_class_registry = {
    "nemo_guardrails": NemoGuardrailsGuardrail,
}