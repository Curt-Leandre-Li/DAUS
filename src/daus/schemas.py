from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


DAUS_SOURCE_TYPES = frozenset(
    {"measured_data", "expert_estimate", "contract_agreement", "simulation"}
)

DAUS_STATUS_APPLICABLE = "applicable"
DAUS_STATUS_NOT_APPLICABLE = "not_applicable"

DAUS_MODE_ADJUSTED_SHUYUAN = "adjusted_shuyuan"
DAUS_MODE_SHAPLEY = "shapley_marginal_contribution"

DAUS_SHAPLEY_AUTO = "auto"
DAUS_SHAPLEY_DISABLED = "disabled"
DAUS_SHAPLEY_REQUIRED = "required"


def require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required.")
    return cleaned


def optional_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text.")
    return value.strip()


def to_decimal(value: Any, field_name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a valid Decimal.")
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid Decimal.") from exc
    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be a finite Decimal.")
    return decimal_value


def require_non_negative_decimal(value: Any, field_name: str) -> Decimal:
    decimal_value = to_decimal(value, field_name)
    if decimal_value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return decimal_value


def require_positive_decimal(value: Any, field_name: str) -> Decimal:
    decimal_value = to_decimal(value, field_name)
    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return decimal_value


def require_score(value: Any, field_name: str) -> Decimal:
    decimal_value = to_decimal(value, field_name)
    if decimal_value < 0 or decimal_value > 100:
        raise ValueError(f"{field_name} must be within [0, 100].")
    return decimal_value


def optional_score(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return require_score(value, field_name)


def normalize_source_type(source_type: str) -> str:
    cleaned = require_text(source_type, "contribution_source_type")
    if cleaned not in DAUS_SOURCE_TYPES:
        allowed = ", ".join(sorted(DAUS_SOURCE_TYPES))
        raise ValueError(f"contribution_source_type must be one of: {allowed}.")
    return cleaned


def normalize_assumptions(assumptions: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    if isinstance(assumptions, str) or not isinstance(assumptions, (tuple, list)):
        raise ValueError("assumptions must be a tuple or list of text items.")
    return tuple(require_text(assumption, "assumption") for assumption in assumptions)


@dataclass(frozen=True, slots=True)
class DAUSContributionInput:
    participant_id: str
    role: str
    measured_shuyuan: Decimal
    quality_score: Decimal
    coverage_score: Decimal
    scarcity_score: Decimal
    sample_score: Decimal
    contribution_source_type: str
    confidence_level: Decimal
    evidence: str
    scenario_factor: Decimal = Decimal("1")
    model_contribution_score: Decimal | None = None
    expert_score: Decimal | None = None
    assumptions: tuple[str, ...] | list[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "participant_id",
            require_text(self.participant_id, "participant_id"),
        )
        object.__setattr__(self, "role", require_text(self.role, "role"))
        object.__setattr__(
            self,
            "measured_shuyuan",
            require_non_negative_decimal(self.measured_shuyuan, "measured_shuyuan"),
        )
        for field_name in (
            "quality_score",
            "coverage_score",
            "scarcity_score",
            "sample_score",
        ):
            object.__setattr__(
                self,
                field_name,
                require_score(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "scenario_factor",
            require_positive_decimal(self.scenario_factor, "scenario_factor"),
        )
        object.__setattr__(
            self,
            "model_contribution_score",
            optional_score(self.model_contribution_score, "model_contribution_score"),
        )
        object.__setattr__(
            self,
            "expert_score",
            optional_score(self.expert_score, "expert_score"),
        )
        object.__setattr__(
            self,
            "contribution_source_type",
            normalize_source_type(self.contribution_source_type),
        )
        confidence_level = to_decimal(self.confidence_level, "confidence_level")
        if confidence_level < 0 or confidence_level > 1:
            raise ValueError("confidence_level must be within [0, 1].")
        object.__setattr__(self, "confidence_level", confidence_level)
        object.__setattr__(self, "evidence", require_text(self.evidence, "evidence"))
        object.__setattr__(
            self,
            "assumptions",
            normalize_assumptions(self.assumptions),
        )


@dataclass(frozen=True, slots=True)
class DAUSUtilityConfig:
    config_id: str = "daus_mvp_v1"
    shapley_mode: str = DAUS_SHAPLEY_AUTO
    score_factor_scale: Decimal = Decimal("100")
    interaction_bonus: Decimal = Decimal("0")
    risk_penalty: Decimal = Decimal("0")
    assumptions: tuple[str, ...] | list[str] = (
        "DAUS MVP uses deterministic score-to-factor mapping.",
        "DAUS outputs support negotiation and simulation, not final contract split.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "config_id", require_text(self.config_id, "config_id"))
        if self.shapley_mode not in {
            DAUS_SHAPLEY_AUTO,
            DAUS_SHAPLEY_DISABLED,
            DAUS_SHAPLEY_REQUIRED,
        }:
            raise ValueError("shapley_mode must be auto, disabled, or required.")
        scale = require_positive_decimal(self.score_factor_scale, "score_factor_scale")
        object.__setattr__(self, "score_factor_scale", scale)
        object.__setattr__(
            self,
            "interaction_bonus",
            require_non_negative_decimal(self.interaction_bonus, "interaction_bonus"),
        )
        object.__setattr__(
            self,
            "risk_penalty",
            require_non_negative_decimal(self.risk_penalty, "risk_penalty"),
        )
        object.__setattr__(
            self,
            "assumptions",
            normalize_assumptions(self.assumptions),
        )

    def public_dict(self) -> dict[str, str]:
        return {
            "config_id": self.config_id,
            "shapley_mode": self.shapley_mode,
            "score_factor_scale": str(self.score_factor_scale),
            "interaction_bonus": str(self.interaction_bonus),
            "risk_penalty": str(self.risk_penalty),
        }


@dataclass(frozen=True, slots=True)
class DAUSParticipantVector:
    participant_id: str
    role: str
    measured_shuyuan: Decimal
    adjusted_shuyuan: Decimal
    daus_score: Decimal
    contribution_share: Decimal
    quality_factor: Decimal
    scenario_factor: Decimal
    coverage_factor: Decimal
    scarcity_factor: Decimal
    sample_factor: Decimal
    contribution_source_type: str
    confidence_level: Decimal
    evidence: str
    model_contribution_score: Decimal | None = None
    expert_score: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "participant_id",
            require_text(self.participant_id, "participant_id"),
        )
        object.__setattr__(self, "role", require_text(self.role, "role"))
        for field_name in (
            "measured_shuyuan",
            "adjusted_shuyuan",
            "daus_score",
            "contribution_share",
            "quality_factor",
            "scenario_factor",
            "coverage_factor",
            "scarcity_factor",
            "sample_factor",
            "confidence_level",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_negative_decimal(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "contribution_source_type",
            normalize_source_type(self.contribution_source_type),
        )
        object.__setattr__(self, "evidence", require_text(self.evidence, "evidence"))


@dataclass(frozen=True, slots=True)
class DAUSAuditRecord:
    event_type: str
    source_type: str
    config: Mapping[str, str]
    assumptions: tuple[str, ...] | list[str]
    message: str
    participant_id: str = ""
    confidence_level: Decimal = Decimal("0")
    evidence: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", require_text(self.event_type, "event_type"))
        object.__setattr__(self, "source_type", normalize_source_type(self.source_type))
        object.__setattr__(self, "config", dict(self.config))
        object.__setattr__(self, "assumptions", normalize_assumptions(self.assumptions))
        object.__setattr__(self, "message", require_text(self.message, "message"))
        if self.participant_id:
            object.__setattr__(self, "participant_id", self.participant_id.strip())
        object.__setattr__(
            self,
            "confidence_level",
            require_non_negative_decimal(self.confidence_level, "confidence_level"),
        )
        if self.evidence:
            object.__setattr__(self, "evidence", self.evidence.strip())


@dataclass(frozen=True, slots=True)
class DAUSResult:
    status: str
    participant_vectors: tuple[DAUSParticipantVector, ...]
    total_daus_score: Decimal
    contribution_shares: Mapping[str, Decimal]
    used_shapley: bool
    calculation_mode: str
    source_types: tuple[str, ...]
    assumptions: tuple[str, ...]
    audit_records: tuple[DAUSAuditRecord, ...]
    not_applicable_reason: str = ""

    def __post_init__(self) -> None:
        if self.status not in {DAUS_STATUS_APPLICABLE, DAUS_STATUS_NOT_APPLICABLE}:
            raise ValueError("status must be applicable or not_applicable.")
        object.__setattr__(self, "participant_vectors", tuple(self.participant_vectors))
        object.__setattr__(
            self,
            "total_daus_score",
            require_non_negative_decimal(self.total_daus_score, "total_daus_score"),
        )
        object.__setattr__(
            self,
            "contribution_shares",
            {
                require_text(participant_id, "participant_id"): require_non_negative_decimal(
                    share,
                    "contribution_share",
                )
                for participant_id, share in dict(self.contribution_shares).items()
            },
        )
        object.__setattr__(
            self,
            "calculation_mode",
            require_text(self.calculation_mode, "calculation_mode"),
        )
        object.__setattr__(
            self,
            "source_types",
            tuple(normalize_source_type(source_type) for source_type in self.source_types),
        )
        object.__setattr__(self, "assumptions", normalize_assumptions(self.assumptions))
        object.__setattr__(self, "audit_records", tuple(self.audit_records))
        if self.not_applicable_reason:
            object.__setattr__(
                self,
                "not_applicable_reason",
                self.not_applicable_reason.strip(),
            )
