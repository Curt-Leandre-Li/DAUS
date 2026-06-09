from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .audit import audit_input_record, audit_result_record
from .schemas import (
    DAUS_MODE_SHAPLEY,
    DAUS_STATUS_APPLICABLE,
    DAUS_STATUS_NOT_APPLICABLE,
    DAUSAuditRecord,
    DAUSShapleyConfig,
    DAUSShapleyResult,
    DataAssetUtilityInput,
)
from .utility import (
    UtilityScoreFunction,
    apply_contribution_shares,
    build_inputs_by_participant_id,
    calculate_raw_shapley_attributions,
    evaluate_all_coalitions,
    evaluate_coalition,
)


def calculate_daus(
    inputs: Iterable[DataAssetUtilityInput],
    config: DAUSShapleyConfig | None = None,
    utility_score_function: UtilityScoreFunction | None = None,
) -> DAUSShapleyResult:
    """Compute Data Asset Utility Shapley attribution for contribution evidence."""
    config = config or DAUSShapleyConfig()
    utility_score_function = utility_score_function or UtilityScoreFunction()
    input_items = tuple(inputs)
    assumptions = tuple(config.assumptions) + (
        f"DAUS evaluated v(S) with {utility_score_function.name}.",
        "DAUS uses coalition marginal contribution, not a direct normalized weighted score.",
    )

    if not input_items:
        result = DAUSShapleyResult(
            status=DAUS_STATUS_NOT_APPLICABLE,
            participant_attributions=(),
            coalitions=(),
            total_utility_score=Decimal("0"),
            contribution_shares={},
            calculation_mode=DAUS_MODE_SHAPLEY,
            utility_score_function=utility_score_function.name,
            source_types=(),
            assumptions=assumptions,
            audit_records=(),
            not_applicable_reason="No contribution evidence was supplied.",
        )
        return result

    inputs_by_participant_id = build_inputs_by_participant_id(input_items)
    participant_ids = tuple(item.participant_id for item in input_items)
    coalitions = evaluate_all_coalitions(participant_ids, inputs_by_participant_id, config, utility_score_function)
    grand_coalition = evaluate_coalition(
        frozenset(participant_ids),
        inputs_by_participant_id,
        config,
        utility_score_function,
    )
    raw_attributions = calculate_raw_shapley_attributions(
        input_items,
        inputs_by_participant_id,
        config,
        utility_score_function,
    )
    total_shapley_value = sum(item.shapley_value for item in raw_attributions)
    if total_shapley_value <= 0:
        audit_records: tuple[DAUSAuditRecord, ...] = tuple(
            audit_input_record(input_item, config) for input_item in input_items
        )
        result = DAUSShapleyResult(
            status=DAUS_STATUS_NOT_APPLICABLE,
            participant_attributions=raw_attributions,
            coalitions=coalitions,
            total_utility_score=grand_coalition.utility_score,
            contribution_shares={},
            calculation_mode=DAUS_MODE_SHAPLEY,
            utility_score_function=utility_score_function.name,
            source_types=tuple(item.contribution_source_type for item in input_items),
            assumptions=assumptions,
            audit_records=audit_records,
            not_applicable_reason="Total Shapley utility contribution must be positive.",
        )
        return result

    attributions = apply_contribution_shares(raw_attributions)
    contribution_shares = {item.participant_id: item.contribution_share for item in attributions}
    partial_result = DAUSShapleyResult(
        status=DAUS_STATUS_APPLICABLE,
        participant_attributions=attributions,
        coalitions=coalitions,
        total_utility_score=grand_coalition.utility_score,
        contribution_shares=contribution_shares,
        calculation_mode=DAUS_MODE_SHAPLEY,
        utility_score_function=utility_score_function.name,
        source_types=tuple(item.contribution_source_type for item in input_items),
        assumptions=assumptions,
        audit_records=tuple(audit_input_record(input_item, config) for input_item in input_items),
    )
    audit_records = (*partial_result.audit_records, audit_result_record(partial_result, config))
    return DAUSShapleyResult(
        status=partial_result.status,
        participant_attributions=partial_result.participant_attributions,
        coalitions=partial_result.coalitions,
        total_utility_score=partial_result.total_utility_score,
        contribution_shares=partial_result.contribution_shares,
        calculation_mode=partial_result.calculation_mode,
        utility_score_function=partial_result.utility_score_function,
        source_types=partial_result.source_types,
        assumptions=partial_result.assumptions,
        audit_records=audit_records,
    )
