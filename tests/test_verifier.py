from src.agents import verifier
from src.schemas import CaseFacts, FinancialResolution, CaseOutput, Assessment, AffectedEntities, RootCauseAnalysis


def facts() -> CaseFacts:
    return CaseFacts(
        case_id="EC_VERIFY", claimed_order_id="order_1", order_found=True,
        order_status="delivered", delivered_late=False, payment_matches=True,
    )


def output() -> CaseOutput:
    return CaseOutput(
        case_id="EC_VERIFY",
        assessment=Assessment(primary_issue="unsupported_late_claim", case_status="no_action", confidence=0.95),
        affected_entities=AffectedEntities(order_ids=["order_1"]),
        root_cause_analysis=RootCauseAnalysis(),
        evidence_ids=["order:order_1"],
        financial_resolution=FinancialResolution(item_total_brl=0, freight_total_brl=0, payment_total_brl=0, recommended_refund_brl=0),
        resolution_actions=["reject_late_refund"],
    )


def test_judge_routes_to_supervisor_when_test_suite_failed():
    result = verifier.judge(facts(), output(), test_suite_passed=False)
    assert result.passed is False
    assert result.next_node == "supervisor"


def test_judge_routes_to_responder_when_local_gates_pass(monkeypatch):
    monkeypatch.setattr(verifier, "call_json", lambda *_: {"pass": True, "feedback": "OK"})
    result = verifier.judge(facts(), output())
    assert result.passed is True
    assert result.next_node == "responder"
