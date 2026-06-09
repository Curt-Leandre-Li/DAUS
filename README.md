# DAUS Algorithm

DAUS means **Data Asset Utility Scoring** (`数据资产效用评分`). It is an explainable and auditable contribution-utility scoring layer for multi-party data asset collaboration.

DAUS converts standardized participant contribution evidence into participant utility scores, contribution shares, and audit records. The result can support revenue allocation simulation and negotiation, but it is **not** a final pricing decision, legal certification, or signed contract split.

## Problem Definition

Data collaborations often involve multiple data providers, multiple data fields, and multiple business scenarios. Simple data volume counts are not enough to explain contribution. DAUS answers a narrower question:

> Given explicit contribution evidence for each participant, what is each participant's auditable utility score and normalized contribution share for simulation and negotiation?

DAUS keeps provenance visible. It distinguishes measured contribution from expert estimate, contract agreement, and simulation.

## Inputs

Each `DAUSContributionInput` represents one participant's standardized contribution evidence:

- `participant_id`
- `role`
- `measured_shuyuan`
- `quality_score`
- `scenario_factor`
- `coverage_score`
- `scarcity_score`
- `sample_score`
- `model_contribution_score` (optional)
- `expert_score` (optional)
- `contribution_source_type`
- `confidence_level`
- `evidence`
- `assumptions`

Allowed source types:

- `measured_data`
- `expert_estimate`
- `contract_agreement`
- `simulation`

Source type is provenance only. It must not be used as a hidden scoring multiplier.

## Outputs

`DAUSResult` contains:

- status: `applicable` or `not_applicable`
- participant vectors
- adjusted Shuyuan per participant
- DAUS score per participant
- normalized contribution share
- whether Shapley marginal contribution was used
- calculation mode
- source types
- assumptions
- audit records
- not-applicable reason, when relevant

## Mathematical Definition

MVP adjusted Shuyuan:

```text
adjusted_shuyuan_i =
  measured_shuyuan_i
  * quality_factor_i
  * scenario_factor_i
  * coverage_factor_i
  * scarcity_factor_i
  * sample_factor_i
```

Score-to-factor policy:

```text
factor = score / 100
```

Coalition utility:

```text
utility(S) =
  sum(adjusted_shuyuan_i for i in S)
  * (1 + optional_interaction_bonus(S))
  - optional_risk_penalty(S)
```

In the MVP, interaction bonus and risk penalty are explicit hooks and default to `0`.

## Relationship With Shapley

Shapley is located inside the DAUS contribution-utility layer. It can convert coalition marginal contribution into contribution weights when model or field contribution evidence exists.

If complete `model_contribution_score` evidence is supplied and Shapley mode is enabled, DAUS uses Shapley marginal contribution over the DAUS utility function. If model contribution evidence is missing, DAUS falls back to deterministic adjusted-Shuyuan mode unless Shapley is explicitly required. Required Shapley without evidence returns `not_applicable`.

Shapley output is not a final contract split. It is a negotiation and simulation support signal.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 -m pytest -q
```

## Example

```python
from decimal import Decimal

from daus import DAUSContributionInput, calculate_daus

inputs = (
    DAUSContributionInput(
        participant_id="hospital-a",
        role="Hospital A",
        measured_shuyuan=Decimal("120"),
        quality_score=Decimal("90"),
        scenario_factor=Decimal("1.2"),
        coverage_score=Decimal("80"),
        scarcity_score=Decimal("70"),
        sample_score=Decimal("95"),
        contribution_source_type="measured_data",
        confidence_level=Decimal("0.9"),
        evidence="validated demo measurement",
        assumptions=("Example only; not a final contract split.",),
    ),
    DAUSContributionInput(
        participant_id="hospital-b",
        role="Hospital B",
        measured_shuyuan=Decimal("80"),
        quality_score=Decimal("85"),
        scenario_factor=Decimal("1.0"),
        coverage_score=Decimal("75"),
        scarcity_score=Decimal("60"),
        sample_score=Decimal("90"),
        contribution_source_type="expert_estimate",
        confidence_level=Decimal("0.7"),
        evidence="expert estimate for simulation",
        assumptions=("Expert estimate pending measured model evidence.",),
    ),
)

result = calculate_daus(inputs)
for vector in result.participant_vectors:
    print(vector.participant_id, vector.daus_score, vector.contribution_share)
```

## Integration Notes

The standalone DAUS core has no runtime dependency on allocation, reporting, Shuyuan metering, databases, APIs, or UI frameworks. The copied `daus_result_to_contribution_input_batch()` function is an optional host-integration adapter retained for source compatibility with systems that provide allocation contracts. It is not required for DAUS scoring.

## Roadmap

- Add documented non-additive interaction functions when product evidence exists.
- Add optional risk penalty plugins with explicit audit semantics.
- Add richer serialization helpers for reporting systems.
- Add benchmark examples for healthcare, finance, and public-data collaboration.
- Keep source-type provenance auditable and avoid hidden metadata scoring.

## Non-Goals

DAUS is not a pricing engine, MAR/compliance-cap module, database, authentication system, production API, legal certification system, or final contract allocation engine.
