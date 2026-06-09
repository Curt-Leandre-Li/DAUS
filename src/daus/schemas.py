from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Mapping

DAUS_SOURCE_TYPES = frozenset(
    {"measured_data", "expert_estimate", "contract_agreement", "simulation"}
)
DAUS_STATUS_APPLICABLE = "applicable"
DAUS_STATUS_NOT_APPLICABLE = "not_applicable"
DAUS_MODE_SHAPLEY = "data_asset_utility_shapley"


def to_decimal(value: Decimal | int | float | str, field_name: str) -> Decimal:
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    try:
        converted = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid Decimal value") from exc
    if converted.is_nan() or converted.is_infinite():
        raise ValueError(f"{field_name} must be finite")
    return converted


def require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def require_non_negative_decimal(value: Decimal | int | float | str, field_name: str) -> Decimal:
    converted = to_decimal(value, field_name)
    if converted < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return converted


def require_score(value: Decimal | int | float | str, field_name: str) -> Decimal:
    converted = require_non_negative_decimal(value, field_name)
    if converted > 100:
        raise ValueError(f"{field_name} must be <= 100")
    return converted


def require_confidence(value: Decimal | int | float | str, field_name: str) -> Decimal:
    converted = require_non_negative_decimal(value, field_name)
    if converted > 1:
        raise ValueError(f"{field_name} must be <= 1")
    return converted


def normalize_assumptions(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(require_non_empty(value, "assumption") for value in values)


@dataclass(frozen=True)
class DataAssetUtilityInput:
    """Evidence for one subject in a DAUS attribution run."""

    participant_id: str
    role: str
    measured_contribution_units: Decimal
    quality_score: Decimal
    coverage_score: Decimal
    scarcity_score: Decimal
    sample_score: Decimal
    contribution_source_type: str
    confidence_level: Decimal
    evidence: str
    scenario_fit_score: Decimal = Decimal("100")
    compliance_usability_score: Decimal = Decimal("100")
    model_contribution_score: Decimal | None = None
    expert_score: Decimal | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "participant_id", require_non_empty(self.participant_id, "participant_id"))
        object.__setattr__(self, "role", require_non_empty(self.role, "role"))
        object.__setattr__(
            self,
            "measured_contribution_units",
            require_non_negative_decimal(self.measured_contribution_units, "measured_contribution_units"),
        )
        for field_name in (
            "quality_score",
            "coverage_score",
            "scarcity_score",
            "sample_score",
            "scenario_fit_score",
            "compliance_usability_score",
        ):
            object.__setattr__(self, field_name, require_score(getattr(self, field_name), field_name))
        if self.model_contribution_score is not None:
            object.__setattr__(
                self,
                "model_contribution_score",
                require_score(self.model_contribution_score, "model_contribution_score"),
            )
        if self.expert_score is not None:
            object.__setattr__(self, "expert_score", require_score(self.expert_score, "expert_score"))
        if self.contribution_source_type not in DAUS_SOURCE_TYPES:
            raise ValueError(
                "contribution_source_type must be one of "
                + ", ".join(sorted(DAUS_SOURCE_TYPES))
            )
        object.__setattr__(
            self,
            "confidence_level",
            require_confidence(self.confidence_level, "confidence_level"),
        )
        object.__setattr__(self, "evidence", require_non_empty(self.evidence, "evidence"))
        object.__setattr__(self, "assumptions", normalize_assumptions(self.assumptions))


@dataclass(frozen=True)
class DataAssetCoalition:
    """A coalition S and its evaluated utility score v(S)."""

    participant_ids: frozenset[str]
    utility_score: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        ids = frozenset(require_non_empty(participant_id, "participant_id") for participant_id in self.participant_ids)
        object.__setattr__(self, "participant_ids", ids)
        object.__setattr__(self, "utility_score", require_non_negative_decimal(self.utility_score, "utility_score"))


@dataclass(frozen=True)
class DAUSShapleyConfig:
    """Configuration for Data Asset Utility Shapley attribution."""

    config_id: str = "daus_shapley_v1"
    score_factor_scale: Decimal = Decimal("100")
    assumptions: tuple[str, ...] = (
        "DAUS defines v(S) as a data-asset utility score function over coalitions.",
        "The default additive utility function is an MVP special case, not the complete DAUS definition.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "config_id", require_non_empty(self.config_id, "config_id"))
        scale = require_non_negative_decimal(self.score_factor_scale, "score_factor_scale")
        if scale <= 0:
            raise ValueError("score_factor_scale must be > 0")
        object.__setattr__(self, "score_factor_scale", scale)
        object.__setattr__(self, "assumptions", normalize_assumptions(self.assumptions))


@dataclass(frozen=True)
class ParticipantShapleyAttribution:
    """Shapley-style participant attribution under the DAUS utility function."""

    participant_id: str
    role: str
    standalone_utility_score: Decimal
    shapley_value: Decimal
    contribution_share: Decimal
    contribution_source_type: str
    confidence_level: Decimal
    evidence: str
    marginal_contributions: tuple[Decimal, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "participant_id", require_non_empty(self.participant_id, "participant_id"))
        object.__setattr__(self, "role", require_non_empty(self.role, "role"))
        object.__setattr__(
            self,
            "standalone_utility_score",
            to_decimal(self.standalone_utility_score, "standalone_utility_score"),
        )
        object.__setattr__(self, "shapley_value", to_decimal(self.shapley_value, "shapley_value"))
        object.__setattr__(self, "contribution_share", to_decimal(self.contribution_share, "contribution_share"))
        if self.contribution_source_type not in DAUS_SOURCE_TYPES:
            raise ValueError("invalid contribution_source_type")
        object.__setattr__(self, "confidence_level", require_confidence(self.confidence_level, "confidence_level"))
        object.__setattr__(self, "evidence", require_non_empty(self.evidence, "evidence"))
        object.__setattr__(
            self,
            "marginal_contributions",
            tuple(to_decimal(value, "marginal_contribution") for value in self.marginal_contributions),
        )
        object.__setattr__(self, "assumptions", normalize_assumptions(self.assumptions))

    @property
    def daus_score(self) -> Decimal:
        """Deprecated compatibility alias for shapley_value."""
        return self.shapley_value


@dataclass(frozen=True)
class DAUSAuditRecord:
    event_type: str
    participant_id: str | None
    description: str
    source_type: str | None
    config_id: str
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", require_non_empty(self.event_type, "event_type"))
        if self.participant_id is not None:
            object.__setattr__(self, "participant_id", require_non_empty(self.participant_id, "participant_id"))
        object.__setattr__(self, "description", require_non_empty(self.description, "description"))
        if self.source_type is not None and self.source_type not in DAUS_SOURCE_TYPES:
            raise ValueError("invalid source_type")
        object.__setattr__(self, "config_id", require_non_empty(self.config_id, "config_id"))
        object.__setattr__(self, "assumptions", normalize_assumptions(self.assumptions))


@dataclass(frozen=True)
class DAUSShapleyResult:
    status: str
    participant_attributions: tuple[ParticipantShapleyAttribution, ...]
    coalitions: tuple[DataAssetCoalition, ...]
    total_utility_score: Decimal
    contribution_shares: Mapping[str, Decimal]
    calculation_mode: str
    utility_score_function: str
    source_types: tuple[str, ...]
    assumptions: tuple[str, ...]
    audit_records: tuple[DAUSAuditRecord, ...]
    not_applicable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {DAUS_STATUS_APPLICABLE, DAUS_STATUS_NOT_APPLICABLE}:
            raise ValueError("invalid DAUS result status")
        object.__setattr__(self, "participant_attributions", tuple(self.participant_attributions))
        object.__setattr__(self, "coalitions", tuple(self.coalitions))
        object.__setattr__(self, "total_utility_score", require_non_negative_decimal(self.total_utility_score, "total_utility_score"))
        object.__setattr__(
            self,
            "contribution_shares",
            {require_non_empty(key, "participant_id"): to_decimal(value, "contribution_share") for key, value in self.contribution_shares.items()},
        )
        object.__setattr__(self, "calculation_mode", require_non_empty(self.calculation_mode, "calculation_mode"))
        object.__setattr__(
            self,
            "utility_score_function",
            require_non_empty(self.utility_score_function, "utility_score_function"),
        )
        object.__setattr__(self, "source_types", tuple(sorted(set(self.source_types))))
        object.__setattr__(self, "assumptions", normalize_assumptions(self.assumptions))
        object.__setattr__(self, "audit_records", tuple(self.audit_records))
        if self.not_applicable_reason is not None:
            object.__setattr__(
                self,
                "not_applicable_reason",
                require_non_empty(self.not_applicable_reason, "not_applicable_reason"),
            )

    @property
    def used_shapley(self) -> bool:
        return self.status == DAUS_STATUS_APPLICABLE and self.calculation_mode == DAUS_MODE_SHAPLEY

    @property
    def participant_vectors(self) -> tuple[ParticipantShapleyAttribution, ...]:
        """Deprecated compatibility alias for participant_attributions."""
        return self.participant_attributions

    @property
    def total_daus_score(self) -> Decimal:
        """Deprecated compatibility alias for total_utility_score."""
        return self.total_utility_score


# Deprecated compatibility aliases. New code should use the DataAsset*/Shapley names.
DAUSContributionInput = DataAssetUtilityInput
DAUSParticipantVector = ParticipantShapleyAttribution
DAUSResult = DAUSShapleyResult
DAUSUtilityConfig = DAUSShapleyConfig
