
# # +-------------------------------------------------------------+
# #
# #           Use NeMo Guardrails API for your LLM calls
# #
# # +-------------------------------------------------------------+
# import os
# import sys
# from datetime import datetime
# from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

# import requests
# from litellm._logging import verbose_proxy_logger
# from litellm.integrations.custom_guardrail import CustomGuardrail
# from litellm.types.guardrails import GuardrailEventHooks

# GUARDRAIL_NAME = "nemo_guardrails"

# if TYPE_CHECKING:
#     from litellm.types.proxy.guardrails.guardrail_hooks.base import GuardrailConfigModel


# class NemoGuardrailsGuardrail(CustomGuardrail):
#     """
#     NeMo Guardrails API integration for LiteLLM.
    
#     This guardrail uses NVIDIA's NeMo Guardrails API to detect and prevent harmful,
#     off-topic, or inappropriate content in both user prompts and LLM responses.
#     """

#     def __init__(
#         self,
#         guardrails_url: Optional[str] = None,
#         config_id: Optional[str] = None,
#         timeout: int = 30,
#         **kwargs,
#     ):
#         """
#         Initialize the NeMo Guardrails API guardrail.

#         Args:
#             guardrails_url: URL of the NeMo Guardrails API (default: 'http://localhost:8000')
#             config_id: Configuration ID to use. If None, will use the first available config
#             timeout: Request timeout in seconds (default: 30)
#             **kwargs: Additional arguments passed to CustomGuardrail
#         """
#         super().__init__(**kwargs)
        
#         # Set API URL with default fallback
#         self.guardrails_url = guardrails_url  or "http://localhost:8000"
       
#         self.timeout = timeout
        
#         # Config ID (will be fetched if not provided)
#         self._config_id = config_id
#         self._configs_cache = None
        
#         verbose_proxy_logger.info(
#             "🛡️ NeMo Guardrails API initialized with URL: %s", 
#             self.guardrails_url
#         )

#     def _get_config_id(self) -> str:
#         """Get the config ID to use for guardrail checks."""
#         if self._config_id:
#             return self._config_id
        
#         # Fetch available configs if not cached
#         if self._configs_cache is None:
#             try:
#                 verbose_proxy_logger.debug(
#                     "🛡️ Fetching available NeMo Guardrails configurations"
#                 )
#                 response = requests.get(
#                     f"{self.guardrails_url}/v1/rails/configs",
#                     timeout=self.timeout
#                 )
#                 response.raise_for_status()
#                 self._configs_cache = response.json()
                
#                 verbose_proxy_logger.info(
#                     "🛡️ Found %d NeMo Guardrails configurations",
#                     len(self._configs_cache)
#                 )
#             except Exception as e:
#                 verbose_proxy_logger.error(
#                     "🚫 Error fetching NeMo Guardrails configs: %s", str(e)
#                 )
#                 raise
        
#         if not self._configs_cache or len(self._configs_cache) == 0:
#             raise ValueError("No NeMo Guardrails configurations available")
        
#         # Use the first available config
#         config_id = self._configs_cache[0].get("id")
#         if not config_id:
#             raise ValueError("Config ID not found in response")
        
#         verbose_proxy_logger.debug("🛡️ Using config ID: %s", config_id)
#         return config_id

#     def _check_message_with_api(self, messages: List[Dict]) -> Dict:
#         """
#         Send messages to the NeMo Guardrails API for checking.
        
#         Args:
#             messages: List of message dictionaries with 'role' and 'content'
            
#         Returns:
#             API response as dictionary
#         """
#         config_id = self._get_config_id()
        
#         try:
#             response = requests.post(
#                 f"{self.guardrails_url}/v1/chat/completions",
#                 json={
#                     "config_id": config_id,
#                     "messages": messages
#                 },
#                 timeout=self.timeout
#             )
#             response.raise_for_status()
#             verbose_proxy_logger.error(response.json())
#             return response.json()
#         except requests.exceptions.Timeout:
#             verbose_proxy_logger.error("🚫 NeMo Guardrails API request timed out")
#             raise
#         except requests.exceptions.RequestException as e:
#             verbose_proxy_logger.error(
#                 "🚫 NeMo Guardrails API request failed: %s", str(e)
#             )
#             raise

#     def _is_message_blocked(self, api_response: Dict) -> tuple[bool, Optional[str], Optional[str]]:
#         """
#         Determine if a message was blocked based on API response.
        
#         Returns:
#             Tuple of (is_blocked, reason, policy_id)
#         """
#         # Check for empty or error responses
#         if not api_response:
#             return True, "Empty response from guardrails API", None
        
#         # NeMo Guardrails API returns violations/alerts when content is blocked
#         # If there are no violations, the message is allowed
#         violations = api_response.get("violations", [])
#         alerts = api_response.get("alerts", [])
        
#         # If there are violations, the message is blocked
#         if violations and len(violations) > 0:
#             violation = violations[0]
#             reason = violation.get("message") or f"Violation: {violation.get('type', 'unknown')}"
#             policy_id = violation.get("id") or violation.get("type")
#             return True, reason, policy_id
        
#         # If there are alerts, the message may be flagged but not necessarily blocked
#         if alerts and len(alerts) > 0:
#             alert = alerts[0]
#             reason = alert.get("message") or f"Alert: {alert.get('type', 'unknown')}"
#             policy_id = alert.get("id") or alert.get("type")
#             # Treat high-severity alerts as blocks; otherwise allow
#             if alert.get("severity") in ["high", "critical", "block"]:
#                 return True, reason, policy_id
        
#         # No violations or alerts - message is allowed
#         return False, None, None

#     async def async_pre_call_hook(
#         self,
#         user_api_key_dict: Dict,
#         cache: Dict,
#         data: Dict,
#         call_type: str,
#     ) -> Optional[Dict]:
#         """
#         Check user input before sending to the LLM.
        
#         This hook runs before the LLM call and validates the user's messages
#         against the defined guardrails via the API.
#         """
#         from litellm.proxy.common_utils.callback_utils import (
#             add_guardrail_to_applied_guardrails_header,
#         )
#         from litellm.proxy.guardrails.guardrail_helpers import (
#             should_proceed_based_on_metadata,
#         )

#         event_type: GuardrailEventHooks = GuardrailEventHooks.pre_call
#         if self.should_run_guardrail(data=data, event_type=event_type) is not True:
#             return None

#         if (
#             await should_proceed_based_on_metadata(
#                 data=data,
#                 guardrail_name=GUARDRAIL_NAME,
#             )
#             is False
#         ):
#             return None

#         verbose_proxy_logger.debug("🛡️ Running NeMo Guardrails API pre-call check")
#         start_time = datetime.now()
        
#         try:
#             # Extract messages from request
#             messages = data.get("messages", [])
#             if not messages:
#                 verbose_proxy_logger.warning("🛡️ No messages found in request data")
#                 return None
            
#             # Get the last user message
#             user_message = None
#             for msg in reversed(messages):
#                 if msg.get("role") == "user":
#                     user_message = msg.get("content", "")
#                     break
            
#             if not user_message:
#                 verbose_proxy_logger.warning("🛡️ No user message found to check")
#                 return None
            
#             verbose_proxy_logger.debug("🛡️ Checking user message: %s", user_message[:100])
            
#             # Check message via API
#             api_response = self._check_message_with_api([{
#                 "role": "user",
#                 "content": user_message
#             }])
            
#             # Check if message was blocked
#             is_blocked, reason, policy_id = self._is_message_blocked(api_response)
            
#             if is_blocked:
#                 verbose_proxy_logger.warning(
#                     "🚫 NeMo Guardrails BLOCKED user message: %s", reason
#                 )
                
#                 self._log_guardrail_result(
#                     data=data,
#                     start_time=start_time,
#                     status="blocked",
#                     reason=f"Message blocked by NeMo Guardrails: {reason}",
#                     user_message=user_message,
#                     policy_id=policy_id,
#                 )
                
#                 # Raise exception to stop the request
#                 from litellm.exceptions import GuardrailRaisedException
#                 # Include the violating policy (if available) in the exception message so the dashboard can surface it
#                 exc_message = "Your message was blocked by content safety policies."
#                 if policy_id:
#                     exc_message = f"{exc_message} Policy: {policy_id}"
#                 raise GuardrailRaisedException(
#                     message=exc_message,
#                     guardrail_name=self.guardrail_name,
#                 )
            
#             # Message passed guardrails
#             verbose_proxy_logger.info("✅ NeMo Guardrails PASSED user message")
            
#             self._log_guardrail_result(
#                 data=data,
#                 start_time=start_time,
#                 status="passed",
#                 reason="Message passed NeMo Guardrails checks",
#                 user_message=user_message,
#             )
            
#             # Add to applied guardrails header
#             add_guardrail_to_applied_guardrails_header(
#                 request_data=data, 
#                 guardrail_name=self.guardrail_name
#             )
            
#             return None
            
#         except Exception as e:
#             if "GuardrailRaisedException" in str(type(e)):
#                 # Re-raise guardrail exceptions
#                 raise
            
#             verbose_proxy_logger.error(
#                 "🚫 Error in NeMo Guardrails pre-call hook: %s", 
#                 str(e),
#                 exc_info=True
#             )
            
#             self._log_guardrail_result(
#                 data=data,
#                 start_time=start_time,
#                 status="error",
#                 reason=f"Error: {str(e)}",
#             )
            
#             # Don't block on errors unless configured to do so
#             return None

#     async def async_post_call_success_hook(
#         self,
#         data: Dict,
#         user_api_key_dict: Dict,
#         response: Any,
#     ) -> Any:
#         """
#         Check LLM response before returning to the user.
        
#         This hook runs after the LLM responds and validates the response
#         against the defined guardrails via the API.
#         """
#         from litellm.proxy.common_utils.callback_utils import (
#             add_guardrail_to_applied_guardrails_header,
#         )
#         from litellm.proxy.guardrails.guardrail_helpers import (
#             should_proceed_based_on_metadata,
#         )

#         event_type: GuardrailEventHooks = GuardrailEventHooks.post_call
#         if self.should_run_guardrail(data=data, event_type=event_type) is not True:
#             return response

#         if (
#             await should_proceed_based_on_metadata(
#                 data=data,
#                 guardrail_name=GUARDRAIL_NAME,
#             )
#             is False
#         ):
#             return response

#         verbose_proxy_logger.debug("🛡️ Running NeMo Guardrails API post-call check")
#         start_time = datetime.now()
        
#         try:
#             # Extract response content
#             response_content = None
#             if hasattr(response, "choices") and len(response.choices) > 0:
#                 choice = response.choices[0]
#                 if hasattr(choice, "message") and hasattr(choice.message, "content"):
#                     response_content = choice.message.content
            
#             if not response_content:
#                 verbose_proxy_logger.warning("🛡️ No response content found to check")
#                 return response
            
#             verbose_proxy_logger.debug(
#                 "🛡️ Checking LLM response: %s", 
#                 response_content[:100]
#             )
            
#             # Check response via API
#             api_response = self._check_message_with_api([{
#                 "role": "assistant",
#                 "content": response_content
#             }])
            
#             # Check if response was blocked
#             is_blocked, reason, policy_id = self._is_message_blocked(api_response)
            
#             if is_blocked:
#                 verbose_proxy_logger.warning(
#                     "🚫 NeMo Guardrails BLOCKED LLM response: %s", reason
#                 )
                
#                 self._log_guardrail_result(
#                     data=data,
#                     start_time=start_time,
#                     status="blocked",
#                     reason=f"LLM response blocked by NeMo Guardrails: {reason}",
#                     llm_response=response_content,
#                     policy_id=policy_id,
#                 )
                
#                 # Modify response to indicate blocking
#                 if hasattr(response, "choices") and len(response.choices) > 0:
#                     response.choices[0].message.content = (
#                         "I apologize, but I cannot provide that response as it violates content safety policies."
#                     )
#             else:
#                 verbose_proxy_logger.info("✅ NeMo Guardrails PASSED LLM response")

#                 self._log_guardrail_result(
#                     data=data,
#                     start_time=start_time,
#                     status="passed",
#                     reason="LLM response passed NeMo Guardrails checks",
#                     llm_response=response_content,
#                 )
            
#             # Add to applied guardrails header
#             add_guardrail_to_applied_guardrails_header(
#                 request_data=data, 
#                 guardrail_name=self.guardrail_name
#             )
            
#             return response
            
#         except Exception as e:
#             verbose_proxy_logger.error(
#                 "🚫 Error in NeMo Guardrails post-call hook: %s",
#                 str(e),
#                 exc_info=True
#             )
            
#             self._log_guardrail_result(
#                 data=data,
#                 start_time=start_time,
#                 status="error",
#                 reason=f"Error: {str(e)}",
#             )
            
#             # Return original response on error
#             return response

#     def _log_guardrail_result(
#         self,
#         data: Dict,
#         start_time: datetime,
#         status: str,
#         reason: str,
#         user_message: Optional[str] = None,
#         llm_response: Optional[str] = None,
#         policy_id: Optional[str] = None,
#     ):
#         """Log guardrail execution results."""
#         end_time = datetime.now()
#         duration = (end_time - start_time).total_seconds()
        
#         log_data = {
#             "guardrail_name": self.guardrail_name,
#             "status": status,
#             "reason": reason,
#             "duration_seconds": duration,
#         }
        
#         if user_message:
#             log_data["user_message_preview"] = user_message[:100]
        
#         if llm_response:
#             log_data["llm_response_preview"] = llm_response[:100]
        
#         if policy_id:
#             log_data["policy_id"] = policy_id
        
#         # Add standard logging information
#         self.add_standard_logging_guardrail_information_to_request_data(
#             guardrail_json_response=log_data,
#             guardrail_status=status,
#             request_data=data,
#             start_time=start_time.timestamp(),
#             end_time=end_time.timestamp(),
#             duration=duration,
#         )
        
#         verbose_proxy_logger.info(
#             "🛡️ NeMo Guardrails result: %s - %s (%.3fs)",
#             status.upper(),
#             reason,
#             duration
#         )

#     @staticmethod
#     def get_config_model() -> Optional[Type["GuardrailConfigModel"]]:
#         """Get the configuration model for this guardrail."""
#         from litellm.types.proxy.guardrails.guardrail_hooks.nemo_guardrails import (
#             NemoGuardrailsConfigModel,
#         )
        
#         return NemoGuardrailsConfigModel





# +-------------------------------------------------------------+
#
#           Use NeMo Guardrails API for your LLM calls
#
# +-------------------------------------------------------------+

import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

import requests
from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.types.guardrails import GuardrailEventHooks

GUARDRAIL_NAME = "nemo_guardrails"

if TYPE_CHECKING:
    from litellm.types.proxy.guardrails.guardrail_hooks.base import GuardrailConfigModel


class NemoGuardrailsGuardrail(CustomGuardrail):
    """
    NeMo Guardrails API integration for LiteLLM.
    
    This guardrail uses NVIDIA's NeMo Guardrails API to detect and prevent harmful,
    off-topic, or inappropriate content in both user prompts and LLM responses.
    """

    def __init__(
        self,
        guardrails_url: Optional[str] = None,
        config_id: Optional[str] = None,
        timeout: int = 30,
        **kwargs,
    ):
        """
        Initialize the NeMo Guardrails API guardrail.

        Args:
            guardrails_url: URL of the NeMo Guardrails API (default: 'http://localhost:8000')
            config_id: Configuration ID to use. If None, will use the first available config
            timeout: Request timeout in seconds (default: 30)
            **kwargs: Additional arguments passed to CustomGuardrail
        """
        super().__init__(**kwargs)
        
        # Set API URL
        self.guardrails_url = guardrails_url or "http://localhost:8000"
        self.timeout = timeout
        
        # Config ID (will be fetched if not provided)
        self._config_id = config_id
        self._configs_cache = None
        
        verbose_proxy_logger.info(
            "🛡️ NeMo Guardrails API initialized with URL: %s", 
            self.guardrails_url
        )

    def _get_config_id(self) -> str:
        """Get the config ID to use for guardrail checks."""
        if self._config_id:
            return self._config_id
        
        # Fetch available configs if not cached
        if self._configs_cache is None:
            try:
                verbose_proxy_logger.debug(
                    "🛡️ Fetching available NeMo Guardrails configurations"
                )
                response = requests.get(
                    f"{self.guardrails_url}/v1/rails/configs",
                    timeout=self.timeout
                )
                response.raise_for_status()
                self._configs_cache = response.json()
                
                verbose_proxy_logger.info(
                    "🛡️ Found %d NeMo Guardrails configurations",
                    len(self._configs_cache)
                )
            except Exception as e:
                verbose_proxy_logger.error(
                    "🚫 Error fetching NeMo Guardrails configs: %s", str(e)
                )
                raise
        
        if not self._configs_cache or len(self._configs_cache) == 0:
            raise ValueError("No NeMo Guardrails configurations available")
        
        # Use the first available config
        config_id = self._configs_cache[0].get("id")
        if not config_id:
            raise ValueError("Config ID not found in response")
        
        verbose_proxy_logger.debug("🛡️ Using config ID: %s", config_id)
        return config_id

    def _check_message_with_api(self, messages: List[Dict]) -> Dict:
        """
        Send messages to the NeMo Guardrails API for checking.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            
        Returns:
            API response as dictionary
        """
        config_id = self._get_config_id()
        
        try:
            response = requests.post(
                f"{self.guardrails_url}/v1/chat/completions",
                json={
                    "config_id": config_id,
                    "messages": messages
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            verbose_proxy_logger.error(response.json())
            return response.json()
        except requests.exceptions.Timeout:
            verbose_proxy_logger.error("🚫 NeMo Guardrails API request timed out")
            raise
        except requests.exceptions.RequestException as e:
            verbose_proxy_logger.error(
                "🚫 NeMo Guardrails API request failed: %s", str(e)
            )
            raise

    def _is_message_blocked(self, api_response: Dict) -> tuple[bool, Optional[str]]:
        """
        Determine if a message was blocked based on API response.
        
        Returns:
            Tuple of (is_blocked, reason)
        """
        # Check for empty or error responses
        verbose_proxy_logger.warning(api_response["messages"][0]["content"])
        if not api_response:
            return True, "Empty response from guardrails API"
        
        # Extract content from response
        response_text = api_response["messages"][0]["content"]
        
        # Handle different response formats
        # if "choices" in api_response and len(api_response["choices"]) > 0:
        #     choice = api_response["choices"][0]
        #     if "message" in choice and "content" in choice["message"]:
        #         response_text = choice["message"]["content"]
        # elif "response" in api_response:
        #     response_text = api_response["response"]
        # elif "content" in api_response:
        #     response_text = api_response["content"]
        
        # Check if response is empty or blocked
        if not response_text or response_text.strip() == "":
            return True, "Empty response from guardrails"
        
        # Check for blocking phrases
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
                "I cannot provide information about causing harm to others. Is there something else I can help you with?",
                "I cannot assist with illegal activities. I'm here to help with legitimate and legal inquiries.",
                "I'm designed to follow safety guidelines and cannot bypass my instructions. How else can I assist you?",
                "Please don't share sensitive personal information like passwords, credit cards, or social security numbers. How else can I help?",
                "I'm here to have respectful conversations. Let's keep things constructive. What can I help you with?",
                "I cannot create malicious code or security exploits. I can help with legitimate programming questions instead.",
                "I understand you may be frustrated. How can I help you in a constructive way?"

            ]
        
        response_lower = response_text.lower()
        for phrase in blocking_phrases:
            if phrase.lower() in response_lower:
                return True, f"Blocking phrase detected: {phrase}"
        
        return False, None

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
        against the defined guardrails via the API.
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

        verbose_proxy_logger.debug("🛡️ Running NeMo Guardrails API pre-call check")
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
            
            # Check message via API
            api_response = self._check_message_with_api([{
                "role": "user",
                "content": user_message
            }])

            verbose_proxy_logger.warning(api_response)
                
            
            # Check if message was blocked
            is_blocked, reason = self._is_message_blocked(api_response)
            
            if is_blocked:
                verbose_proxy_logger.warning(
                    "🚫 NeMo Guardrails BLOCKED user message: %s", reason
                )
                
                self._log_guardrail_result(
                    data=data,
                    start_time=start_time,
                    status="blocked",
                    reason=f"Message blocked by NeMo Guardrails: {reason}",
                    user_message=user_message,
                )
                
                # Raise exception to stop the request
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
        against the defined guardrails via the API.
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

        verbose_proxy_logger.debug("🛡️ Running NeMo Guardrails API post-call check")
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
            
            # Check response via API
            api_response = self._check_message_with_api([{
                "role": "assistant",
                "content": response_content
            }])
            
            # Check if response was blocked
            is_blocked, reason = self._is_message_blocked(api_response)
            
            if is_blocked:
                verbose_proxy_logger.warning(
                    "🚫 NeMo Guardrails BLOCKED LLM response: %s", reason
                )
                
                self._log_guardrail_result(
                    data=data,
                    start_time=start_time,
                    status="blocked",
                    reason=f"LLM response blocked by NeMo Guardrails: {reason}",
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






















