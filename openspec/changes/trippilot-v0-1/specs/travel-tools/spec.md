## Purpose
Provide controlled, replaceable, typed travel research with clear evidence provenance and predictable failures for mainland China itineraries.

## ADDED Requirements

### Requirement: Controlled schema-validated tool access
Every tool call SHALL enforce agent permissions and explicit input/output schemas before accepting results. V0.1 SHALL expose read-only tools only; future high-risk/write tools MUST require explicit approval.

#### Scenario: Unauthorized tool
- **WHEN** Transport requests a local POI tool or an agent requests an unregistered purchase tool
- **THEN** access is denied and the provider is not invoked.

#### Scenario: Invalid provider payload
- **WHEN** a provider returns malformed timestamps or an invalid result structure
- **THEN** the tool returns a sanitized controlled error and no invalid facts enter itinerary evidence.

### Requirement: Replaceable railway research
Rail research SHALL provide direct/transfer options, departure and arrival stations/times, duration, fare or explicit unknown, train type, and availability provenance through the same contract for mock, dataset, and future authorized real providers. Agents MUST NOT depend on railway website HTML or unauthorized scraping.

#### Scenario: Provider substitution
- **WHEN** configuration changes from mock to dataset for the same supported rail query
- **THEN** the Transport consumer accepts the same result schema without logic changes and the source label changes accordingly.

#### Scenario: Unconfigured real rail
- **WHEN** real rail is selected without a configured authorized adapter
- **THEN** a controlled unavailable/configuration result is returned; no website scraping or fabricated live schedule occurs.

#### Scenario: Transfer evidence
- **WHEN** a rail option requires a transfer
- **THEN** every leg exposes dated station/time information and the interchange duration is available for feasibility validation.

### Requirement: Mainland local research
The system SHALL support Amap-backed POI/attraction/restaurant search, explicit coordinates, distance, walking/driving routes, public transit when supported, and weather. Unsupported modes or dates SHALL return controlled unavailable results.

#### Scenario: POI and route lookup
- **WHEN** Local Travel researches a city and a pair of selected POIs
- **THEN** results include source references, GCJ-02 coordinates where supplied, and supported route duration/distance; absent opening times remain unknown.

#### Scenario: Unsupported transit or forecast horizon
- **WHEN** the requested transit route or weather date is outside provider coverage
- **THEN** the system reports unavailable coverage and does not substitute invented data or label straight-line distance as a timed route.

### Requirement: Evidence provenance and honest costs
Each returned fact SHALL carry provider, source kind, retrieval time, applicable date range, and quality/staleness information. Unknown fares/availability MUST remain unknown; fixture results MUST never appear as live.

#### Scenario: Dataset train
- **WHEN** an itinerary uses a dated dataset train record
- **THEN** the UI and result retain its dataset source, valid date, and non-guaranteed seat availability.

### Requirement: Bounded sanitized provider failures
External calls SHALL time out within 10 seconds per attempt, retry at most once for transient faults within the remaining run budget, and never retry authentication or unsupported inputs. Provider errors and logs MUST NOT contain secrets or raw credential-bearing responses.

#### Scenario: Timeout and retry
- **WHEN** a tool times out twice
- **THEN** it returns TIMEOUT, consumes two global attempts, and planning uses an explicit fallback or partial outcome.

#### Scenario: Credential failure
- **WHEN** a provider returns an authentication error containing a token or key in its raw body
- **THEN** the public error and logs contain only sanitized error metadata and no retry is performed.
