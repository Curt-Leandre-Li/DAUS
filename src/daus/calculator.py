from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .audit import input_audit_record, result_audit_record
from .schemas import (
    DAUS_MODE_ADJUSTED_SHUYUAN,
    DAUS_MODE_SHAPLEY,
    DAUS_SHAPLEY_AUTO,
    DAUS_SHAPLEY_DISABLED,
    DAUS_SHAPLEY_REQUIRED,
    DAUS_STATUS_APPLICABLE,
    DAUS_STATUS_NOT_APPLICABLE,
    DAUSAuditRecord,
    DAUSContributionInput,
    DAUSResult,
    DAUSUtilityConfig,
)
from .utility import (
    apply_scores_to_vectors,
    build_participant_vector,
    calculate_shapley_scores,
)


def calculate_daus(
    contribution_inputs: Iterable[DAUSContributionInput],
    config: DAUSUtilityConfig | None = None,
) -> DAUSResult:
    effective_config = config or DAUSUtilityConfig()
    inputs = tuple(contribution_inputs)
    if not inputs:
        assumptions = (
            *effective_config.assumptions,
            "No DAUS contribution inputs were supplied.",
        )
        audit_record = DAUSAuditRecord(
            event_type="result_finalized",
            source_type="simulation",
            config=effective_config.public_dict(),
            assumptions=assumptions,
            message="DAUS returned not_applicable because no inputs were supplied.",
        )
        return DAUSResult(
            status=DAUS_STATUS_NOT_APPLICABLE,
            participant_vectors=(),
            total_daus_score=Decimal("0"),
            contribution_shares={},
            used_shapley=False,
            calculation_mode=DAUS_MODE_ADJUSTED_SHUYUAN,
            source_types=(),
            assumptions=assumptions,
            audit_records=(audit_record,),
            not_applicable_reason="no DAUS contribution inputs supplied",
        )

    _reject_duplicate_participants(inputs)
    input_audits = tuple(
        input_audit_record(contribution_input, effective_config)
        for contribution_input in inputs
    )
    vectors = tuple(
        build_participant_vector(contribution_input, effective_config)
        for contribution_input in inputs
    )

    has_model_contribution_data = all(
        contribution_input.model_contribution_score is not None
        for contribution_input in inputs
    )
    if (
        effective_config.shapley_mode == DAUS_SHAPLEY_REQUIRED
        and not has_model_contribution_data
    ):
        assumptions = (
            *effective_config.assumptions,
            "Shapley was required but field/model contribution evidence was missing.",
        )
        result = DAUSResult(
            status=DAUS_STATUS_NOT_APPLICABLE,
            participant_vectors=apply_scores_to_vectors(vectors, _zero_scores(vectors)),
            total_daus_score=Decimal("0"),
            contribution_shares=_zero_scores(vectors),
            used_shapley=False,
            calculation_mode=DAUS_MODE_SHAPLEY,
            source_types=_source_types(vectors),
            assumptions=assumptions,
            audit_records=input_audits,
            not_applicable_reason=(
                "field/model contribution evidence is required for DAUS Shapley mode"
            ),
        )
        return _with_result_audit(result, effective_config)

    if (
        effective_config.shapley_mode in {DAUS_SHAPLEY_AUTO, DAUS_SHAPLEY_REQUIRED}
        and has_model_contribution_data
    ):
        scores = calculate_shapley_scores(vectors, effective_config)
        used_shapley = True
        calculation_mode = DAUS_MODE_SHAPLEY
        shapley_assumption = (
            "DAUS Shapley mode used explicit field/model contribution evidence."
        )
    else:
        scores = {
            vector.participant_id: vector.adjusted_shuyuan
            for vector in vectors
        }
        used_shapley = False
        calculation_mode = DAUS_MODE_ADJUSTED_SHUYUAN
        shapley_assumption = (
            "No complete field/model contribution evidence was supplied; DAUS used "
            "deterministic adjusted-Shuyuan contribution mode."
        )

    vectors_with_scores = apply_scores_to_vectors(vectors, scores)
    total_score = sum(vector.daus_score for vector in vectors_with_scores)
    contribution_shares = {
        vector.participant_id: vector.contribution_share
        for vector in vectors_with_scores
    }
    assumptions = (*effective_config.assumptions, shapley_assumption)
    status = DAUS_STATUS_APPLICABLE
    not_applicable_reason = ""
    if total_score <= 0:
        status = DAUS_STATUS_NOT_APPLICABLE
        not_applicable_reason = "total DAUS score is zero"
        assumptions = (
            *assumptions,
            "DAUS did not allocate by hidden equal split when total score was zero.",
        )

    result = DAUSResult(
        status=status,
        participant_vectors=vectors_with_scores,
        total_daus_score=total_score,
        contribution_shares=contribution_shares,
        used_shapley=used_shapley,
        calculation_mode=calculation_mode,
        source_types=_source_types(vectors_with_scores),
        assumptions=assumptions,
        audit_records=input_audits,
        not_applicable_reason=not_applicable_reason,
    )
    return _with_result_audit(result, effective_config)


def daus_result_to_contribution_input_batch(
    result: DAUSResult,
    *,
    total_amount: float | None = None,
):
    ContributionInputBatch, ParticipantContributionInput = _allocation_contracts()
    participant_inputs = tuple(
        ParticipantContributionInput(
            participant_id=vector.participant_id,
            participant_display_name=vector.role,
            model_utility_score=float(vector.daus_score),
            contribution_source_type=vector.contribution_source_type,
            contribution_source_label="DAUS contribution utility score",
            source_assumption=(
                "DAUS score is contribution-utility evidence for negotiation "
                "and simulation, not a final contract split."
            ),
            metadata={
                "daus_calculation_mode": result.calculation_mode,
                "daus_used_shapley": result.used_shapley,
                "daus_status": result.status,
            },
        )
        for vector in result.participant_vectors
    )
    return ContributionInputBatch(
        participant_inputs=participant_inputs,
        total_amount=total_amount,
        metadata={
            "daus_status": result.status,
            "daus_calculation_mode": result.calculation_mode,
        },
    )


def _reject_duplicate_participants(inputs: tuple[DAUSContributionInput, ...]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for contribution_input in inputs:
        if contribution_input.participant_id in seen:
            duplicates.add(contribution_input.participant_id)
        seen.add(contribution_input.participant_id)
    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate participant_id values are not allowed: {duplicate_list}")


def _source_types(vectors) -> tuple[str, ...]:
    return tuple(sorted({vector.contribution_source_type for vector in vectors}))


def _zero_scores(vectors) -> dict[str, Decimal]:
    return {vector.participant_id: Decimal("0") for vector in vectors}


def _with_result_audit(result: DAUSResult, config: DAUSUtilityConfig) -> DAUSResult:
    return DAUSResult(
        status=result.status,
        participant_vectors=result.participant_vectors,
        total_daus_score=result.total_daus_score,
        contribution_shares=result.contribution_shares,
        used_shapley=result.used_shapley,
        calculation_mode=result.calculation_mode,
        source_types=result.source_types,
        assumptions=result.assumptions,
        audit_records=(*result.audit_records, result_audit_record(result, config)),
        not_applicable_reason=result.not_applicable_reason,
    )


def _allocation_contracts():
    """Load optional host allocation contracts for compatibility adapters.

    The standalone DAUS package has no runtime dependency on allocation. This
    helper is used only by daus_result_to_contribution_input_batch(), which is a
    host-integration adapter retained from the source project.
    """
    if __package__ and __package__.startswith("src."):
        try:
            from src.allocation import ContributionInputBatch, ParticipantContributionInput
        except ModuleNotFoundError as exc:
            if exc.name not in {"src", "src.allocation"}:
                raise
            raise ImportError(
                "daus_result_to_contribution_input_batch requires host allocation "
                "contracts; core DAUS scoring has no allocation dependency."
            ) from exc

        return ContributionInputBatch, ParticipantContributionInput
    try:
        from allocation import ContributionInputBatch, ParticipantContributionInput
    except ModuleNotFoundError as exc:
        if exc.name != "allocation":
            raise
        try:
            from src.allocation import ContributionInputBatch, ParticipantContributionInput
        except ModuleNotFoundError as src_exc:
            if src_exc.name not in {"src", "src.allocation"}:
                raise
            raise ImportError(
                "daus_result_to_contribution_input_batch requires host allocation "
                "contracts; core DAUS scoring has no allocation dependency."
            ) from src_exc
    return ContributionInputBatch, ParticipantContributionInput
