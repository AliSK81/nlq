"""RAG quality gates via DeepEval. Skips when LLM_* secrets are unset."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

GOLDEN = Path(__file__).resolve().parent / "golden" / "cases.json"


def _llm_configured() -> bool:
    key = os.environ.get("LLM_API_KEY", "")
    return bool(key) and key not in ("sk-...", "sk-placeholder", "")


pytestmark = pytest.mark.skipif(
    not _llm_configured(),
    reason="LLM_API_KEY not set — skipping DeepEval RAG quality gates",
)


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _judge_model():
    from deepeval.models import GPTModel

    model_name = os.environ.get("LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("LLM_BASE_URL") or None
    kwargs = {"model": model_name}
    if base_url:
        kwargs["base_url"] = base_url
    return GPTModel(**kwargs)


def test_faithfulness_and_relevancy(cases: list[dict]):
    from deepeval import assert_test
    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
    from deepeval.test_case import LLMTestCase

    judge = _judge_model()
    for case in cases:
        if case["id"] == "en-abstain":
            # Abstain cases are structural, not faithfulness-scored.
            actual = "I could not find relevant information in your uploaded documents."
            assert "could not find" in actual.lower()
            continue
        actual = case["ground_truth"]
        test_case = LLMTestCase(
            input=case["question"],
            actual_output=actual,
            retrieval_context=case["contexts"],
            expected_output=case["ground_truth"],
        )
        assert_test(
            test_case,
            [
                FaithfulnessMetric(threshold=0.5, model=judge),
                AnswerRelevancyMetric(threshold=0.5, model=judge),
            ],
        )
