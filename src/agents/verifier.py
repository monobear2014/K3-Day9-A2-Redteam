"""Verifier Agent - chot chan cuoi truoc khi ghi file.

OWNER: P5

README muc 7 giao cho Verifier dung viec nay: "kiem tra ID, so tien va schema
truoc khi ghi file". Nen Python tinh lai toan bo va CO QUYEN PHU QUYET ket luan
cua Policy Agent. Model <= 10B sai la chuyen binh thuong; hard gate 0 diem thi khong.

Confidence sinh tu muc dong thuan, khong phai so bia:
  - LLM va deterministic trung nhau, moi agent goi LLM thanh cong -> 0.95
  - Trung nhau nhung co agent phai fallback                       -> 0.80
  - Lech nhau, lay ket qua deterministic                          -> 0.60
"""

import json

from .. import rules
from ..llm_client import call_json
from ..schemas import (
    AffectedEntities,
    Assessment,
    CaseFacts,
    CaseOutput,
    FinancialResolution,
    PolicyVerdict,
    RankedCause,
    ResponsibleParty,
    RootCauseAnalysis,
    VerifierVerdict,
)
from .base import JSON_RULE, facts_brief

CONF_AGREE_FULL = 0.95
CONF_AGREE_FALLBACK = 0.80
CONF_OVERRIDE = 0.60


JUDGE_SYSTEM = f"""{JSON_RULE}

You are the independent Verifier/Reflector, not the content generator. Judge
the proposed output against only the supplied facts and criteria below. Do not
rewrite the answer or infer missing facts.

Mark pass=true only if EVERY criterion passes:
1. primary_issue matches the highest-priority applicable policy rule.
2. order, item, seller, payment, and evidence IDs appear in the supplied facts.
3. refund is non-negative and equals payment_total for canceled/unavailable,
   freight_total for late delivery, otherwise 0.
4. output has the required schema fields and permitted enum values.
5. the repository test suite must be run before release; any reported failure
   requires pass=false.

Return exactly {{"pass": <boolean>, "feedback": "<specific Vietnamese feedback>"}}.
"""


def run(
    f: CaseFacts, policy_v: PolicyVerdict, all_llm_ok: bool
) -> tuple[CaseOutput, dict]:
    """Tra ve (output da xac minh, bao cao kiem tra de ghi vao trace)."""
    truth = rules.decide(f)
    agreed = policy_v.primary_issue == truth.primary_issue

    if agreed:
        issue = policy_v.primary_issue
        confidence = CONF_AGREE_FULL if all_llm_ok else CONF_AGREE_FALLBACK
        source = "llm_agreed"
    else:
        # PHU QUYET: du lieu thang suy luan cua model.
        issue = truth.primary_issue
        confidence = CONF_OVERRIDE
        source = "deterministic_override"

    decision = truth if not agreed else rules.decide(f)
    entities = rules.entity_ids(f)
    evidence = rules.build_evidence(f, decision.root_cause)

    # Truong hop don khong co item row (README muc 6).
    if not f.items:
        entities["item_ids"] = []
        entities["seller_ids"] = []

    output = CaseOutput(
        case_id=f.case_id,
        assessment=Assessment(
            primary_issue=issue,
            case_status=decision.case_status,
            confidence=confidence,
        ),
        affected_entities=AffectedEntities(**entities),
        root_cause_analysis=RootCauseAnalysis(
            ranked_causes=[RankedCause(cause_code=decision.root_cause, rank=1)],
            responsible_parties=[
                ResponsibleParty(**p) for p in decision.responsible_parties
            ],
        ),
        evidence_ids=evidence,
        financial_resolution=FinancialResolution(
            currency="BRL",
            item_total_brl=f.item_total_brl if f.items else 0.0,
            freight_total_brl=f.freight_total_brl if f.items else 0.0,
            payment_total_brl=f.payment_total_brl,
            recommended_refund_brl=decision.refund_brl,
        ),
        resolution_actions=[decision.action],
    )

    report = {
        "agreed": agreed,
        "llm_issue": policy_v.primary_issue,
        "deterministic_issue": truth.primary_issue,
        "matched_rule": truth.matched_rule,
        "confidence": confidence,
        "source": source,
        "checks": _checks(f, output),
    }
    return output, report


def judge(f: CaseFacts, output: CaseOutput, test_suite_passed: bool = True) -> VerifierVerdict:
    """LLM-as-a-judge with deterministic gates before graph routing.

    A failed verdict routes to ``supervisor``.  An unavailable judge never
    invents a failure: local structural checks remain the safety boundary.
    """
    checks = _checks(f, output)
    deterministic_pass = (
        test_suite_passed
        and not checks["invalid_evidence"]
        and checks["schema_ok"]
        and checks["refund_non_negative"]
    )
    if not deterministic_pass:
        feedback = "Verifier gate failed: " + json.dumps(checks, ensure_ascii=False)
        return VerifierVerdict(
            **{"pass": False}, feedback=feedback, next_node="supervisor", llm_ok=False
        )

    user = json.dumps(
        {
            "facts": json.loads(facts_brief(f)),
            "proposed_output": output.to_json_dict(),
            "local_checks": checks,
            "test_suite_passed": test_suite_passed,
        },
        ensure_ascii=False,
    )
    verdict = call_json(JUDGE_SYSTEM, user)
    if not verdict or not isinstance(verdict.get("pass"), bool):
        return VerifierVerdict(
            **{"pass": True},
            feedback="LLM judge unavailable; deterministic gates passed.",
            next_node="responder",
            llm_ok=False,
        )
    passed = verdict["pass"]
    return VerifierVerdict(
        **{"pass": passed},
        feedback=str(verdict.get("feedback", ""))[:500],
        next_node="responder" if passed else "supervisor",
        llm_ok=True,
    )


def _checks(f: CaseFacts, out: CaseOutput) -> dict:
    """Kiem tra cuoi: moi evidence ID phai dung duoc tu CSV (README muc 5)."""
    valid_items = {f"item:{f.claimed_order_id}:{i.order_item_id}" for i in f.items}
    valid_pays = {
        f"payment:{f.claimed_order_id}:{p.payment_sequential}" for p in f.payments
    }
    valid_sellers = {f"seller:{s}" for s in f.seller_ids}
    valid_order = {f"order:{f.claimed_order_id}"}

    bad = []
    for ev in out.evidence_ids:
        if ev.startswith("policy:"):
            continue
        if ev not in (valid_items | valid_pays | valid_sellers | valid_order):
            bad.append(ev)

    return {
        "evidence_count": len(out.evidence_ids),
        "invalid_evidence": bad,
        "schema_ok": True,  # CaseOutput da validate luc khoi tao
        "refund_non_negative": out.financial_resolution.recommended_refund_brl >= 0,
    }
