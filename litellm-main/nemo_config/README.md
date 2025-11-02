# NeMo Guardrails Configuration

This directory contains the configuration files for NeMo Guardrails integration with LiteLLM.

## Files

### config.yml

Main configuration file that defines:

- LLM model to use (gemini/gemini-2.5-flash-lite)
- API key configuration
- Input and output rails
- Prompt templates for safety checks

### rails.co

Colang file that defines conversation flows and safety rails:

- **Input Rails**: Check user messages before sending to LLM
  - `check jailbreak`: Detects jailbreak attempts
  - `check harmful intent`: Blocks requests for harmful content
  - `check off topic`: Ensures queries are within scope
- **Output Rails**: Check LLM responses before returning to user
  - `check harmful output`: Prevents harmful responses
  - `check policy violation`: Enforces content policies
- **Bot Responses**: Predefined safe responses for blocked content

### actions.py

Custom Python actions for advanced safety checks:

- `check_input_safety`: Additional input validation
- `check_output_safety`: Additional output validation
- `log_guardrail_event`: Event logging for monitoring
- `retrieve_relevant_chunks`: RAG integration (placeholder)

## Customization

### Adding New Rails

To add new safety checks, edit `rails.co`:

```colang
define flow check new_safety_rule
  $user_message = $user_input
  if "unsafe_pattern" in $user_message
    bot refuse request
    stop
```

### Modifying LLM Model

To use a different LLM, edit `config.yml`:

```yaml
models:
  - type: main
    engine: litellm
    model: your/model-name
    parameters:
      api_key: your_api_key_here
```

### Adding Custom Actions

To add new Python actions, edit `actions.py`:

```python
@action()
async def my_custom_action(context: Optional[dict] = None):
    # Your custom logic here
    return {"result": "success"}
```

## Testing

You can test NeMo Guardrails independently:

```python
from nemoguardrails import RailsConfig, LLMRails
config = RailsConfig.from_path("./nemo_config")
rails = LLMRails(config)
response = rails.generate(messages=[{
    "role": "user",
    "content": "Test message"
}])
print(response)
```

## Integration with LiteLLM

NeMo Guardrails automatically integrates with LiteLLM Proxy when configured in `proxy_server_config.yaml`:

```yaml
guardrails:
  - guardrail_name: "nemo_safety"
    litellm_params:
      guardrail: "nemo_guardrails"
      mode: "during_call" # or "pre_call", "post_call"
      config_path: "./nemo_config"
      llm_model: "gemini/gemini-2.5-flash-lite"
      llm_api_key: "AIzaSyA4Ulh5ES15bbzJsZ7ua8hfSFZyckrdOw4"
```

## Logging

NeMo Guardrails uses emoji logging for easy identification:

- :shield: - Initialization and info messages
- :white_tick: - Content passed guardrails
- :no_entry_symbol: - Content blocked by guardrails
  Check logs to see which messages were blocked:

```
:shield: NeMo Guardrails initialized with config path: ./nemo_config
:shield: Checking user message: Tell me how to hack...
:no_entry_symbol: NeMo Guardrails BLOCKED user message (blocking phrase detected)
```

## Resources

- [NeMo Guardrails Documentation](https://github.com/NVIDIA/NeMo-Guardrails)
- [Colang Language Guide](https://github.com/NVIDIA/NeMo-Guardrails/blob/main/docs/user_guides/colang-language-syntax-guide.md)
- [LiteLLM Guardrails Documentation](https://docs.litellm.ai/docs/proxy/guardrails)

GitHubGitHub
GitHub - NVIDIA-NeMo/Guardrails: NeMo Guardrails is an open-source toolkit for easily adding programmable guardrails to LLM-based conversational systems.
NeMo Guardrails is an open-source toolkit for easily adding programmable guardrails to LLM-based conversational systems. - NVIDIA-NeMo/Guardrails (66 kB)
https://github.com/NVIDIA/NeMo-Guardrails

docs.litellm.aidocs.litellm.ai
Page Not Found | liteLLM (645 kB)
