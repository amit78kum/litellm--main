# NeMo Guardrails Configuration

This directory contains the configuration files for NeMo Guardrails integration with LiteLLM.

## Files

### config.yml

Main configuration file that defines:

### NeMo Guardrails configuration for LiteLLM

This folder contains an example NeMo Guardrails configuration used with the LiteLLM proxy. The README focuses on quick start, test steps, and troubleshooting (especially the "empty response" symptom).

Contents

- `config.yml` — main guardrails configuration (models, engines, API keys, rails)
- `rails.co` — Colang source defining input/output rails and bot behaviours
- `actions.py` — optional Python actions invoked from Colang

Quick start

1. Create a virtualenv and install NeMo Guardrails (and dependencies):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install nemoguardrails
```

2. Start the NeMo Guardrails server from this repository root (example):

```powershell
# run the guardrails server using the local config directory
nemoguardrails server --config nemo_config --port 8000 --verbose
```

3. Verify the server is healthy:

```powershell
curl http://localhost:8000/v1/rails/configs
```

Expected: a JSON list of available rail configurations (each has an `id`). If you get an HTML page, error, or empty response, check server logs and the `config.yml` correctness.

How to test locally (simple script)

- Use the provided `test_nemoguardrails_simple.py` script in repository root to exercise listing configs, a safe request and an unsafe request.

Troubleshooting: empty responses or rejections

- If you see logs like:

  - "{'messages': [{'role': 'assistant', 'content': "I'm sorry, I cannot assist with that request..."}]}"
  - or your proxy reports "Empty response from guardrails"

  These indicate the guardrails server itself returned a rejection message (assistant role refusal) or an unexpected response format. Do the following:

  1. Check the guardrails server logs (the terminal where you started `nemoguardrails server`) for errors or stack traces.
  2. Confirm the `config.yml` has a valid `model` and that any required external API keys (OpenAI, Vertex, etc.) are provided via environment variables or the config. Missing model/API keys often cause guardrails to return empty or refusal messages.
  3. Call the guardrails API directly and inspect raw JSON:

```powershell
# list configs
curl http://localhost:8000/v1/rails/configs | jq .

# call a chat completion (replace <CONFIG_ID>)
curl -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"config_id":"<CONFIG_ID>","messages":[{"role":"user","content":"What is the capital of India?"}]}' | jq .
```

Look for fields like `messages`, `violations`, or `alerts`. A normal successful response typically includes `messages` with an `assistant` role and a content string. A rejection may also be returned as a `messages` array where the assistant content is a refusal message.

Integration with LiteLLM proxy

- Prefer API-based configuration with the proxy. Example `litellm` guardrails initializer expects these parameters (see `guardrail_initializers.py`):

```yaml
guardrails:
  - guardrail_name: "nemo_guardrails"
    litellm_params:
      guardrails_url: "http://localhost:8000"
      config_id: null # or the specific config id to lock to
      timeout: 30
      default_on: true
```

Notes

- If `guardrails_url` is missing in the proxy config, the proxy may pass `None` and fail when contacting the server (Invalid URL 'None/…'). Ensure `guardrails_url` is set or the proxy default is used.
- If the guardrails server refuses safe questions, inspect `rails.co` and `actions.py` — some rules may be over-broad (e.g., match keywords like "capital" incorrectly). Narrow patterns or add test cases.

Advanced debugging tips

- Enable `--verbose` and `--auto-reload` when running `nemoguardrails server` during development.
- Add a temporary debug action in `actions.py` to log raw user input and rule matching outputs.
- If the server returns an empty JSON or 500, capture the full server traceback — it usually points to a missing package, invalid model name, or missing API key.

Resources

- NeMo Guardrails: https://github.com/NVIDIA/NeMo-Guardrails
- Colang guide: https://github.com/NVIDIA/NeMo-Guardrails/tree/main/docs/user_guides

If you want, I can:

- Add a small example `config.yml` and a minimal `rails.co` (safe test rules) in this folder.
- Add a `debug_actions.py` helper that logs raw API responses for debugging.

---

Last updated: Automated update to improve quickstart and troubleshooting steps.
