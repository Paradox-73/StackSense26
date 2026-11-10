"""A small client for an OpenAI-compatible chat API (Google Gemini's free tier by default), using only the standard library.

The rule-based engine makes every decision. This module is used only to read free text and to write
summaries, and every caller has a fallback that works without it:

  * `available()` is False when no API key is configured or the daily request limit is used up, so callers
    skip the model entirely.
  * `chat()` tries a chain of models in order and moves on after a 404, 429, 5xx or a timeout.
  * Every real network request is counted per calendar day in `data/llm_cache/.usage.json`; once the daily limit
    is reached no more requests are sent that day (saved answers are still served).
  * Every answer is saved in `data/llm_cache/` under a hash of (model chain, messages), so the same input
    gives the same output, and the saved files can be committed for reviewers.

Configuration (environment variables, or a `.env` file in the repository root):
  STACKSENSE_LLM_API_KEY or OPENROUTER_API_KEY   the key (never logged, never returned)
  STACKSENSE_LLM_BASE_URL                        default https://generativelanguage.googleapis.com/v1beta/openai
                                                 (Gemini free tier); https://openrouter.ai/api/v1 also works
  STACKSENSE_LLM_MODELS                          comma-separated model chain, tried in order
  STACKSENSE_LLM_DAILY_LIMIT                     most real requests per calendar day, default 200; 0 = no limit
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = ROOT / ".env"
CACHE_DIR = ROOT / "data" / "llm_cache"

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODELS = "gemini-3.5-flash-lite,gemini-flash-lite-latest,gemini-2.5-flash-lite"
DEFAULT_DAILY_LIMIT = 200
TIMEOUT_S = 30
RETRY_STATUS = {404, 408, 429}  # plus every 5xx: try the next model in the chain


class LLMError(RuntimeError):
    """The model chain could not give a usable answer. The message never contains the API key."""


@dataclass
class Reply:
    """One model answer: the text, the model that wrote it, and whether it came from the disk cache."""
    text: str
    model: str
    cached: bool = False


# A transport sends one request and returns (HTTP status, parsed JSON body). Tests replace it with a fake.
Transport = Callable[[str, dict, dict, float], "tuple[int, dict]"]


def urllib_transport(url: str, headers: dict, payload: dict, timeout: float) -> tuple[int, dict]:
    """POST `payload` as JSON with the standard library. Network failures raise OSError or TimeoutError."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        try:
            body = json.loads(err.read().decode("utf-8"))
        except (ValueError, OSError):
            body = {}
        return err.code, body
    except urllib.error.URLError as err:  # DNS failure, refused connection, timeout while connecting
        raise OSError(str(err.reason)) from None


_transport: Transport = urllib_transport


def set_transport(fn: Transport | None) -> None:
    """Replace the function that sends requests (used by tests); None restores the real one."""
    global _transport
    _transport = fn or urllib_transport


# ------------------------------------------------------------------ configuration

def _load_dotenv(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines from a .env file. Blank lines and '#' comments are skipped; quotes are removed."""
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out


def _setting(name: str) -> str:
    """A setting from the environment, else from .env; empty string when absent."""
    return (os.environ.get(name) or _load_dotenv(DOTENV_PATH).get(name) or "").strip()


def _api_key() -> str:
    return _setting("STACKSENSE_LLM_API_KEY") or _setting("OPENROUTER_API_KEY")


def base_url() -> str:
    return (_setting("STACKSENSE_LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def models() -> list[str]:
    """The model chain, in the order they are tried."""
    raw = _setting("STACKSENSE_LLM_MODELS") or DEFAULT_MODELS
    return [m.strip() for m in raw.split(",") if m.strip()]


def daily_limit() -> int:
    """Most real network requests per calendar day (0 means no limit). A bad value falls back to the default."""
    raw = _setting("STACKSENSE_LLM_DAILY_LIMIT")
    try:
        return max(0, int(raw)) if raw else DEFAULT_DAILY_LIMIT
    except ValueError:
        return DEFAULT_DAILY_LIMIT


def _usage_path() -> Path:
    return CACHE_DIR / ".usage.json"


def requests_today() -> int:
    """How many real requests were sent today (the counter starts again each calendar day)."""
    try:
        entry = json.loads(_usage_path().read_text(encoding="utf-8"))
        if entry.get("date") == datetime.date.today().isoformat():
            return int(entry.get("count", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return 0


def _count_request() -> None:
    """Add one to today's counter. A failed write is ignored (the limit is a safety net, not a ledger)."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        entry = {"date": datetime.date.today().isoformat(), "count": requests_today() + 1}
        _usage_path().write_text(json.dumps(entry) + "\n", encoding="utf-8")
    except OSError:
        pass


def limit_reached() -> bool:
    limit = daily_limit()
    return limit > 0 and requests_today() >= limit


def available() -> bool:
    """True when an API key is configured and today's request limit is not used up.
    Otherwise every feature uses its rule-based fallback (saved answers are still served by chat())."""
    return bool(_api_key()) and not limit_reached()


# ------------------------------------------------------------------ disk cache

def cache_key(chain: list[str], messages: list[dict], json_mode: bool) -> str:
    blob = json.dumps({"models": chain, "messages": messages, "json": json_mode}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_read(key: str) -> Reply | None:
    try:
        entry = json.loads((CACHE_DIR / f"{key}.json").read_text(encoding="utf-8"))
        return Reply(entry["text"], entry["model"], cached=True)
    except (OSError, ValueError, KeyError):
        return None


def _cache_write(key: str, chain: list[str], messages: list[dict], reply: Reply) -> None:
    """Save one answer as a small JSON file. A failed write is ignored: the cache is an optimisation."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        entry = {"models": chain, "messages": messages, "model": reply.model, "text": reply.text}
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(entry, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass


# ------------------------------------------------------------------ chat

def _ask_model(model: str, messages: list[dict], json_mode: bool) -> str | None:
    """Ask one model. Returns its text, or None when the next model in the chain should be tried."""
    url = f"{base_url()}/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {_api_key()}"}
    payload: dict = {"model": model, "messages": messages, "temperature": 0}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    for _ in range(2):
        if limit_reached():
            return None
        _count_request()
        try:
            status, body = _transport(url, headers, payload, TIMEOUT_S)
        except (OSError, TimeoutError):
            return None
        if status == 200:
            return _message_text(body)
        if status in (400, 422) and "response_format" in payload:
            payload.pop("response_format")  # this model has no JSON mode: ask again in plain mode
            continue
        return None  # 404, 429, 5xx, or anything else: try the next model
    return None


def _message_text(body: dict) -> str | None:
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return text.strip() if isinstance(text, str) and text.strip() else None


def chat(messages: list[dict], json_mode: bool = True, use_cache: bool = True) -> Reply:
    """Send `messages` to the first model in the chain that answers. Raises LLMError when none does."""
    chain = models()
    key = cache_key(chain, messages, json_mode)
    if use_cache and (hit := _cache_read(key)):
        return hit
    if not _api_key():
        raise LLMError("no API key configured")
    if limit_reached():
        raise LLMError(f"the daily limit of {daily_limit()} model requests is used up")
    for model in chain:
        text = _ask_model(model, messages, json_mode)
        if text is not None:
            reply = Reply(text, model)
            if use_cache:
                _cache_write(key, chain, messages, reply)
            return reply
    raise LLMError(f"none of the {len(chain)} configured models answered")


def chat_json(messages: list[dict], use_cache: bool = True) -> tuple[dict, Reply]:
    """Like chat(), but returns the parsed JSON object. Raises LLMError when the reply holds no JSON object."""
    reply = chat(messages, json_mode=True, use_cache=use_cache)
    data = extract_json(reply.text)
    if not isinstance(data, dict):
        raise LLMError("the model did not return a JSON object")
    return data, reply


def extract_json(text: str):
    """Parse a JSON value from model output that may be wrapped in code fences or extra prose; None if absent."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    candidates = [fenced.group(1).strip()] if fenced else []
    candidates.append(text)
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start:end + 1])
    for cand in candidates:
        try:
            return json.loads(cand)
        except ValueError:
            continue
    return None
