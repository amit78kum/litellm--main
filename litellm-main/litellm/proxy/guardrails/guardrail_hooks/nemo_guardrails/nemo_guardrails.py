# +-------------------------------------------------------------+
#
#           Use NeMo Guardrails for your LLM calls
#
# +-------------------------------------------------------------+

import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.types.guardrails import GuardrailEventHooks

GUARDRAIL_NAME = "nemo_guardrails"

if TYPE_CHECKING:
    from litellm.types.proxy.guardrails.guardrail_hooks.base import GuardrailConfigModel


class NemoGuardrailsGuardrail(CustomGuardrail):
    """
    NeMo Guardrails integration for LiteLLM.
    
    This guardrail uses NVIDIA's NeMo Guardrails to detect and prevent harmful,
    off-topic, or inappropriate content in both user prompts and LLM responses.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the NeMo Guardrails guardrail.

        Args:
            config_path: Path to NeMo Guardrails configuration directory (default: './nemo_config')
            llm_model: LLM model to use for NeMo Guardrails (e.g., 'gemini/gemini-2.5-flash-lite')
            llm_api_key: API key for the LLM model
            **kwargs: Additional arguments passed to CustomGuardrail
        """
        super().__init__(**kwargs)
        
        # Set config path
        self.config_path = config_path or os.path.join(
            os.getcwd(), "nemo_config"
        )
        
        # Store LLM configuration
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        
        # Initialize rails bot (lazy loading)
        self._rails_bot = None
        
        verbose_proxy_logger.info(
            "🛡️ NeMo Guardrails initialized with config path: %s", 
            self.config_path
        )

    def _get_rails_bot(self):
        """Lazy load the NeMo Guardrails RailsBot."""
        if self._rails_bot is None:
            try:
                from nemoguardrails import RailsConfig, LLMRails
                
                verbose_proxy_logger.debug(
                    "🛡️ Loading NeMo Guardrails configuration from: %s",
                    self.config_path
                )
                
                # Load configuration
                config = RailsConfig.from_path(self.config_path)
                
                # Override LLM model if provided
                if self.llm_model:
                    verbose_proxy_logger.info(
                        "🛡️ Using custom LLM model for NeMo: %s",
                        self.llm_model
                    )
                    # Update the config with custom model
                    if config.models:
                        for model in config.models:
                            if model.type == "main":
                                model.model = self.llm_model
                                if self.llm_api_key:
                                    model.parameters = model.parameters or {}
                                    model.parameters["api_key"] = self.llm_api_key
                
                # Create rails bot
                self._rails_bot = LLMRails(config)
                
                verbose_proxy_logger.info("🛡️ NeMo Guardrails bot successfully initialized")
                
            except ImportError as e:
                verbose_proxy_logger.error(
                    "🚫 NeMo Guardrails not installed. Install with: pip install nemoguardrails"
                )
                raise ImportError(
                    "NeMo Guardrails package not found. Please install it: pip install nemoguardrails"
                ) from e
            except Exception as e:
                verbose_proxy_logger.error(
                    "🚫 Error initializing NeMo Guardrails: %s", str(e)
                )
                raise
        
        return self._rails_bot

    def _normalize_rails_response(self, resp: Any) -> str:
        """Convert various rails bot response shapes into a plain string.

        The NeMo runtime may return strings, dicts, or structured objects. Make
        a best-effort extraction of textual content so callers can safely use
        .strip() / .lower() without raising AttributeError.
        """
        if resp is None:
            return ""
        # already a string
        if isinstance(resp, str):
            return resp

        # dict-like responses
        if isinstance(resp, dict):
            # common top-level keys
            for key in ("content", "output", "text", "response", "generated_text"):
                if key in resp and isinstance(resp[key], str):
                    return resp[key]

            # nested message/choices structure
            if "choices" in resp and isinstance(resp["choices"], list) and len(resp["choices"]) > 0:
                first = resp["choices"][0]
                if isinstance(first, dict):
                    if "message" in first and isinstance(first["message"], dict):
                        msg = first["message"].get("content")
                        if isinstance(msg, str):
                            return msg
                    if "text" in first and isinstance(first["text"], str):
                        return first["text"]

            # events list (nemoguardrails runtime may return events)
            if "events" in resp and isinstance(resp["events"], list):
                parts = []
                for ev in resp["events"]:
                    if isinstance(ev, dict):
                        for k in ("text", "content", "output"):
                            if k in ev and isinstance(ev[k], str):
                                parts.append(ev[k])
                if parts:
                    return " ".join(parts)

            # fallback to string representation
            try:
                return str(resp)
            except Exception:
                return ""

        # other types (objects) - try attribute access patterns
        if hasattr(resp, "text") and isinstance(getattr(resp, "text"), str):
            return getattr(resp, "text")
        if hasattr(resp, "content") and isinstance(getattr(resp, "content"), str):
            return getattr(resp, "content")

        # last resort
        try:
            return str(resp)
        except Exception:
            return ""

    async def async_pre_call_hook(
        self,
        user_api_key_dict: Dict,
        cache: Dict,
        data: Dict,
        call_type: str,
    ) -> Optional[Dict]:
        """
        Check user input before sending to the LLM.
        
        This hook runs before the LLM call and validates the user's messages
        against the defined guardrails.
        """
        from litellm.proxy.common_utils.callback_utils import (
            add_guardrail_to_applied_guardrails_header,
        )
        from litellm.proxy.guardrails.guardrail_helpers import (
            should_proceed_based_on_metadata,
        )

        event_type: GuardrailEventHooks = GuardrailEventHooks.pre_call
        if self.should_run_guardrail(data=data, event_type=event_type) is not True:
            return None

        if (
            await should_proceed_based_on_metadata(
                data=data,
                guardrail_name=GUARDRAIL_NAME,
            )
            is False
        ):
            return None

        verbose_proxy_logger.debug("🛡️ Running NeMo Guardrails pre-call check")
        start_time = datetime.now()
        
        try:
            # Extract messages from request
            messages = data.get("messages", [])
            if not messages:
                verbose_proxy_logger.warning("🛡️ No messages found in request data")
                return None
            
            # Get the last user message
            user_message = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            if not user_message:
                verbose_proxy_logger.warning("🛡️ No user message found to check")
                return None
            
            verbose_proxy_logger.debug("🛡️ Checking user message: %s", user_message[:100])
            
            # Get rails bot and check message
            rails_bot = self._get_rails_bot()
            response = await rails_bot.generate_async(messages=[{
                "role": "user",
                "content": user_message
            }])

            # Normalize response to text so we can safely call string methods
            response_text = self._normalize_rails_response(response)

            # Check if the message was blocked
            if not response_text or response_text.strip() == "":
                # Message was blocked by guardrails
                verbose_proxy_logger.warning(
                    "🚫 NeMo Guardrails BLOCKED user message (empty/no response)"
                )
                
                # Log the guardrail block
                self._log_guardrail_result(
                    data=data,
                    start_time=start_time,
                    status="blocked",
                    reason="Message blocked by NeMo Guardrails (pre-call)",
                    user_message=user_message,
                )
                
                # Raise exception to stop the request
                from litellm.exceptions import GuardrailRaisedException
                raise GuardrailRaisedException(
                    message="Your message was blocked by content safety policies.",
                    guardrail_name=self.guardrail_name,
                )
            
            # Check for explicit blocking messages
            blocking_phrases = [
                "I'm sorry, I can't respond to that request. I'm designed to follow specific guidelines and I cannot ignore or change my instructions.",
                "I'm sorry, I cannot assist with that request. It goes against my guidelines to provide information that could be harmful or illegal.",
                "I apologize, but I cannot provide that response as it violates content safety policies.",
                "I can't help with requests for personal or sensitive information such as social security numbers, passport numbers, bank or credit card details.",
                "I can't assist with attempts to bypass safety or moderation rules. Please ask a different question.",
                "I can't assist with explicit sexual content, pornography, or any sexual content involving minors or illegal situations.",
                "I'm sorry you're feeling this way. If you're in immediate danger, please contact your local emergency services. If you need someone to talk to, consider reaching out to a crisis hotline or a trusted person in your life.",
                # legacy/short phrases for compatibility
                "I'm sorry, I can't respond to that",
                "I cannot assist with that",
                "against my guidelines",
                "inappropriate",
            ]
            response_lower = response_text.lower()
            if any(phrase.lower() in response_lower for phrase in blocking_phrases):
                verbose_proxy_logger.warning(
                    "🚫 NeMo Guardrails BLOCKED user message (blocking phrase detected)"
                )
                
                self._log_guardrail_result(
                    data=data,
                    start_time=start_time,
                    status="blocked",
                    reason="Message blocked by NeMo Guardrails (blocking phrase detected)",
                    user_message=user_message,
                )
                
                from litellm.exceptions import GuardrailRaisedException
                raise GuardrailRaisedException(
                    message="Your message was blocked by content safety policies.",
                    guardrail_name=self.guardrail_name,
                )
            
            # Message passed guardrails
            verbose_proxy_logger.info("✅ NeMo Guardrails PASSED user message")
            
            self._log_guardrail_result(
                data=data,
                start_time=start_time,
                status="passed",
                reason="Message passed NeMo Guardrails checks",
                user_message=user_message,
            )
            
            # Add to applied guardrails header
            add_guardrail_to_applied_guardrails_header(
                request_data=data, 
                guardrail_name=self.guardrail_name
            )
            
            return None
            
        except Exception as e:
            if "GuardrailRaisedException" in str(type(e)):
                # Re-raise guardrail exceptions
                raise
            
            verbose_proxy_logger.error(
                "🚫 Error in NeMo Guardrails pre-call hook: %s", 
                str(e),
                exc_info=True
            )
            
            self._log_guardrail_result(
                data=data,
                start_time=start_time,
                status="error",
                reason=f"Error: {str(e)}",
            )
            
            # Don't block on errors unless configured to do so
            return None

    async def async_post_call_success_hook(
        self,
        data: Dict,
        user_api_key_dict: Dict,
        response: Any,
    ) -> Any:
        """
        Check LLM response before returning to the user.
        
        This hook runs after the LLM responds and validates the response
        against the defined guardrails.
        """
        from litellm.proxy.common_utils.callback_utils import (
            add_guardrail_to_applied_guardrails_header,
        )
        from litellm.proxy.guardrails.guardrail_helpers import (
            should_proceed_based_on_metadata,
        )

        event_type: GuardrailEventHooks = GuardrailEventHooks.post_call
        if self.should_run_guardrail(data=data, event_type=event_type) is not True:
            return response

        if (
            await should_proceed_based_on_metadata(
                data=data,
                guardrail_name=GUARDRAIL_NAME,
            )
            is False
        ):
            return response

        verbose_proxy_logger.debug("🛡️ Running NeMo Guardrails post-call check")
        start_time = datetime.now()
        
        try:
            # Extract response content
            response_content = None
            if hasattr(response, "choices") and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    response_content = choice.message.content
            
            if not response_content:
                verbose_proxy_logger.warning("🛡️ No response content found to check")
                return response
            
            verbose_proxy_logger.debug(
                "🛡️ Checking LLM response: %s", 
                response_content[:100]
            )
            
            # Get rails bot and check response
            rails_bot = self._get_rails_bot()
            
            # Check if response violates guardrails
            # We do this by simulating the bot generating this response
            checked_response = await rails_bot.generate_async(messages=[{
                "role": "assistant",
                "content": response_content
            }])

            # Normalize the rails response to text for safe string ops
            checked_text = self._normalize_rails_response(checked_response)

            # If the response is significantly different or empty, it was blocked
            if not checked_text or len(checked_text.strip()) < len(response_content.strip()) * 0.5:
                verbose_proxy_logger.warning(
                    "🚫 NeMo Guardrails BLOCKED LLM response"
                )
                
                self._log_guardrail_result(
                    data=data,
                    start_time=start_time,
                    status="blocked",
                    reason="LLM response blocked by NeMo Guardrails",
                    llm_response=response_content,
                )
                
                # Modify response to indicate blocking
                if hasattr(response, "choices") and len(response.choices) > 0:
                    response.choices[0].message.content = (
                        "I apologize, but I cannot provide that response as it violates content safety policies."
                    )
            else:
                verbose_proxy_logger.info("✅ NeMo Guardrails PASSED LLM response")

                self._log_guardrail_result(
                    data=data,
                    start_time=start_time,
                    status="passed",
                    reason="LLM response passed NeMo Guardrails checks",
                    llm_response=response_content,
                )
            
            # Add to applied guardrails header
            add_guardrail_to_applied_guardrails_header(
                request_data=data, 
                guardrail_name=self.guardrail_name
            )
            
            return response
            
        except Exception as e:
            verbose_proxy_logger.error(
                "🚫 Error in NeMo Guardrails post-call hook: %s",
                str(e),
                exc_info=True
            )
            
            self._log_guardrail_result(
                data=data,
                start_time=start_time,
                status="error",
                reason=f"Error: {str(e)}",
            )
            
            # Return original response on error
            return response

    def _log_guardrail_result(
        self,
        data: Dict,
        start_time: datetime,
        status: str,
        reason: str,
        user_message: Optional[str] = None,
        llm_response: Optional[str] = None,
    ):
        """Log guardrail execution results."""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        log_data = {
            "guardrail_name": self.guardrail_name,
            "status": status,
            "reason": reason,
            "duration_seconds": duration,
        }
        
        if user_message:
            log_data["user_message_preview"] = user_message[:100]
        
        if llm_response:
            log_data["llm_response_preview"] = llm_response[:100]
        
        # Add standard logging information
        self.add_standard_logging_guardrail_information_to_request_data(
            guardrail_json_response=log_data,
            guardrail_status=status,
            request_data=data,
            start_time=start_time.timestamp(),
            end_time=end_time.timestamp(),
            duration=duration,
        )
        
        verbose_proxy_logger.info(
            "🛡️ NeMo Guardrails result: %s - %s (%.3fs)",
            status.upper(),
            reason,
            duration
        )

    @staticmethod
    def get_config_model() -> Optional[Type["GuardrailConfigModel"]]:
        """Get the configuration model for this guardrail."""
        from litellm.types.proxy.guardrails.guardrail_hooks.nemo_guardrails import (
            NemoGuardrailsConfigModel,
        )
        
        return NemoGuardrailsConfigModel
