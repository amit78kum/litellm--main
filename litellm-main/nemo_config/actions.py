# NeMo Guardrails - Custom Actions
# This file defines custom Python actions that can be used in rails
from typing import Optional
from nemoguardrails.actions import action
@action(is_system_action=True)
async def check_input_safety(context: Optional[dict] = None):
    """
    Custom action to check if user input is safe.
    This is a placeholder for more sophisticated safety checks.
    You can integrate with external APIs or models here.
    """
    if context is None:
        context = {}
    user_message = context.get("user_message", "")
    # Simple keyword-based checks (expand as needed)
    unsafe_keywords = [
        "hack",
        "exploit",
        "vulnerability",
        "malware",
        "bomb",
        "weapon",
        "illegal",
        "drugs",
    ]
    user_message_lower = user_message.lower()
    for keyword in unsafe_keywords:
        if keyword in user_message_lower:
            return {
                "is_safe": False,
                "reason": f"Detected potentially unsafe keyword: {keyword}"
            }
    return {
        "is_safe": True,
        "reason": "Input passed safety checks"
    }
@action(is_system_action=True)
async def check_output_safety(context: Optional[dict] = None):
    """
    Custom action to check if bot output is safe.
    This is a placeholder for more sophisticated safety checks on bot responses.
    """
    if context is None:
        context = {}
    bot_message = context.get("bot_message", "")
    # Simple checks for sensitive information
    sensitive_patterns = [
        "password",
        "credit card",
        "social security",
        "api key",
        "secret key",
    ]
    bot_message_lower = bot_message.lower()
    for pattern in sensitive_patterns:
        if pattern in bot_message_lower:
            return {
                "is_safe": False,
                "reason": f"Detected sensitive information: {pattern}"
            }
    return {
        "is_safe": True,
        "reason": "Output passed safety checks"
    }
@action(is_system_action=True)
async def log_guardrail_event(context: Optional[dict] = None):
    """
    Log guardrail events for monitoring and analysis.
    This action can be extended to log to external systems,
    databases, or monitoring platforms.
    """
    if context is None:
        context = {}
    event_type = context.get("event_type", "unknown")
    message = context.get("message", "")
    # In production, you might want to log to a file, database, or monitoring service
    print(f"[NeMo Guardrails] Event: {event_type} | Message: {message[:100]}")
    return {"logged": True}
@action()
async def retrieve_relevant_chunks(context: Optional[dict] = None):
    """
    Custom action for RAG (Retrieval-Augmented Generation).
    This is a placeholder that can be extended to integrate with
    vector databases or knowledge bases.
    """
    if context is None:
        context = {}
    # Placeholder - implement your RAG logic here
    return {
        "chunks": [],
        "message": "RAG not implemented"
    }