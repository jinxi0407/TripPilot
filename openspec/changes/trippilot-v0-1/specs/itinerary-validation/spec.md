## Purpose
Detect itinerary constraint conflicts, reconcile estimated costs, and repair plans within bounded attempts without disguising uncertain data as verified facts.

## ADDED Requirements

### Requirement: Structured feasibility validation
The Critic SHALL return valid, structured issues with type/severity/message/evidence, checked constraints, and unverified checks. It SHALL check chronological conflicts, opening times when known, train departure, transfers, daily travel/density, destination coverage, and route inefficiency.

#### Scenario: Insufficient train connection
- **WHEN** a prior activity ends only 15 minutes before train departure and station access plus the configured 45-minute station buffer is required
- **THEN** validation marks the itinerary invalid with high-severity TRAIN_DEPARTURE_RISK or TRANSFER_RISK including affected leg references.

#### Scenario: Cross-station transfer
- **WHEN** a connection leaves less time than station-to-station route duration plus the 30-minute interchange buffer
- **THEN** Critic reports a blocking transfer issue even if the train arrival precedes the next departure.

#### Scenario: Closed attraction and missing destination
- **WHEN** an activity falls outside supplied opening intervals and one required city is absent
- **THEN** separate OPENING_TIME_CONFLICT and MISSING_DESTINATION issues are returned.

#### Scenario: Relaxed pace exceeded
- **WHEN** a relaxed day contains more than 3 attractions or more than 120 minutes of local travel under the default policy
- **THEN** Critic reports EXCESSIVE_DENSITY or EXCESSIVE_TRAVEL with observed and allowed values.

#### Scenario: Unknown data
- **WHEN** a required local duration or opening schedule is unavailable
- **THEN** the check is recorded as unverified, the final outcome is partial, and the system does not assert full feasibility.

### Requirement: Six-category budget accounting
Costs SHALL include inter-city transport, local transport, accommodation placeholder, attraction tickets, food estimate, and miscellaneous reserve. Computation SHALL use integer CNY minor units, reconcile daily/category/trip totals, and count each expense once.

#### Scenario: Budget overflow
- **WHEN** the known estimated total is 410000 fen against a 400000-fen budget
- **THEN** validation emits BUDGET_EXCEEDED with a 10000-fen excess and initiates repair if attempts remain.

#### Scenario: Unknown fare
- **WHEN** known costs are below budget but a train fare is unknown
- **THEN** budget compliance is unverified and the unknown cost is not silently treated as zero.

#### Scenario: Overnight rail expense
- **WHEN** a paid train leg spans midnight
- **THEN** its fare is counted once on departure day and all daily costs sum to the trip total.

### Requirement: Bounded feedback-driven re-planning
Validation feedback SHALL trigger at most 2 automatic re-plans after the initial draft, for at most 3 validation passes. Repeated identical issues after an unsuccessful repair SHALL stop early. Hard constraints MUST NOT be relaxed without user input.

#### Scenario: Persistent impossible budget
- **WHEN** the required plan remains over budget after allowed repairs
- **THEN** the run ends as conflict with remaining issues and suggested user changes rather than looping or declaring success.

### Requirement: Weather transport budget and route revisions
The system SHALL support explicit revisions driven by changed weather, transport conflict, budget violation, or route inefficiency. Changed activities SHALL receive updated route/timing evidence and whole-plan validation before a revised result is presented as complete.

#### Scenario: Severe rain
- **WHEN** new weather evidence shows severe rain during an outdoor visit and a feasible indoor candidate exists
- **THEN** WEATHER_RISK triggers revision to an indoor activity, route recalculation, and a fresh Critic pass within the attempt limit.

#### Scenario: Train conflict
- **WHEN** an evidenced chosen train becomes unavailable
- **THEN** revision selects another evidenced feasible option or returns a transport conflict without inventing availability.

#### Scenario: Inefficient route
- **WHEN** supported comparison shows the current local order exceeds a feasible same-POI alternative by more than 30 percent travel time
- **THEN** ROUTE_INEFFICIENCY is reported and a bounded repair can reorder visits while preserving opening-time and other hard constraints.
