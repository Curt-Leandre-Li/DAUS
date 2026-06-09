from __future__ import annotations

from decimal import Decimal

import pytest

from daus import (
    DAUS_MODE_ADJUSTED_SHUYUAN,
    DAUS_MODE_SHAPLEY,
    DAUS_STATUS_APPLICABLE,
    DAUS_STATUS_NOT_APPLICABLE,
    DAUSContributionInput,
    DAUSUtilityConfig,
    calculate_daus,
)


def daus_input(
    participant_id: str,
    measured_shuyuan: str,
    *,
    source_type: str = "measured_data",
    model_contribution_score: str | None = None,
) -> DAUSContributionInput:
    return DAUSContributionInput(
        participant_id=participant_id,
        role=f"Participant {participant_id.upper()}",
        measured_shuyuan=Decimal(measured_shuyuan),
        quality_score=Decimal("100"),
        scenario_factor=Decimal("1"),
        coverage_score=Decimal("100"),
        scarcity_score=Decimal("100"),
        sample_score=Decimal("100"),
        model_contribution_score=(
            None if model_contribution_score is None else Decimal(model_contribution_score)
        ),
        expert_score=Decimal("80"),
        contribution_source_type=source_type,
        confidence_level=Decimal("0.8"),
        evidence=f"{source_type} fixture evidence",
        assumptions=(f"{source_type} DAUS test assumption",),
    )


def test_single_participant_adjusted_shuyuan_formula() -> None:
    result = calculate_daus(
        (
            DAUSContributionInput(
                participant_id="a",
                role="Participant A",
                measured_shuyuan=Decimal("100"),
                quality_score=Decimal("90"),
                scenario_factor=Decimal("1.2"),
                coverage_score=Decimal("80"),
                scarcity_score=Decimal("50"),
                sample_score=Decimal("100"),
                contribution_source_type="measured_data",
                confidence_level=Decimal("0.9"),
                evidence="measured Shuyuan fixture",
            ),
        )
    )

    vector = result.participant_vectors[0]
    assert result.status == DAUS_STATUS_APPLICABLE
    assert vector.adjusted_shuyuan == Decimal("43.200")
    assert vector.daus_score == Decimal("43.200")
    assert vector.contribution_share == Decimal("1")
    assert result.used_shapley is False


def test_multi_participant_scores_normalize_to_one() -> None:
    result = calculate_daus((daus_input("a", "50"), daus_input("b", "150")))

    assert result.total_daus_score == Decimal("200")
    assert result.contribution_shares["a"] == Decimal("0.25")
    assert result.contribution_shares["b"] == Decimal("0.75")
    assert sum(result.contribution_shares.values()) == Decimal("1.00")


def test_duplicate_participant_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate participant_id"):
        calculate_daus((daus_input("a", "1"), daus_input("a", "2")))


def test_empty_input_returns_not_applicable_result() -> None:
    result = calculate_daus(())

    assert result.status == DAUS_STATUS_NOT_APPLICABLE
    assert result.participant_vectors == ()
    assert result.total_daus_score == Decimal("0")
    assert result.not_applicable_reason == "no DAUS contribution inputs supplied"


def test_negative_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="measured_shuyuan must be non-negative"):
        daus_input("a", "-1")

    with pytest.raises(ValueError, match="scenario_factor must be positive"):
        DAUSContributionInput(
            participant_id="a",
            role="Participant A",
            measured_shuyuan=Decimal("1"),
            quality_score=Decimal("100"),
            scenario_factor=Decimal("-1"),
            coverage_score=Decimal("100"),
            scarcity_score=Decimal("100"),
            sample_score=Decimal("100"),
            contribution_source_type="measured_data",
            confidence_level=Decimal("0.9"),
            evidence="invalid factor fixture",
        )


def test_source_types_are_retained_in_vectors() -> None:
    result = calculate_daus(
        (
            daus_input("a", "20", source_type="measured_data"),
            daus_input("b", "20", source_type="expert_estimate"),
            daus_input("c", "20", source_type="simulation"),
            daus_input("d", "20", source_type="contract_agreement"),
        )
    )

    assert [vector.contribution_source_type for vector in result.participant_vectors] == [
        "measured_data",
        "expert_estimate",
        "simulation",
        "contract_agreement",
    ]
    assert result.source_types == (
        "contract_agreement",
        "expert_estimate",
        "measured_data",
        "simulation",
    )


def test_shapley_and_adjusted_shuyuan_modes_have_consistent_output_shape() -> None:
    adjusted = calculate_daus(
        (daus_input("a", "30"), daus_input("b", "70")),
        DAUSUtilityConfig(shapley_mode="disabled"),
    )
    shapley = calculate_daus(
        (
            daus_input("a", "30", model_contribution_score="60"),
            daus_input("b", "70", model_contribution_score="70"),
        )
    )

    assert adjusted.calculation_mode == DAUS_MODE_ADJUSTED_SHUYUAN
    assert shapley.calculation_mode == DAUS_MODE_SHAPLEY
    assert adjusted.used_shapley is False
    assert shapley.used_shapley is True
    assert [vector.participant_id for vector in adjusted.participant_vectors] == [
        vector.participant_id for vector in shapley.participant_vectors
    ]
    assert set(adjusted.contribution_shares) == set(shapley.contribution_shares)


def test_required_shapley_without_model_data_returns_not_applicable() -> None:
    result = calculate_daus(
        (daus_input("a", "10"), daus_input("b", "20")),
        DAUSUtilityConfig(shapley_mode="required"),
    )

    assert result.status == DAUS_STATUS_NOT_APPLICABLE
    assert result.used_shapley is False
    assert "field/model contribution evidence" in result.not_applicable_reason


def test_audit_records_include_source_type_config_and_assumptions() -> None:
    result = calculate_daus((daus_input("a", "10", source_type="simulation"),))

    assert result.audit_records
    for record in result.audit_records:
        assert record.source_type in {"simulation", "measured_data"}
        assert record.config["config_id"] == "daus_mvp_v1"
        assert record.assumptions
    assert any(record.source_type == "simulation" for record in result.audit_records)


def test_optional_allocation_adapter_fails_clearly_without_host_contracts() -> None:
    from daus import daus_result_to_contribution_input_batch

    result = calculate_daus((daus_input("a", "20"),))

    with pytest.raises(ImportError, match="requires host allocation contracts"):
        daus_result_to_contribution_input_batch(result)
