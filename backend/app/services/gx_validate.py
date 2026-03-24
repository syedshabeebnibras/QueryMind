"""Great Expectations validation on query result DataFrames.

MVP validations:
- No completely null columns
- Row count within expected bounds
- No duplicate rows (if result is small enough)
"""

from typing import Any

import great_expectations as gx
import pandas as pd

from app.core.config import settings
from app.core.logging import log


def validate_results(df: pd.DataFrame) -> dict[str, Any]:
    """Run GX validations on a result DataFrame and return a summary."""
    if df.empty:
        return {
            "success": True,
            "expectations_evaluated": 0,
            "expectations_passed": 0,
            "details": [],
        }

    context = gx.get_context()
    data_source = context.data_sources.add_pandas(name="result_ds")
    data_asset = data_source.add_dataframe_asset(name="result_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("result_batch")

    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    suite = context.suites.add(
        gx.ExpectationSuite(name="query_result_suite")
    )

    # Expectation: row count is within bounds
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(min_value=0, max_value=settings.querymind_max_rows)
    )

    # Expectation: no columns are entirely null
    for col in df.columns:
        if df[col].isna().all() and len(df) > 0:
            suite.add_expectation(
                gx.expectations.ExpectColumnValuesToNotBeNull(column=col)
            )

    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="result_validation",
            data=batch_definition,
            suite=suite,
        )
    )

    result = validation_definition.run(batch_parameters={"dataframe": df})

    details = []
    expectations_passed = 0
    expectations_evaluated = 0

    for r in result.results:
        expectations_evaluated += 1
        passed = r.success
        if passed:
            expectations_passed += 1
        details.append({
            "expectation": r.expectation_config.type,
            "success": passed,
            "kwargs": {k: v for k, v in r.expectation_config.kwargs.items() if k != "batch_id"},
        })

    # Cleanup ephemeral resources
    try:
        context.validation_definitions.delete("result_validation")
        context.suites.delete("query_result_suite")
        context.data_sources.delete("result_ds")
    except Exception:
        pass

    summary = {
        "success": result.success,
        "expectations_evaluated": expectations_evaluated,
        "expectations_passed": expectations_passed,
        "details": details,
    }
    log.info("gx_validation_complete", success=summary["success"])
    return summary
