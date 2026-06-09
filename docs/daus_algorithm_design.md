# DAUS Algorithm Design

## Definition

DAUS means **Data Asset Utility Shapley**.

DAUS is a Shapley-value variant for data asset contribution attribution. Its core idea is to replace the model-performance utility used by traditional Data Shapley with an auditable data-asset utility score.

```text
Traditional Data Shapley:
v(S) = model performance trained or evaluated on data coalition S

DAUS:
v_DAUS(S) = Data Asset Utility Score of coalition S
```

DAUS still computes marginal contribution over coalitions. It is not merely a weighted score table, and it is not a final revenue split.

## What DAUS Is

DAUS provides an attribution layer:

```text
Contribution evidence
  -> Data-asset utility function v_DAUS(S)
  -> Coalition marginal contribution
  -> Shapley-style participant attribution
  -> Audit record
```

The output can support negotiation, simulation, or downstream allocation, but DAUS itself does not decide final price, contract terms, or payment.

## Relationship With Data Shapley

Traditional Data Shapley uses model performance metrics such as accuracy, loss, AUC, F1, or task reward as `v(S)`. DAUS changes the definition of `v(S)`:

```text
v_DAUS(S) = UtilityScoreFunction(S)
```

The utility score can be built from auditable data-asset signals:

- measured contribution units
- data quality
- coverage
- scarcity
- sample scale
- scenario fit
- compliance usability
- measured evidence
- expert estimate
- contract-agreed evidence
- simulation evidence

Model contribution evidence may be included as one utility signal when available. It is not required for DAUS to run.

## Inputs

Canonical input object: `DataAssetUtilityInput`.

Required fields:

- `participant_id`
- `role`
- `measured_contribution_units`
- `quality_score`
- `coverage_score`
- `scarcity_score`
- `sample_score`
- `contribution_source_type`
- `confidence_level`
- `evidence`

Optional fields:

- `scenario_fit_score`
- `compliance_usability_score`
- `model_contribution_score`
- `expert_score`
- `assumptions`

Allowed source types:

- `measured_data`
- `expert_estimate`
- `contract_agreement`
- `simulation`

Source type is provenance. It is not a hidden multiplier.

## Outputs

Canonical result object: `DAUSShapleyResult`.

It contains:

- evaluated `DataAssetCoalition` records
- coalition utility scores `v_DAUS(S)`
- `ParticipantShapleyAttribution` records
- Shapley values
- contribution shares
- source types
- confidence levels
- assumptions
- audit records
- not-applicable reason when needed

## Core Flow

1. Validate participant contribution evidence.
2. Build every coalition `S` needed by the Shapley calculation.
3. Evaluate `v_DAUS(S)` with a `UtilityScoreFunction`.
4. For each participant `i`, compute marginal utility:

   ```text
   marginal_i(S) = v_DAUS(S union {i}) - v_DAUS(S)
   ```

5. Compute Shapley attribution:

   ```text
   phi_i = sum over S subset N\{i} of
           |S|! * (|N|-|S|-1)! / |N|!
           * marginal_i(S)
   ```

6. Normalize Shapley values into contribution shares when total contribution is positive.
7. Emit audit records and assumptions.

## MVP Utility Function

The default MVP utility function is additive and explainable:

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

This additive form is a special case. In this case, Shapley attribution equals each participant's standalone additive utility contribution. DAUS is still defined at the coalition level, and callers may provide non-additive `UtilityScoreFunction` implementations.

## Position of Shapley in DAUS

Shapley is not an optional label attached after scoring. It is the attribution method DAUS uses to convert coalition utility into participant contribution.

DAUS differs from traditional Data Shapley only in the coalition utility target:

- traditional Data Shapley uses model performance as `v(S)`;
- DAUS uses auditable data-asset utility as `v(S)`.

## Measured vs Simulated Contribution

DAUS must not disguise simulated evidence as measured evidence.

Every input carries:

- `contribution_source_type`
- `confidence_level`
- `evidence`
- optional assumptions

When real measured contribution evidence exists, use `measured_data`. When evidence is expert-estimated or simulated, use `expert_estimate` or `simulation` and disclose the assumptions.

## Audit Fields

Each DAUS result should expose:

- utility function name
- config id
- participant source type
- participant confidence level
- evidence summary
- evaluated coalition utilities
- assumptions
- not-applicable reason when applicable

## MVP Non-Goals

DAUS Core does not implement:

- final revenue allocation
- pricing
- contract negotiation
- reporting artifact generation
- database persistence
- authentication
- deployment
- domain-specific adapters
- model training
- hidden fallback allocation

Host projects may consume DAUS results in their own allocation or reporting layers.
