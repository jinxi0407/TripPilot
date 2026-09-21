## Purpose
Evaluate travel planning and agent controls reproducibly using a small frozen case set and report actual measurements with transparent baselines and limitations.

## ADDED Requirements

### Requirement: Small reproducible case set
Evaluation SHALL define 24 cases spanning mainland travel, deterministic routing, weather, transport, cost, route constraints, missing data, and loop/failure controls. Each case SHALL identify inputs, fixed clock, fixture version, expected routing/tool permissions, and outcome assertions.

#### Scenario: Repeatable fixture run
- **WHEN** a case runs twice against identical fixtures and a deterministic test model
- **THEN** constraint and routing assertions have identical outcomes without external API calls.

### Requirement: Independent correctness tests
Backend tests SHALL use pytest with mocked APIs and SHALL test tools independently, routing, permission enforcement, itinerary constraints, budget arithmetic, max steps, retries, duplicate detection, fallback, and re-plan limits.

#### Scenario: Provider failure isolation
- **WHEN** a unit suite runs without network access and without API keys
- **THEN** independent tool and failure-control tests complete using mocks and fixtures.

### Requirement: Defined measured metrics
Evaluation SHALL record task completion, routing correctness, tool selection correctness, constraint satisfaction, budget compliance, route feasibility, hallucinated transport information, average agent steps, latency, and token usage. Missing/inapplicable values MUST be marked explicitly and excluded only with disclosed denominators.

#### Scenario: Missing token usage
- **WHEN** a provider does not return usage metadata
- **THEN** token usage is null/unknown rather than a fabricated estimate or zero.

### Requirement: Fair baseline comparison
The report SHALL compare a simple single-call LLM planner and TripPilot under recorded model, parameters, input fixtures, date, and repetition count. It SHALL separate deterministic fixture tests from measured live-model experiments and MUST NOT invent improvement percentages.

#### Scenario: Baseline has no tool loop
- **WHEN** both systems are evaluated with the same frozen evidence packet and user query
- **THEN** the baseline makes one planning call, TripPilot can select from that same fixture evidence universe, both use the same external validator, and unavailable baseline routing metrics are marked not applicable.

#### Scenario: Evaluation not run
- **WHEN** no authorized configured model calls have been made
- **THEN** the report states not run with empty measured results and makes no comparative performance claim.
