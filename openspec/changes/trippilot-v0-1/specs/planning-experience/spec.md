## Purpose
Offer a responsive local planning interface with clear run lifecycle, itinerary evidence, agent progress, and usable fallbacks when data or maps are unavailable.

## ADDED Requirements

### Requirement: Asynchronous local planning lifecycle
The API SHALL support plan creation, status/result polling, clarification, revisions, and cancellation using typed requests/responses. It SHALL distinguish queued, running, needs_clarification, completed, partial, conflict, failed, and cancelled statuses.

#### Scenario: Run and poll
- **WHEN** a valid plan request is submitted
- **THEN** the API returns 202 with a run ID and polling URL, and polling returns ordered new trace events and the eventual typed result.

#### Scenario: Stale clarification
- **WHEN** clarification answers use an outdated revision
- **THEN** the API returns 409 and does not mutate the run.

#### Scenario: Cancel and late completion
- **WHEN** a running request is cancelled and a provider callback later returns
- **THEN** cancellation remains terminal and the late callback cannot publish a completed result.

#### Scenario: Expired process-local run
- **WHEN** a run is unavailable after expiry or restart
- **THEN** the API returns 404 and the UI offers resubmission with an explanation.

### Requirement: Responsive planning workspace
Desktop UI SHALL provide left request/chat input, center itinerary, right agent activity, and a reserved map area. Narrow screens SHALL provide accessible stacked or tabbed views. Status MUST NOT rely on color alone.

#### Scenario: Day presentation
- **WHEN** a completed or partial plan is opened
- **THEN** each day shows city order, train/stations/times when known, POIs, local legs, estimated daily cost, and visible source/uncertainty labels alongside total budget.

#### Scenario: Mobile navigation
- **WHEN** the viewport is 390 pixels wide
- **THEN** input, itinerary, trace, and map fallback remain keyboard reachable without horizontal page overflow.

### Requirement: Map fallback and secret isolation
The map area SHALL present selected-day POIs/route context and a usable coordinate list when interactive rendering is unavailable. Backend Amap credentials MUST NOT be embedded in frontend assets; an interactive Amap map requires separately configured browser access.

#### Scenario: No map credential
- **WHEN** no browser map access is configured
- **THEN** day selection still displays POI names/coordinates and a clear map-unavailable state without breaking itinerary use.

### Requirement: Honest result and error states
The UI SHALL distinguish verified results, estimates, partial/unverified plans, impossible constraints, configuration failures, and provider failures. It MUST NOT describe a conflict or incomplete budget as a verified success.

#### Scenario: Over-budget result
- **WHEN** automatic repairs cannot satisfy the budget
- **THEN** the UI displays the excess, unresolved issues, and an option to revise constraints.

#### Scenario: Revision in progress
- **WHEN** the user requests a weather revision
- **THEN** the prior itinerary remains visible with its version while the new linked run is pending, and only the validated revision is shown as complete.

### Requirement: Local security and capacity
The backend SHALL bind locally by default, restrict CORS to configured frontend origins, reject oversized inputs, cap active runs at 2, and retain at most 50 terminal runs for at most 60 minutes. Secrets SHALL come only from environment variables and SHALL never appear in API responses or logs.

#### Scenario: Capacity exhausted
- **WHEN** two runs are active and a third is submitted
- **THEN** the API returns 503 with a safe retry message rather than starting unbounded work.
