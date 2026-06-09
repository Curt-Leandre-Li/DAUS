from __future__ import annotations

from decimal import Decimal

import pytest

from daus import (
    DAUS_STATUS_APPLICABLE,
    DAUS_STATUS_NOT_APPLICABLE,
    DataAssetCoalition,
    DataAssetUtilityInput,
    UtilityScoreFunction,
    calculate_daus,
)


def utility_input(
    participant_id: str,
    units: str,
    *,
    source_type: str = "measured_data",
) -> DataAssetUtilityInput:
    return DataAssetUtilityInput(
        participant_id=participant_id,
        role="data_provider",
        measured_contribution_units=Decimal(units),
        quality_score=Decimal("100"),
        coverage_score=Decimal("100"),
        scarcity_score=Decimal("100"),
        sample_score=Decimal("100"),
        contribution_source_type=source_type,
        confidence_level=Decimal("0.9"),
        evidence=f"evidence for {participant_id}",
    )


def attribution_by_id(result):
    return {item.participant_id: item for item in result.participant_attributions}


def test_single_subject_returns_shapley_attribution() -> None:
    result = calculate_daus([utility_input("source-a", "25")])

    assert result.status == DAUS_STATUS_APPLICABLE
    assert result.used_shapley is True
    assert result.total_utility_score == Decimal("25")
    attribution = result.participant_attributions[0]
    assert attribution.shapley_value == Decimal("25")
    assert attribution.contribution_share == Decimal("1")


def test_additive_mvp_is_shapley_special_case() -> None:
    result = calculate_daus([utility_input("source-a", "50"), utility_input("source-b", "150")])
    by_id = attribution_by_id(result)

    assert result.total_utility_score == Decimal("200")
    assert by_id["source-a"].shapley_value == Decimal("50")
    assert by_id["source-b"].shapley_value == Decimal("150")
    assert by_id["source-a"].contribution_share == Decimal("0.25")
    assert by_id["source-b"].contribution_share == Decimal("0.75")
    assert sum(result.contribution_shares.values()) == Decimal("1.00")


def test_non_additive_utility_uses_coalition_marginal_contribution() -> None:
    class PairBonusUtility(UtilityScoreFunction):
        name = "pair_bonus_data_asset_utility"

        def __call__(self, coalition, inputs_by_participant_id, config):
            base = super().__call__(coalition, inputs_by_participant_id, config)
            if coalition.participant_ids == frozenset({"source-a", "source-b"}):
                return base + Decimal("12")
            return base

    result = calculate_daus(
        [utility_input("source-a", "10"), utility_input("source-b", "10")],
        utility_score_function=PairBonusUtility(),
    )
    by_id = attribution_by_id(result)

    assert result.total_utility_score == Decimal("32")
    assert by_id["source-a"].standalone_utility_score == Decimal("10")
    assert by_id["source-b"].standalone_utility_score == Decimal("10")
    assert by_id["source-a"].shapley_value == Decimal("16")
    assert by_id["source-b"].shapley_value == Decimal("16")
    assert by_id["source-a"].shapley_value != by_id["source-a"].standalone_utility_score
    assert "DAUS uses coalition marginal contribution" in " ".join(result.assumptions)


def test_source_type_is_preserved_without_changing_formula_secretly() -> None:
    measured = calculate_daus([utility_input("source-a", "100", source_type="measured_data")])
    simulated = calculate_daus([utility_input("source-a", "100", source_type="simulation")])

    assert measured.participant_attributions[0].shapley_value == simulated.participant_attributions[0].shapley_value
    assert measured.participant_attributions[0].contribution_source_type == "measured_data"
    assert simulated.participant_attributions[0].contribution_source_type == "simulation"


def test_empty_input_is_not_applicable() -> None:
    result = calculate_daus([])

    assert result.status == DAUS_STATUS_NOT_APPLICABLE
    assert result.not_applicable_reason == "No contribution evidence was supplied."
    assert result.participant_attributions == ()


def test_duplicate_participant_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate participant_id"):
        calculate_daus([utility_input("source-a", "10"), utility_input("source-a", "20")])


def test_negative_contribution_units_are_rejected() -> None:
    with pytest.raises(ValueError, match="measured_contribution_units"):
        utility_input("source-a", "-1")


@pytest.mark.parametrize("bad_value", ["NaN", "Infinity", float("inf")])
def test_non_finite_inputs_are_rejected(bad_value) -> None:
    with pytest.raises(ValueError, match="finite"):
        DataAssetUtilityInput(
            participant_id="source-a",
            role="data_provider",
            measured_contribution_units=bad_value,
            quality_score=Decimal("100"),
            coverage_score=Decimal("100"),
            scarcity_score=Decimal("100"),
            sample_score=Decimal("100"),
            contribution_source_type="measured_data",
            confidence_level=Decimal("0.9"),
            evidence="bad evidence",
        )


def test_invalid_source_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="contribution_source_type"):
        utility_input("source-a", "10", source_type="unknown")


def test_coalitions_are_exposed_with_utility_scores() -> None:
    result = calculate_daus([utility_input("source-a", "10"), utility_input("source-b", "20")])

    coalitions = {coalition.participant_ids: coalition.utility_score for coalition in result.coalitions}
    assert coalitions[frozenset()] == Decimal("0")
    assert coalitions[frozenset({"source-a"})] == Decimal("10")
    assert coalitions[frozenset({"source-b"})] == Decimal("20")
    assert coalitions[frozenset({"source-a", "source-b"})] == Decimal("30")
    assert all(isinstance(coalition, DataAssetCoalition) for coalition in result.coalitions)


def test_audit_records_include_source_type_config_and_assumptions() -> None:
    result = calculate_daus([utility_input("source-a", "10", source_type="expert_estimate")])

    assert result.audit_records
    input_record = result.audit_records[0]
    assert input_record.source_type == "expert_estimate"
    assert input_record.config_id == "daus_shapley_v1"
    assert result.assumptions
