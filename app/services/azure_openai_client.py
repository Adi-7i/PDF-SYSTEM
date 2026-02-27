import asyncio
import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests


def _env_first(*names: str) -> Optional[str]:
    for name in names:
        val = os.environ.get(name)
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return None


def _build_azure_chat_completions_url(base_url: str, deployment: str, api_version: str) -> str:
    base = base_url.strip().rstrip("/")
    # If user accidentally points at a deeper path, normalize back to the resource root.
    if "/openai/deployments/" in base:
        base = base.split("/openai/deployments/")[0]
    if base.endswith("/openai"):
        base = base[: -len("/openai")]

    path = f"{base}/openai/deployments/{deployment}/chat/completions"
    return f"{path}?{urlencode({'api-version': api_version})}"


class AzureOpenAIConfigError(RuntimeError):
    pass


def _get_azure_config() -> Dict[str, str]:
    """
    Primary env vars (per user request):
      - LLM_API_KEY
      - LLM_AZURE_BASE_URL
      - LLM_AZURE_API_VERSION
      - LLM_AZURE_DEPLOYMENT

    Fallbacks are supported for interoperability with common conventions.
    """
    api_key = _env_first("LLM_API_KEY", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY")
    base_url = _env_first("LLM_AZURE_BASE_URL", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_BASE_URL")
    api_version = _env_first("LLM_AZURE_API_VERSION", "AZURE_OPENAI_API_VERSION") or "2024-02-01"
    deployment = _env_first("LLM_AZURE_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT")

    missing = [k for k, v in [("LLM_API_KEY", api_key), ("LLM_AZURE_BASE_URL", base_url), ("LLM_AZURE_DEPLOYMENT", deployment)] if not v]
    if missing:
        raise AzureOpenAIConfigError(f"Missing required Azure OpenAI env var(s): {', '.join(missing)}")

    return {
        "api_key": api_key,
        "base_url": base_url,
        "api_version": api_version,
        "deployment": deployment,
    }


def chat_completion_sync(
    *,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    timeout_s: int = 90,
) -> str:
    cfg = _get_azure_config()
    url = _build_azure_chat_completions_url(cfg["base_url"], cfg["deployment"], cfg["api_version"])

    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": cfg["api_key"],
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout_s)
    if resp.status_code >= 400:
        # Avoid leaking secrets. Provide a compact error message.
        raise RuntimeError(f"Azure OpenAI request failed ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"Unexpected Azure OpenAI response shape: {str(data)[:500]}")


async def chat_completion_async(
    *,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    timeout_s: int = 90,
) -> str:
    return await asyncio.to_thread(
        chat_completion_sync,
        prompt=prompt,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
    )

