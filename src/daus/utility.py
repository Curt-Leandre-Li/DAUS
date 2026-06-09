from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from itertools import combinations
from math import factorial

from .schemas import (
    DAUSContributionInput,
    DAUSParticipantVector,
    DAUSUtilityConfig,
)


def score_to_factor(score: Decimal, config: DAUSUtilityConfig) -> Decimal:
    return score / config.score_factor_scale


def build_participant_vector(
    contribution_input: DAUSContributionInput,
    config: DAUSUtilityConfig,
) -> DAUSParticipantVector:
    quality_factor = score_to_factor(contribution_input.quality_score, config)
    coverage_factor = score_to_factor(contribution_input.coverage_score, config)
    scarcity_factor = score_to_factor(contribution_input.scarcity_score, config)
    sample_factor = score_to_factor(contribution_input.sample_score, config)
    adjusted_shuyuan = (
        contribution_input.measured_shuyuan
        * quality_factor
        * contribution_input.scenario_factor
        * coverage_factor
        * scarcity_factor
        * sample_factor
    )
    return DAUSParticipantVector(
        participant_id=contribution_input.participant_id,
        role=contribution_input.role,
        measured_shuyuan=contribution_input.measured_shuyuan,
        adjusted_shuyuan=adjusted_shuyuan,
        daus_score=adjusted_shuyuan,
        contribution_share=Decimal("0"),
        quality_factor=quality_factor,
        scenario_factor=contribution_input.scenario_factor,
        coverage_factor=coverage_factor,
        scarcity_factor=scarcity_factor,
        sample_factor=sample_factor,
        contribution_source_type=contribution_input.contribution_source_type,
        confidence_level=contribution_input.confidence_level,
        evidence=contribution_input.evidence,
        model_contribution_score=contribution_input.model_contribution_score,
        expert_score=contribution_input.expert_score,
    )


def coalition_utility(
    vectors: tuple[DAUSParticipantVector, ...],
    participant_ids: frozenset[str],
    config: DAUSUtilityConfig,
) -> Decimal:
    if not participant_ids:
        return Decimal("0")
    base_utility = sum(
        vector.adjusted_shuyuan
        for vector in vectors
        if vector.participant_id in participant_ids
    )
    return base_utility * (Decimal("1") + config.interaction_bonus) - config.risk_penalty


def calculate_shapley_scores(
    vectors: tuple[DAUSParticipantVector, ...],
    config: DAUSUtilityConfig,
) -> dict[str, Decimal]:
    participant_ids = tuple(vector.participant_id for vector in vectors)
    participant_count = len(participant_ids)
    if participant_count == 0:
        return {}

    denominator = Decimal(factorial(participant_count))
    scores = {participant_id: Decimal("0") for participant_id in participant_ids}
    for participant_id in participant_ids:
        others = tuple(item for item in participant_ids if item != participant_id)
        for subset_size in range(len(others) + 1):
            for subset in combinations(others, subset_size):
                coalition = frozenset(subset)
                coalition_with_participant = coalition | {participant_id}
                weight = Decimal(
                    factorial(subset_size)
                    * factorial(participant_count - subset_size - 1)
                ) / denominator
                marginal_contribution = coalition_utility(
                    vectors,
                    coalition_with_participant,
                    config,
                ) - coalition_utility(vectors, coalition, config)
                scores[participant_id] += weight * marginal_contribution
    return scores


def apply_scores_to_vectors(
    vectors: tuple[DAUSParticipantVector, ...],
    scores: dict[str, Decimal],
) -> tuple[DAUSParticipantVector, ...]:
    total_score = sum(scores.values())
    if total_score <= 0:
        return tuple(
            replace(
                vector,
                daus_score=scores.get(vector.participant_id, Decimal("0")),
                contribution_share=Decimal("0"),
            )
            for vector in vectors
        )
    return tuple(
        replace(
            vector,
            daus_score=scores[vector.participant_id],
            contribution_share=scores[vector.participant_id] / total_score,
        )
        for vector in vectors
    )
