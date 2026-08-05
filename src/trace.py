"""Ghi trace.jsonl - bang chung handoff that giua cac agent.

OWNER: P5 (Coordinator & Verifier)

README muc 8: "trace chay that cua 50 case (khong append, chi can luot chay moi nhat)"
-> moi lan chay phai TRUNCATE file, khong noi them.
"""

import json
from datetime import datetime, timezone
from typing import Any

from . import config


class Tracer:
    def __init__(self, path=None):
        self.path = path or config.TRACE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Truncate: chi giu luot chay moi nhat.
        self.path.write_text("", encoding="utf-8")

    def log(self, case_id: str, event: str, agent: str, payload: dict[str, Any]) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
            "event": event,
            "agent": agent,
            "model": config.MODEL_NAME,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def handoff(self, case_id: str, src: str, dst: str, summary: dict[str, Any]) -> None:
        """Ghi lai mot lan chuyen giao bang chung giua 2 agent."""
        self.log(case_id, "handoff", src, {"to": dst, "summary": summary})


def write_metadata(runtime_seconds: float, case_count: int) -> None:
    """Sinh logging/metadata.json theo README muc 8."""
    meta = {
        "model": config.MODEL_NAME,
        "parameter_size": config.MODEL_PARAMETER_SIZE,
        "provider": config.MODEL_PROVIDER,
        "endpoint": config.LLM_BASE_URL,
        "framework": "custom multi-agent orchestration (openai-sdk + pydantic)",
        "runtime": {
            "python": "3.11",
            "total_seconds": round(runtime_seconds, 2),
            "cases": case_count,
        },
        "policy_version": config.POLICY_VERSION,
        "agents": [
            "coordinator",
            "order_seller",
            "payment",
            "delivery",
            "policy",
            "verifier",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    config.METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.METADATA_PATH.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
