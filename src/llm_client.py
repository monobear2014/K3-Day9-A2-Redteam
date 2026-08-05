"""Client goi LLM, dung cho moi endpoint OpenAI-compatible.

OWNER: P5 (Coordinator & Verifier)

Model <= 10B hay tra JSON hong. Chien luoc 3 lop:
  1. Ep JSON mode (response_format).
  2. Retry bang tenacity khi timeout / rate limit.
  3. Parse hong sau N lan -> tra None, agent tu fallback sang deterministic.
Tha mat diem confidence con hon vo schema roi an hard gate 0 diem.
"""

import json
from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from . import config

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
            timeout=config.LLM_TIMEOUT_S,
        )
    return _client


@retry(
    stop=stop_after_attempt(config.LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _raw_call(system: str, user: str) -> str:
    resp = get_client().chat.completions.create(
        model=config.MODEL_NAME,
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def call_json(system: str, user: str) -> Optional[dict]:
    """Goi LLM, tra dict hoac None neu that bai. KHONG BAO GIO raise len agent."""
    try:
        text = _raw_call(system, user)
    except Exception as exc:  # noqa: BLE001 - agent can biet fail, khong can loai loi
        print(f"  [llm] call failed: {type(exc).__name__}: {exc}")
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Model nho hay boc JSON trong ```json ... ``` hoac them loi dan.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        print(f"  [llm] khong parse duoc JSON: {text[:120]!r}")
        return None


def health_check() -> bool:
    """Kiem tra endpoint song truoc khi chay 50 case. Chay: python -m src.llm_client"""
    out = call_json(
        'Ban tra ve JSON hop le. Tra dung: {"ok": true}',
        "Tra ve {\"ok\": true}",
    )
    return bool(out and out.get("ok"))


if __name__ == "__main__":
    print(f"model   : {config.MODEL_NAME} ({config.MODEL_PARAMETER_SIZE})")
    print(f"endpoint: {config.LLM_BASE_URL}")
    print("health  :", "OK" if health_check() else "FAIL")
