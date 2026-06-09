from __future__ import annotations

from decimal import Decimal

from .schemas import (
    DAUSAuditRecord,
    DAUSContributionInput,
    DAUSResult,
    DAUSUtilityConfig,
)


def input_audit_record(
    contribution_input: DAUSContributionInput,
    config: DAUSUtilityConfig,
) -> DAUSAuditRecord:
    return DAUSAuditRecord(
        event_type="input_validated",
        participant_id=contribution_input.participant_id,
        source_type=contribution_input.contribution_source_type,
        confidence_level=contribution_input.confidence_level,
        config=config.public_dict(),
        assumptions=(*config.assumptions, *contribution_input.assumptions),
        evidence=contribution_input.evidence,
        message="DAUS contribution input validated.",
    )


def result_audit_record(
    result: DAUSResult,
    config: DAUSUtilityConfig,
) -> DAUSAuditRecord:
    source_type = result.source_types[0] if len(result.source_types) == 1 else "simulation"
    return DAUSAuditRecord(
        event_type="result_finalized",
        source_type=source_type,
        confidence_level=_minimum_confidence(result),
        config=config.public_dict(),
        assumptions=result.assumptions,
        message=(
            "DAUS result finalized with Shapley marginal contribution."
            if result.used_shapley
            else "DAUS result finalized with adjusted-Shuyuan contribution mode."
        ),
    )


def _minimum_confidence(result: DAUSResult) -> Decimal:
    if not result.participant_vectors:
        return Decimal("0")
    return min(vector.confidence_level for vector in result.participant_vectors)
