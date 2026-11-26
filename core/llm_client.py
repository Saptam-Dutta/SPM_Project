"""
llm_client.py
-------------
One provider-agnostic wrapper used by EVERY page of the app (charter,
schedule, cost, risks). Pick a provider once in the sidebar and every page
uses it. Each provider function takes (model, api_key, prompt) and returns
plain text; any failure is normalised into a RuntimeError with a readable
message.

Providers: Google Gemini, OpenAI, Anthropic Claude, and "OpenAI-compatible
API" (any service that speaks the OpenAI chat-completions protocol, via a
custom base URL).
"""

PROVIDER_MODELS = {
    "Google Gemini": ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.8-flash"],
    "OpenAI": ["gpt-5.4", "gpt-5.4-mini", "gpt-4.1"],
    "Anthropic Claude": ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5-20251001"],
    "OpenAI-compatible API": [],  # model ID is typed in, plus a base URL
}


def _call_gemini(model: str, api_key: str, prompt: str, base_url: str = "") -> str:
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("The 'google-genai' package isn't installed. Run: pip install google-genai") from exc

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        text = response.text or ""
        if text.strip():
            return text
    except Exception as first_error:
        # Some newer Gemini models are only served through the Interactions
        # API (this is what the EVM app used), so try that before giving up.
        interactions = getattr(client, "interactions", None)
        if interactions is None:
            raise first_error
        try:
            response = interactions.create(model=model, input=prompt)
            return response.output_text or ""
        except Exception:
            raise first_error
    interactions = getattr(client, "interactions", None)
    if interactions is not None:
        response = interactions.create(model=model, input=prompt)
        return response.output_text or ""
    return ""


def _call_openai(model: str, api_key: str, prompt: str, base_url: str = "") -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The 'openai' package isn't installed. Run: pip install openai") from exc

    client = OpenAI(api_key=api_key, base_url=(base_url or "").strip() or None, timeout=90.0, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _call_anthropic(model: str, api_key: str, prompt: str, base_url: str = "") -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("The 'anthropic' package isn't installed. Run: pip install anthropic") from exc

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


_DISPATCH = {
    "Google Gemini": _call_gemini,
    "OpenAI": _call_openai,
    "Anthropic Claude": _call_anthropic,
    "OpenAI-compatible API": _call_openai,
}


def call_llm(provider: str, model: str, api_key: str, prompt: str, base_url: str = "") -> str:
    """Send `prompt` to the chosen provider and return the raw text reply.
    Raises RuntimeError (safe to show to the user) on any failure."""
    if not provider or provider not in _DISPATCH:
        raise RuntimeError(f"Unknown or unselected AI provider: '{provider}'.")
    if not model:
        raise RuntimeError("No model selected. Choose a model in the sidebar first.")
    if not api_key:
        raise RuntimeError("No API key provided. Paste one into the sidebar first.")
    if provider == "OpenAI-compatible API" and base_url and not base_url.startswith(("http://", "https://")):
        raise RuntimeError("The API base URL must start with http:// or https://.")

    try:
        return _DISPATCH[provider](model, api_key, prompt, base_url)
    except RuntimeError:
        raise
    except Exception as exc:  # network / auth / quota / SDK errors
        raise RuntimeError(f"{provider} API call failed: {exc}") from exc


def parse_json_reply(raw_text: str) -> dict:
    """Parse a JSON object out of an LLM reply (tolerates markdown fences)."""
    import json

    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise RuntimeError("The AI returned content that wasn't valid JSON. Try again.\n\nRaw response:\n" + (raw_text or ""))
