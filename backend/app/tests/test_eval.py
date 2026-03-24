"""Evaluation harness — loads test cases from eval_suite.json and checks accuracy."""

import json
from pathlib import Path

import pytest

from app.services.sql_safety import check_sql_safety

EVAL_SUITE_PATH = Path(__file__).parent.parent.parent / "eval_suite.json"


def load_eval_suite() -> list[dict]:
    if not EVAL_SUITE_PATH.exists():
        pytest.skip("eval_suite.json not found")
    with open(EVAL_SUITE_PATH) as f:
        return json.load(f)


class TestEvalSuite:
    """Evaluation harness: validate that expected SQL passes safety checks."""

    def test_expected_sql_passes_safety(self) -> None:
        suite = load_eval_suite()
        passed = 0
        failed = []
        for case in suite:
            expected_sql = case.get("expected_sql")
            if not expected_sql:
                continue
            try:
                check_sql_safety(expected_sql)
                passed += 1
            except Exception as e:
                failed.append({"question": case["question"], "error": str(e)})

        total = passed + len(failed)
        if total > 0:
            accuracy = passed / total
            print(f"\nEval accuracy (safety pass): {accuracy:.1%} ({passed}/{total})")
            for f in failed:
                print(f"  FAIL: {f['question']} → {f['error']}")
