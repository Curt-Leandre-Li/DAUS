from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from itertools import combinations
from math import factorial
from typing import Mapping

from .schemas import (
    DAUSShapleyConfig,
    DataAssetCoalition,
    DataAssetUtilityInput,
    ParticipantShapleyAttribution,
)


def score_to_factor(score: Decimal, config: DAUSShapleyConfig) -> Decimal:
    """Convert a 0-100 utility signal into a multiplicative factor."""
    return score / config.score_factor_scale


class UtilityScoreFunction:
    """Callable v(S) for DAUS coalition utility evaluation.

    The default implementation is additive and auditable. It is an MVP utility
    score function; callers may provide a subclass or callable for coalition
    interactions while keeping the Shapley attribution contract unchanged.
    """

    name = "additive_data_asset_utility"

    def individual_utility_score(
        self,
        evidence: DataAssetUtilityInput,
        config: DAUSShapleyConfig,
    ) -> Decimal:
        return (
            evidence.measured_contribution_units
            * score_to_factor(evidence.quality_score, config)
            * score_to_factor(evidence.coverage_score, config)
            * score_to_factor(evidence.scarcity_score, config)
            * score_to_factor(evidence.sample_score, config)
            * score_to_factor(evidence.scenario_fit_score, config)
            * score_to_factor(evidence.compliance_usability_score, config)
        )

    def __call__(
        self,
        coalition: DataAssetCoalition,
        inputs_by_participant_id: Mapping[str, DataAssetUtilityInput],
        config: DAUSShapleyConfig,
    ) -> Decimal:
        return sum(
            self.individual_utility_score(inputs_by_participant_id[participant_id], config)
            for participant_id in coalition.participant_ids
        )


def build_inputs_by_participant_id(
    inputs: tuple[DataAssetUtilityInput, ...],
) -> dict[str, DataAssetUtilityInput]:
    result: dict[str, DataAssetUtilityInput] = {}
    for item in inputs:
        if item.participant_id in result:
            raise ValueError(f"duplicate participant_id: {item.participant_id}")
        result[item.participant_id] = item
    return result


def coalition_ids(participant_ids: tuple[str, ...]) -> tuple[frozenset[str], ...]:
    coalitions: list[frozenset[str]] = []
    for size in range(len(participant_ids) + 1):
        for subset in combinations(participant_ids, size):
            coalitions.append(frozenset(subset))
    return tuple(coalitions)


def evaluate_coalition(
    participant_ids: frozenset[str],
    inputs_by_participant_id: Mapping[str, DataAssetUtilityInput],
    config: DAUSShapleyConfig,
    utility_score_function: UtilityScoreFunction,
) -> DataAssetCoalition:
    empty_score_coalition = DataAssetCoalition(participant_ids=participant_ids)
    utility_score = utility_score_function(empty_score_coalition, inputs_by_participant_id, config)
    return DataAssetCoalition(participant_ids=participant_ids, utility_score=utility_score)


def evaluate_all_coalitions(
    participant_ids: tuple[str, ...],
    inputs_by_participant_id: Mapping[str, DataAssetUtilityInput],
    config: DAUSShapleyConfig,
    utility_score_function: UtilityScoreFunction,
) -> tuple[DataAssetCoalition, ...]:
    return tuple(
        evaluate_coalition(ids, inputs_by_participant_id, config, utility_score_function)
        for ids in coalition_ids(participant_ids)
    )


def calculate_raw_shapley_attributions(
    inputs: tuple[DataAssetUtilityInput, ...],
    inputs_by_participant_id: Mapping[str, DataAssetUtilityInput],
    config: DAUSShapleyConfig,
    utility_score_function: UtilityScoreFunction,
) -> tuple[ParticipantShapleyAttribution, ...]:
    participant_ids = tuple(item.participant_id for item in inputs)
    participant_count = len(participant_ids)
    denominator = Decimal(factorial(participant_count))
    attributions: list[ParticipantShapleyAttribution] = []

    for item in inputs:
        others = tuple(participant_id for participant_id in participant_ids if participant_id != item.participant_id)
        shapley_value = Decimal("0")
        marginal_values: list[Decimal] = []
        for size in range(len(others) + 1):
            for subset in combinations(others, size):
                subset_ids = frozenset(subset)
                with_item_ids = frozenset((*subset, item.participant_id))
                before = evaluate_coalition(subset_ids, inputs_by_participant_id, config, utility_score_function)
                after = evaluate_coalition(with_item_ids, inputs_by_participant_id, config, utility_score_function)
                marginal = after.utility_score - before.utility_score
                weight = Decimal(factorial(size) * factorial(participant_count - size - 1)) / denominator
                shapley_value += weight * marginal
                marginal_values.append(marginal)

        standalone = evaluate_coalition(
            frozenset({item.participant_id}),
            inputs_by_participant_id,
            config,
            utility_score_function,
        )
        attributions.append(
            ParticipantShapleyAttribution(
                participant_id=item.participant_id,
                role=item.role,
                standalone_utility_score=standalone.utility_score,
                shapley_value=shapley_value,
                contribution_share=Decimal("0"),
                contribution_source_type=item.contribution_source_type,
                confidence_level=item.confidence_level,
                evidence=item.evidence,
                marginal_contributions=tuple(marginal_values),
                assumptions=item.assumptions,
            )
        )
    return tuple(attributions)


def apply_contribution_shares(
    attributions: tuple[ParticipantShapleyAttribution, ...],
) -> tuple[ParticipantShapleyAttribution, ...]:
    total = sum(item.shapley_value for item in attributions)
    if total <= 0:
        return attributions
    return tuple(replace(item, contribution_share=item.shapley_value / total) for item in attributions)
