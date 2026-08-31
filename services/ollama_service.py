"""Server-side gateway to a local Ollama instance.

The browser never talks to Ollama directly. The frontend can only trigger
one of the two fixed, server-defined analysis flows in
prompts/forensic_prompts.py; it cannot supply an arbitrary system prompt,
model name, or Ollama URL.
"""
import json
import logging

import requests

import config

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when Ollama cannot be reached or returns an unusable response."""


def check_connection():
    """Return (ok: bool, message: str) describing Ollama reachability."""
    try:
        resp = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m.get("name") for m in resp.json().get("models", [])]
            if config.OLLAMA_MODEL in models:
                return True, f"Connected. Model '{config.OLLAMA_MODEL}' is available."
            return True, (
                f"Connected to Ollama, but model '{config.OLLAMA_MODEL}' was not "
                f"found in {models}. Pull it with: ollama pull {config.OLLAMA_MODEL}"
            )
        return False, f"Ollama responded with status {resp.status_code}."
    except requests.exceptions.RequestException as exc:
        return False, f"Cannot reach Ollama at {config.OLLAMA_BASE_URL}: {exc}"


def ask_ollama(messages, temperature=None, expect_json=True):
    """Send a chat request to the local Ollama server.

    messages: list of {"role": "system"|"user"|"assistant", "content": str}
    Returns the parsed JSON object from the model's reply when expect_json is
    True, otherwise the raw text content.
    Raises OllamaError on any connection, timeout, or validation failure.
    """
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": config.OLLAMA_TEMPERATURE if temperature is None else temperature,
        },
    }
    if expect_json:
        payload["format"] = "json"

    try:
        resp = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=config.OLLAMA_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as exc:
        raise OllamaError("Ollama request timed out.") from exc
    except requests.exceptions.RequestException as exc:
        raise OllamaError(f"Could not reach Ollama: {exc}") from exc

    if resp.status_code != 200:
        raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        body = resp.json()
    except ValueError as exc:
        raise OllamaError("Ollama returned a non-JSON HTTP body.") from exc

    content = (body.get("message") or {}).get("content", "")
    if not content:
        raise OllamaError("Ollama returned an empty response.")

    if not expect_json:
        return content

    try:
        return json.loads(content)
    except (ValueError, TypeError) as exc:
        parsed = _extract_json_object(content)
        if parsed is not None:
            return parsed
        logger.warning("Ollama response was not valid JSON: %s", content[:500])
        raise OllamaError(
            "Ollama did not return valid JSON. The model may need a lower "
            "temperature or a different model."
        ) from exc


def _extract_json_object(text):
    """Best-effort recovery of a JSON object embedded in extra prose."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None
