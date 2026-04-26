#!/usr/bin/env python3
"""Unified LLM engine: codex exec (128K) → call_llm fallback (auto-batch).

All cmd_* functions in ai_report.py call exactly one function: call_engine().
This module handles engine selection, context limits, and batching internally.
"""

import json, os, re, shutil, subprocess, sys
from functools import lru_cache
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def load_dotenv(path: Path = None):
    """Minimal .env loader — no dependencies."""
    p = path or Path(__file__).parent / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------------------------------------------------------------------------
# Low-level backends
# ---------------------------------------------------------------------------

def call_llm(prompt: str, system: str = "", max_tokens: int = None) -> str:
    """OpenAI-compatible HTTP call. Thin wrapper, no retry, no batching."""
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        print("LLM_API_KEY not set", file=sys.stderr); sys.exit(1)
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    if max_tokens is None:
        max_tokens = int(os.environ.get("LLM_MAX_TOKENS", 2000))
    payload = json.dumps({"model": model, "messages": msgs, "max_tokens": max_tokens}).encode()
    req = Request(f"{base}/chat/completions", data=payload,
                  headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"].get("content") or ""
    except HTTPError as e:
        print(f"LLM API error: {e.code} {e.read().decode()[:200]}", file=sys.stderr); sys.exit(1)


def _call_codex(content: str, system: str) -> str:
    """Call codex exec: content via stdin, system prompt as instruction."""
    result = subprocess.run(
        ["codex", "exec", "--ephemeral", system],
        input=content, capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        print(f"codex exec failed ({result.returncode}): {result.stderr[:200]}", file=sys.stderr)
        return ""
    return result.stdout.strip()


@lru_cache(maxsize=1)
def _codex_available() -> bool:
    return shutil.which("codex") is not None


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def call_engine(content: str, system: str, max_tokens: int = 4000) -> str:
    """Unified LLM call. All cmd_* functions use this and only this.

    Strategy:
      1. codex exec available? → 128K context, single call, full content
      2. fallback → call_llm with auto-batching for small-context models
    """
    if _codex_available():
        result = _call_codex(content, system)
        if result:
            return result
        print("codex exec failed, falling back to call_llm", file=sys.stderr)
    return _call_llm_auto(content, system, max_tokens)


def _call_llm_auto(content: str, system: str, max_tokens: int) -> str:
    """call_llm with auto-batching for small-context models (e.g. glm-5.1 ~8K tokens)."""
    MAX_PROMPT_CHARS = 6000  # safe for glm-5.1: ~3K tokens content + system overhead
    if len(content) + len(system) < MAX_PROMPT_CHARS:
        return call_llm(content, system, max_tokens)

    # Split by natural section breaks (---), accumulate chunks under budget
    sections = re.split(r'\n---\n', content)
    budget = MAX_PROMPT_CHARS - len(system) - 500
    chunks, cur = [], ""
    for sec in sections:
        if len(cur) + len(sec) > budget:
            if cur:
                chunks.append(cur)
            cur = sec
        else:
            cur = cur + "\n---\n" + sec if cur else sec
    if cur:
        chunks.append(cur)

    parts = [call_llm(chunk, system, max_tokens) for chunk in chunks]
    return "\n".join(p for p in parts if p)
