import httpx
import pytest
from server.pitchstate.jev import ACTIONS, PHASES, JevJudge, JevUnavailable


def response():
    def choice(options):
        return {
            "type": "choice",
            "choice": next(iter(options)),
            "probabilities": {k: 1.0 if i == 0 else 0.0 for i, k in enumerate(options)},
            "confidence": 0.8,
        }

    return {
        "model": "jev-1.13.0",
        "answers": {
            "next_action": choice(ACTIONS),
            "phase": choice(PHASES),
            "dangerous_run": {"type": "noul", "noul": 0.1},
        },
        "usage": {"input_tokens": 500, "output_tokens": 60},
    }


def test_cache_and_durable_budget(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    judge = JevJudge(tmp_path, api_key="test", max_calls=1, client=client)
    assert judge.judge({"a": 1})["cached"] is False
    assert judge.judge({"a": 1})["cached"] is True
    assert len(calls) == 1
    with pytest.raises(JevUnavailable, match="budget"):
        JevJudge(tmp_path, api_key="test", max_calls=1, client=client).judge({"a": 2})
    assert judge.usage()["accountedInputTokens"] == 500


def test_rejects_invalid_probabilities_without_paid_retry(tmp_path):
    bad = response()
    bad["answers"]["next_action"]["probabilities"]["pass"] = 4
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=bad)))
    judge = JevJudge(tmp_path, api_key="test", client=client)
    with pytest.raises(JevUnavailable):
        judge.judge({"a": 1})
    with pytest.raises(JevUnavailable, match="already failed"):
        judge.judge({"a": 1})
    assert judge.usage()["reservedCalls"] == 1


def test_does_not_follow_redirects_or_expose_error_body(tmp_path):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                302, text="secret", headers={"location": "https://example.com"}
            )
        )
    )
    with pytest.raises(JevUnavailable, match="HTTP 302"):
        JevJudge(tmp_path, api_key="test", client=client).judge({})


def test_dynamic_decisions_aggregate_categories_without_inventing_probabilities(tmp_path):
    options = [
        {"id": "pass_1_2", "label": "#1 to #2 pass", "kind": "pass"},
        {"id": "carry_1", "label": "#1 carries", "kind": "carry"},
        {"id": "insufficient_evidence", "label": "Unknown", "kind": "insufficient_evidence"},
    ]

    def handler(request):
        import json

        payload = json.loads(request.content)
        assert set(payload["questions"]["next_action"]["criteria"]) == {o["id"] for o in options}
        body = response()
        body["answers"]["next_action"] = {
            "type": "choice",
            "choice": "pass_1_2",
            "probabilities": {"pass_1_2": 0.6, "carry_1": 0.3, "insufficient_evidence": 0.1},
            "confidence": 0.5,
        }
        return httpx.Response(200, json=body)

    result = JevJudge(
        tmp_path, api_key="test", client=httpx.Client(transport=httpx.MockTransport(handler))
    ).judge({"decisionCandidates": options})
    assert result["nextDecision"]["choice"] == "pass_1_2"
    assert result["nextAction"]["probabilities"]["pass"] == 0.6
    assert result["candidates"] == options
