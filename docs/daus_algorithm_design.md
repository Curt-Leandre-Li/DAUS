# DAUS Algorithm Design

DAUS means Data Asset Utility. It is the
contribution-utility layer between Shuyuan metering and revenue allocation
simulation.

DAUS is not a pricing module, not a simple weighted table, and not a direct
final-contract allocation algorithm. Its job is to transform multi-party,
multi-field, multi-scenario contribution evidence into explainable and
auditable participant utility scores that can be consumed by allocation
simulation.

## Position In The MVP Chain

The intended dependency direction is:

```text
quality_assessment
-> shuyuan_metering
-> daus
-> allocation
-> reporting
-> demo_ui
```

Module relationship:

- `quality_assessment` produces explicit quality scores, quality factors, and
  assumptions. DAUS may consume the public quality-related factor or score
  supplied to it, but it must not read quality internals.
- `shuyuan_metering` produces measured Shuyuan values using the canonical
  formula `base_shuyuan * scenario_coefficient * quality_adjustment_factor`.
  DAUS consumes those public Shuyuan values as contribution evidence.
- `daus` turns participant contribution evidence into adjusted Shuyuan, DAUS
  score, contribution share, and audit records.
- `allocation` consumes prepared public contribution scores and applies
  simulation schemes, contract constraints, role-pool ratios, and manual
  confirmation rules. Allocation must not recompute DAUS.
- `reporting` renders supplied public result objects. It may explain DAUS
  results but must not recalculate DAUS, allocation, quality scoring, or
  Shuyuan metering.
- `demo_ui` presents the chain to stakeholders and must clearly distinguish
  simulated contribution from measured contribution.

## Inputs

Each DAUS contribution input represents one participant's standardized
contribution evidence for a scenario.

Required MVP fields:

- `participant_id`
- `role`
- `measured_shuyuan`
- `quality_score`
- `scenario_factor`
- `coverage_score`
- `scarcity_score`
- `sample_score`
- `model_contribution_score`
- `expert_score`
- `contribution_source_type`
- `confidence_level`
- `evidence`

Allowed `contribution_source_type` values:

- `measured_data`
- `expert_estimate`
- `contract_agreement`
- `simulation`

Source type is provenance. It must not be used as a hidden multiplier or score
boost.

## Outputs

DAUS outputs:

- participant vectors with adjusted Shuyuan and factor details;
- `daus_score` for each participant;
- normalized contribution share for each participant;
- whether Shapley/marginal contribution calculation was used;
- whether the basis is measured, expert-estimated, contract-agreed, or
  simulated;
- assumptions;
- audit records with source type, confidence, config, and evidence.

The output is negotiation and simulation support. It is not a final price
decision and not a signed revenue contract.

## Core Flow

1. Validate participant inputs and reject duplicates.
2. Validate non-negative Shuyuan values and positive factors.
3. Convert public score fields into deterministic factors.
4. Calculate each participant's adjusted Shuyuan.
5. Build the data-asset coalition `S`.
6. Calculate coalition utility using the DAUS utility function.
7. If model/field contribution data is available and Shapley is enabled, compute
   marginal contribution over the DAUS utility function.
8. Otherwise use deterministic adjusted-Shuyuan contribution mode and mark the
   result as simulation/expert-supported where appropriate.
9. Normalize DAUS scores into contribution shares.
10. Emit audit records and assumptions.

## MVP Formula

Participant adjusted Shuyuan:

```text
adjusted_shuyuan_i =
  measured_shuyuan_i
  * quality_factor_i
  * scenario_factor_i
  * coverage_factor_i
  * scarcity_factor_i
  * sample_factor_i
```

MVP score-to-factor policy:

```text
factor = score / 100
```

Scores must be in `[0, 100]`. `scenario_factor` must be positive.
`measured_shuyuan` must be non-negative.

Coalition utility:

```text
utility(S) =
  sum(adjusted_shuyuan_i for i in S)
  * (1 + optional_interaction_bonus(S))
  - optional_risk_penalty(S)
```

In the MVP, `optional_interaction_bonus(S)` and
`optional_risk_penalty(S)` are explicit extension hooks and default to `0`.
They must not read metadata as a hidden scoring channel.

## Shapley In DAUS

Shapley is placed in the DAUS contribution-utility layer. It is a way to turn
coalition marginal contribution into contribution weights.

Shapley is not the final revenue allocation layer. Final allocation still needs
contract constraints, role-pool ratios, negotiation, authorization scope,
manual confirmation, and audit records.

DAUS may use Shapley only when field/model contribution evidence is present.
When that evidence is absent, DAUS must not fabricate a Shapley result. It may
produce a deterministic adjusted-Shuyuan contribution result and mark the basis
as expert estimate, contract agreement, or simulation.

## With Model Contribution Data

When model or field contribution data is supplied:

- the input must expose `model_contribution_score` or equivalent prepared
  contribution evidence;
- DAUS may compute marginal contribution against the DAUS utility function;
- the result must set `used_shapley = true`;
- the result must preserve source type, confidence level, evidence, and
  assumptions.

The MVP utility function is additive unless a future approved phase supplies
documented interaction or risk functions. Therefore, Shapley values over the
default utility function are explainable and deterministic.

## Without Real Model Contribution Data

When real model contribution evidence is not available:

- DAUS may use `expert_estimate`, `contract_agreement`, or `simulation` inputs;
- the result must set `used_shapley = false`;
- the result must explicitly say it is not measured model contribution;
- reports and UI must not present the result as measured Shapley output.

This is not deceptive because the result carries its evidence basis, source
type, confidence, and assumptions. Simulated contribution is acceptable for
business explanation only when it is labelled as simulated.

## Audit Fields

Each DAUS audit record should include:

- `event_type`
- `participant_id`, when applicable;
- `source_type`;
- `confidence_level`;
- `config`;
- `assumptions`;
- `evidence`;
- `message`.

Audit records support review and negotiation. They are not legal
certification.

## MVP Non-Goals

DAUS MVP does not implement:

- pricing;
- MAR or compliance-cap logic;
- database persistence;
- authentication;
- production API integration;
- real hospital integration;
- real patient data processing;
- legal certification;
- complex interaction models;
- hidden metadata scoring;
- final signed contract allocation.

## Legacy Compatibility

The canonical implementation is `src/daus/`.

`src/shuyuan_metering/daus.py` is legacy compatibility only. It exists so older
imports can continue to resolve while callers migrate to `src.daus` or `daus`.
The legacy surface must not contain independent DAUS calculation logic. Any
supported compatibility function must convert old input objects into canonical
DAUS inputs and delegate to `calculate_daus()` or
`daus_result_to_contribution_input_batch()`.

No new DAUS feature, scoring formula, Shapley behavior, or allocation adapter
logic should be added to `src/shuyuan_metering/daus.py`.
