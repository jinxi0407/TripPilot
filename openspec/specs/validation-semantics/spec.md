# validation-semantics Specification

## Purpose
TripPilot SHALL distinguish confirmed blocking violations from missing external evidence and informational notices across Critic, API, traveler UI and measured evaluation, without hiding remaining travel uncertainty.

## Requirements
### Requirement: Typed evidence semantics
Every issue MUST expose severity, status, blocking, target, source and evidence. Blocking MUST imply confirmed and error.
#### Scenario: Missing facts
- **WHEN** opening hours, weather, transport coverage, hotel route or price is unknown
- **THEN** it is unverified and non-blocking with a specific uncertainty message
#### Scenario: Proven contradiction
- **WHEN** known timing, required destination, route, weather or known costs contradict a hard constraint
- **THEN** it is confirmed, blocking and eligible for bounded replanning

### Requirement: Budget facts and estimates
The system SHALL separate known_cost, unknown_cost_items, estimated_cost and budget_limit.
#### Scenario: Estimated expense exceeds limit
- **WHEN** estimates exceed the budget but known costs do not
- **THEN** BUDGET_RISK is non-blocking, while unknown prices remain BUDGET_PARTIAL
#### Scenario: Known lower bound exceeds limit
- **WHEN** known_cost exceeds budget_limit
- **THEN** BUDGET_EXCEEDED is a blocking confirmed violation

### Requirement: Bounded replanning and status
Only blocking issues SHALL trigger automatic replanning. Existing attempt limits MUST remain unchanged.
#### Scenario: Uncertainty only
- **WHEN** issues exist but none are blocking
- **THEN** no replanning occurs and unverified information produces partial rather than conflict
#### Scenario: Hard conflict
- **WHEN** a blocking issue remains
- **THEN** conflict is returned after bounded attempts and the problem stays visible

### Requirement: Deduplicated traveler presentation
Exact duplicate issues SHALL be removed while distinct activity targets remain inspectable. Traveler mode SHALL aggregate uncertainty and highlight only blocking issues; demo mode SHALL show classified counts and expandable targets.
#### Scenario: Multiple missing opening hours
- **WHEN** two activities on a day lack opening hours
- **THEN** traveler mode shows one grouped item with two activities and demo details retain both targets
#### Scenario: No confirmed violation
- **WHEN** blocking confirmed count is zero
- **THEN** the banner is neutral/green, no conflict text or literal svg appears, and budget/replanning controls are not shown for uncertainty alone

### Requirement: Truthful regression evidence
The implementation MUST save raw before/after LIVE validation, verify day density, and rerun the original fifty cases for both TripPilot and Single-Agent Baseline without editing cases or labels.
#### Scenario: Strict replanning metric
- **WHEN** there is an observed confirmed blocking conflict followed by Critic, replan and removal
- **THEN** it counts as a successful recovery; unknown-with-no-replan is excluded from the denominator and absent opportunities are N/A
