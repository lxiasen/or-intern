"""LiteLLM kwargs resolution for OR-Intern.

Matching the ML-Intern signature: _resolve_llm_params(model_name, session_hf_token, reasoning_effort=..., strict=False)
Returns a dict of LiteLLM base kwargs (model, api_key, api_base, thinking, etc.).
Messages and tools are added separately by the agent loop.
"""

import os
from typing import Any, Optional


# Exceptions expected by effort_probe
class UnsupportedEffortError(Exception):
    """Raised when a model does not support the requested effort level."""
    pass


# ── Local model providers ──
_LOCAL_PROVIDERS = {
    "ollama": {"env_base_url": "OLLAMA_BASE_URL", "default_port": 11434},
    "vllm": {"env_base_url": "VLLM_BASE_URL", "default_port": 8000},
    "lm_studio": {"env_base_url": "LMSTUDIO_BASE_URL", "default_port": 1234},
    "llamacpp": {"env_base_url": "LLAMACPP_BASE_URL", "default_port": 8080},
}

_DEFAULT_MAX_TOKENS = 200_000


def _is_local_model(model_name: str) -> bool:
    return any(model_name.startswith(f"{p}/") for p in _LOCAL_PROVIDERS)


def _get_local_provider(model_name: str) -> Optional[str]:
    for p in _LOCAL_PROVIDERS:
        if model_name.startswith(f"{p}/"):
            return p
    return None


def _get_model_id(model_name: str) -> str:
    for p in _LOCAL_PROVIDERS:
        if model_name.startswith(f"{p}/"):
            return model_name[len(p) + 1:]
    if "/" in model_name:
        return model_name.split("/", 1)[1]
    return model_name


# ── Reasoning effort mapping ──
_EFFORT_ANTHROPIC = {
    "minimal": None, "low": 1024, "medium": 4096,
    "high": 8192, "xhigh": 16384, "max": 32768,
}

_EFFORT_OPENAI = {
    "minimal": "minimal", "low": "low", "medium": "medium",
    "high": "high", "xhigh": "high", "max": "high",
}


def resolve_model_max_tokens(model_name: str) -> int:
    """Resolve max context tokens for a model."""
    try:
        from litellm import get_model_info
        stripped = model_name.removeprefix("huggingface/").split(":", 1)[0]
        info = get_model_info(stripped)
        if info and isinstance(info.get("max_input_tokens"), int):
            return info["max_input_tokens"]
    except Exception:
        pass
    return _DEFAULT_MAX_TOKENS


def resolve_api_key(model_name: str) -> Optional[str]:
    """Resolve API key from environment."""
    if model_name.startswith("anthropic/"):
        return os.getenv("ANTHROPIC_API_KEY")
    elif model_name.startswith("openai/"):
        return os.getenv("OPENAI_API_KEY")
    else:
        return os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")


# ── LiteLLM effort validation patch (from ml-intern) ──
def _patch_litellm_effort_validation() -> None:
    try:
        from litellm.llms.anthropic.chat import transformation as _t
    except Exception:
        return
    cfg = getattr(_t, "AnthropicConfig", None)
    if cfg is None:
        return
    original = getattr(cfg, "_is_opus_4_6_model", None)
    if original is None or getattr(original, "_hf_agent_patched", False):
        return
    original._hf_agent_patched = True

_patch_litellm_effort_validation()


def _resolve_llm_params(
    model_name: str,
    session_hf_token: str | None = None,
    reasoning_effort: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Build LiteLLM kwargs for the given model.

    Matches the ML-Intern call signature:
      _resolve_llm_params(model_name, session.hf_token, reasoning_effort=...)

    Returns a dict with: model, api_key, api_base, thinking/reasoning_effort, etc.
    Messages, tools, stream, max_tokens are added separately by the agent loop.
    """
    is_anthropic = model_name.startswith("anthropic/")
    is_openai = model_name.startswith("openai/")
    is_local = _is_local_model(model_name)

    # Build LiteLLM model ID
    if is_local:
        litellm_model = f"openai/{_get_model_id(model_name)}"
    elif is_openai or is_anthropic:
        litellm_model = model_name
    else:
        litellm_model = f"openai/{model_name}"

    params: dict[str, Any] = {
        "model": litellm_model,
    }

    # API key
    api_key = resolve_api_key(model_name)
    if api_key:
        params["api_key"] = api_key

    # Custom API base for OpenAI-compatible endpoints
    # Check env var OPENAI_API_BASE first, then config
    custom_base = os.getenv("OPENAI_API_BASE")
    if custom_base:
        params["api_base"] = custom_base

    # Reasoning / thinking effort
    if reasoning_effort:
        if is_anthropic:
            budget = _EFFORT_ANTHROPIC.get(reasoning_effort)
            if budget:
                params["thinking"] = {"type": "enabled", "budget_tokens": budget}
                params["output_config"] = {"effort": reasoning_effort}
        elif is_openai:
            mapped = _EFFORT_OPENAI.get(reasoning_effort)
            if mapped:
                params["reasoning_effort"] = mapped

    # Local model base URL
    if is_local:
        provider = _get_local_provider(model_name)
        info = _LOCAL_PROVIDERS.get(provider, {})
        base_url = os.getenv(info.get("env_base_url", ""))
        if not base_url:
            base_url = f"http://localhost:{info.get('default_port', 8000)}/v1"
        params["api_base"] = base_url

    return params
