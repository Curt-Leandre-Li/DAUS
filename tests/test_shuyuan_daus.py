from __future__ import annotations

import importlib
from decimal import Decimal

from daus import DAUSContributionInput, DAUSUtilityConfig, calculate_daus


def test_standalone_package_does_not_require_legacy_shuyuan_metering_surface() -> None:
    module = importlib.import_module("daus")

    assert hasattr(module, "calculate_daus")
    assert importlib.util.find_spec("shuyuan_metering") is None


def test_standalone_daus_result_matches_expected_legacy_migration_shape() -> None:
    result = calculate_daus(
        (
            DAUSContributionInput(
                participant_id="source-a",
                role="Display source-a",
                measured_shuyuan=Decimal("30"),
                quality_score=Decimal("90"),
                scenario_factor=Decimal("0.8"),
                coverage_score=Decimal("75"),
                scarcity_score=Decimal("50"),
                sample_score=Decimal("100"),
                expert_score=Decimal("90"),
                contribution_source_type="measured_data",
                confidence_level=Decimal("0.9"),
                evidence="legacy DAUS compatibility input",
                assumptions=("legacy path is compatibility only",),
            ),
            DAUSContributionInput(
                participant_id="source-b",
                role="Display source-b",
                measured_shuyuan=Decimal("15"),
                quality_score=Decimal("60"),
                scenario_factor=Decimal("0.4"),
                coverage_score=Decimal("50"),
                scarcity_score=Decimal("20"),
                sample_score=Decimal("100"),
                expert_score=Decimal("60"),
                contribution_source_type="measured_data",
                confidence_level=Decimal("0.6"),
                evidence="legacy DAUS compatibility input",
                assumptions=("legacy path is compatibility only",),
            ),
        ),
        DAUSUtilityConfig(shapley_mode="disabled"),
    )

    assert result.status == "applicable"
    assert result.used_shapley is False
    assert [vector.participant_id for vector in result.participant_vectors] == [
        "source-a",
        "source-b",
    ]
    assert [vector.daus_score for vector in result.participant_vectors] == [
        Decimal("8.100000"),
        Decimal("0.360000"),
    ]
    assert sum(result.contribution_shares.values()) == Decimal("1.000000")
