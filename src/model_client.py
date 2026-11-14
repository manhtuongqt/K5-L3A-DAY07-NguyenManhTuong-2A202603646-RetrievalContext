"""Small, auditable HTTP adapter. No SDK, silent fallback, or secret-bearing logs.

OpenAI-compatible contract: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
Anthropic messages are supported for gateways exposing that protocol.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def load_env(path: Path) -> None:
    """Load local simple KEY=value settings without overwriting process variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


class ModelError(RuntimeError):
    def __init__(self, message, *, attempts=None):
        super().__init__(message)
        self.attempts = attempts or []


class ModelClient:
    def __init__(self, api_key: str, base_url: str, model: str, *, api_style="openai",
                 timeout=120, max_retries=1, max_tokens=1600, temperature=0.0):
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
            raise ValueError("API base URL must use HTTPS (except localhost)")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("API base URL must not contain credentials, query, or fragment")
        if not api_key.strip() or not model.strip():
            raise ValueError("DAY07_API_KEY and DAY07_MODEL are required")
        if api_style not in ("openai", "anthropic"):
            raise ValueError("DAY07_API_STYLE must be openai or anthropic")
        self._key, self.base_url, self.model = api_key, base_url.rstrip("/"), model
        self.api_style = api_style
        self.timeout, self.max_retries = float(timeout), int(max_retries)
        self.max_tokens, self.temperature = int(max_tokens), float(temperature)

    @classmethod
    def from_env(cls, root=None):
        if root is not None:
            load_env(Path(root) / ".env")
        return cls(os.environ.get("DAY07_API_KEY", ""), os.environ.get("DAY07_BASE_URL", ""),
                   os.environ.get("DAY07_MODEL", ""), api_style=os.environ.get("DAY07_API_STYLE", "openai"),
                   timeout=os.environ.get("DAY07_TIMEOUT_SECONDS", os.environ.get("DAY07_TIMEOUT", 120)), max_retries=os.environ.get("DAY07_MAX_RETRIES", 1),
                   max_tokens=os.environ.get("DAY07_MAX_TOKENS", 1600), temperature=os.environ.get("DAY07_TEMPERATURE", 0))

    def public_config(self):
        return {"model": self.model, "base_url": self.base_url, "api_style": self.api_style,
                "temperature": self.temperature, "max_tokens": self.max_tokens,
                "timeout_seconds": self.timeout, "max_retries": self.max_retries}

    def _redact(self, text):
        text = str(text).replace(self._key, "[REDACTED]")
        return re.sub(r"\bsk-[A-Za-z0-9_-]{12,}", "[REDACTED]", text)

    def complete(self, messages, tools=None, tool_choice=None):
        """Return text/tool_calls/model/usage/request_id/latency_ms/attempts.

        Only retry transient failures, bounded by max_retries. Every failed HTTP
        attempt remains visible; absent usage is unknown, never assumed free.
        """
        if self.api_style == "anthropic":
            system = "\n\n".join(str(m["content"]) for m in messages if m["role"] == "system")
            body = {"model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature,
                    "system": system, "messages": [m for m in messages if m["role"] != "system"]}
            if tools:
                body["tools"] = [{"name": t["function"]["name"], "description": t["function"].get("description", ""),
                                  "input_schema": t["function"]["parameters"]} for t in tools]
            if tool_choice:
                body["tool_choice"] = {"type": "any" if tool_choice == "required" else "auto"}
            endpoint = self.base_url + "/messages"
            headers = {"x-api-key": self._key, "anthropic-version": "2023-06-01"}
        else:
            body = {"model": self.model, "messages": messages, "temperature": self.temperature,
                    "max_tokens": self.max_tokens, "stream": False}
            if tools:
                body["tools"] = tools
            if tool_choice:
                body["tool_choice"] = tool_choice
            endpoint = self.base_url + "/chat/completions"
            headers = {"Authorization": "Bearer " + self._key}
        headers.update({"Content-Type": "application/json", "User-Agent": "Day07-Lab/1.0"})
        request = urllib.request.Request(endpoint, data=json.dumps(body).encode("utf-8"), headers=headers)
        attempts, started = [], time.perf_counter()
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                    request_id = response.headers.get("x-request-id", raw.get("id"))
                if raw.get("error"):
                    raise ValueError("provider returned an error object")
                if self.api_style == "anthropic":
                    text = "\n".join(x.get("text", "") for x in raw.get("content", []) if x.get("type") == "text")
                    calls = [{"id": x.get("id"), "name": x.get("name"), "arguments": x.get("input", {})}
                             for x in raw.get("content", []) if x.get("type") == "tool_use"]
                    usage_raw = raw.get("usage")
                    usage = None if usage_raw is None else {"input_tokens": usage_raw.get("input_tokens"),
                              "output_tokens": usage_raw.get("output_tokens"), "raw": usage_raw}
                    finish = raw.get("stop_reason")
                else:
                    choices = raw.get("choices", [])
                    if not choices:
                        raise ValueError("provider returned no choices")
                    msg = choices[0]["message"]
                    text = msg.get("content") or ""
                    if isinstance(text, list):
                        text = "\n".join(x.get("text", "") for x in text)
                    calls = [{"id": x.get("id"), "name": x["function"]["name"],
                              "arguments": x["function"].get("arguments", "{}")}
                             for x in msg.get("tool_calls", [])]
                    usage_raw = raw.get("usage")
                    usage = None if usage_raw is None else {"input_tokens": usage_raw.get("prompt_tokens"),
                              "output_tokens": usage_raw.get("completion_tokens"), "raw": usage_raw}
                    finish = choices[0].get("finish_reason")
                attempts.append({"attempt": attempt + 1, "status": "success", "latency_ms": (time.perf_counter() - t0) * 1000,
                                 "usage": usage, "request_id": request_id})
                return {"text": text, "tool_calls": calls, "model": raw.get("model", self.model), "usage": usage,
                        "request_id": request_id, "finish_reason": finish, "attempts": attempts,
                        "latency_ms": (time.perf_counter() - started) * 1000,
                        "raw_sanitized": {"id": raw.get("id"), "model": raw.get("model"), "usage": usage_raw,
                                          "finish_reason": finish}}
            except urllib.error.HTTPError as exc:
                # Never retain request headers or arbitrary provider response bodies.
                detail = {"attempt": attempt + 1, "status": "error", "type": "HTTPError", "http_status": exc.code,
                          "latency_ms": (time.perf_counter() - t0) * 1000, "usage": None}
                attempts.append(detail)
                transient = exc.code in (408, 429, 500, 502, 503, 504)
                if not transient or attempt == self.max_retries:
                    raise ModelError(f"Provider HTTP {exc.code}", attempts=attempts) from None
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
                attempts.append({"attempt": attempt + 1, "status": "error", "type": type(exc).__name__,
                                 "message": self._redact(exc), "latency_ms": (time.perf_counter() - t0) * 1000, "usage": None})
                if attempt == self.max_retries or isinstance(exc, (ValueError, KeyError, TypeError)):
                    raise ModelError(self._redact(f"Provider {type(exc).__name__}: {exc}"), attempts=attempts) from None
            time.sleep(min(2 ** attempt, 4))
        raise AssertionError("unreachable")
