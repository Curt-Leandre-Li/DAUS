from __future__ import annotations

from .schemas import DAUSAuditRecord, DAUSShapleyConfig, DAUSShapleyResult, DataAssetUtilityInput


def audit_input_record(input_item: DataAssetUtilityInput, config: DAUSShapleyConfig) -> DAUSAuditRecord:
    return DAUSAuditRecord(
        event_type="contribution_evidence_registered",
        participant_id=input_item.participant_id,
        description="Contribution evidence accepted for DAUS coalition utility evaluation.",
        source_type=input_item.contribution_source_type,
        config_id=config.config_id,
        assumptions=input_item.assumptions,
    )


def audit_result_record(result: DAUSShapleyResult, config: DAUSShapleyConfig) -> DAUSAuditRecord:
    return DAUSAuditRecord(
        event_type="daus_shapley_attribution_completed",
        participant_id=None,
        description="DAUS Shapley attribution finalized over a data-asset utility function.",
        source_type=None,
        config_id=config.config_id,
        assumptions=result.assumptions,
    )
