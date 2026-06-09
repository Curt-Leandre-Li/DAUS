# DAUS: Data Asset Utility Shapley

DAUS stands for **Data Asset Utility Shapley**. It is a Shapley-value variant for data asset contribution attribution.

Traditional Data Shapley usually defines coalition utility as model performance:

```text
v(S) = model performance trained or evaluated on data coalition S
```

DAUS replaces that model-performance target with an auditable data-asset utility score:

```text
v_DAUS(S) = Data Asset Utility Score of coalition S
```

The result is still Shapley-style marginal contribution attribution over coalitions. DAUS is not a final contract split, a pricing engine, or a simple normalized weighted score.

## Why DAUS?

Data asset collaboration often needs explainable contribution attribution before there is enough evidence to run repeated model-training experiments. DAUS lets teams build `v(S)` from auditable contribution evidence such as quality, coverage, scarcity, sample scale, scenario fit, compliance usability, measured evidence, expert assumptions, or contract-agreed evidence.

Real model contribution evidence can be one input signal, but DAUS does not require model accuracy, loss, AUC, F1, or any other training metric to define coalition utility.

## Input

The canonical input is `DataAssetUtilityInput`:

- `participant_id`
- `role`
- `measured_contribution_units`
- `quality_score`
- `coverage_score`
- `scarcity_score`
- `sample_score`
- `scenario_fit_score`
- `compliance_usability_score`
- `model_contribution_score` optional
- `expert_score` optional
- `contribution_source_type`: `measured_data`, `expert_estimate`, `contract_agreement`, or `simulation`
- `confidence_level`
- `evidence`
- `assumptions`

## Output

`calculate_daus(...)` returns `DAUSShapleyResult`, including:

- evaluated coalitions `S`
- coalition utility scores `v(S)`
- participant Shapley values
- contribution shares
- source types and confidence levels
- audit records
- assumptions

## Mathematical Definition

For participants `N`, DAUS defines a coalition utility function:

```text
v_DAUS(S) = UtilityScoreFunction(S)
```

The default MVP utility function is additive:

```text
u_i = measured_contribution_units_i
    * quality_factor_i
    * coverage_factor_i
    * scarcity_factor_i
    * sample_factor_i
    * scenario_fit_factor_i
    * compliance_usability_factor_i

v_DAUS(S) = sum(u_i for i in S)
```

This additive form is a special case. Under additive utility, each participant's DAUS Shapley value equals its standalone utility contribution. The API still evaluates coalitions so that non-additive utility functions can be supplied later.

DAUS attribution uses the Shapley formula:

```text
phi_i = sum over S subset N\{i} of
        |S|! * (|N|-|S|-1)! / |N|!
        * (v_DAUS(S union {i}) - v_DAUS(S))
```

## Relationship With Shapley

DAUS is not a replacement for Shapley. It is a data-asset version of Shapley.

- Traditional Data Shapley: `v(S)` is model performance.
- DAUS: `v(S)` is auditable data-asset utility.

This distinction is important when model-performance experiments are unavailable, incomplete, expensive, or not the right governance basis.

## Quick Start

```bash
python3 -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q
```

## Example

```python
from decimal import Decimal
from daus import DataAssetUtilityInput, calculate_daus

inputs = [
    DataAssetUtilityInput(
        participant_id="source-a",
        role="data_provider",
        measured_contribution_units=Decimal("100"),
        quality_score=Decimal("95"),
        coverage_score=Decimal("90"),
        scarcity_score=Decimal("80"),
        sample_score=Decimal("100"),
        contribution_source_type="measured_data",
        confidence_level=Decimal("0.9"),
        evidence="validated contribution evidence batch",
    ),
    DataAssetUtilityInput(
        participant_id="source-b",
        role="data_provider",
        measured_contribution_units=Decimal("80"),
        quality_score=Decimal("85"),
        coverage_score=Decimal("75"),
        scarcity_score=Decimal("90"),
        sample_score=Decimal("95"),
        contribution_source_type="expert_estimate",
        confidence_level=Decimal("0.7"),
        evidence="expert-reviewed simulation evidence",
    ),
]

result = calculate_daus(inputs)
for attribution in result.participant_attributions:
    print(attribution.participant_id, attribution.shapley_value, attribution.contribution_share)
```

## Roadmap

- Additional coalition-level utility functions with interaction terms.
- Stronger audit serialization helpers.
- Reference examples for measured, expert-estimated, and simulation-based evidence.
- Optional adapters in host projects, kept outside DAUS Core.
