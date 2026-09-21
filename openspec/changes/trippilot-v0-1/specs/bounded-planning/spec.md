## Purpose
Construct grounded multi-day itineraries with explicit execution limits, accountable evidence use, and useful partial results when planning cannot finish.

## ADDED Requirements

### Requirement: Evidence-grounded itinerary composition
The Travel Planner SHALL compose dated activities, evidenced inter-city and local legs, destination order, and daily/trip costs from specialist/tool results. It MUST NOT invent train numbers, times, fares, or availability.

#### Scenario: Supported multi-city itinerary
- **WHEN** complete fixture evidence supports the five-day Shanghai/Hangzhou/Nanjing/Suzhou request
- **THEN** the draft includes five dated days, all required cities, train/station details, POIs, local transport, costs, and evidence references.

#### Scenario: Missing rail evidence
- **WHEN** rail research yields no supported service
- **THEN** the planner returns an explicit transport gap or conflict instead of a plausible invented train.

### Requirement: Bounded reasoning and action
Planner SHALL use at most 8 decision steps per pass; optional Local Travel reasoning SHALL use at most 4 steps per run. Every reasoning/action loop SHALL have explicit finalization, deadline, retry, duplicate-action detection, and fallback. Failed decisions and schema repairs MUST consume step and global model-call budgets.

#### Scenario: Step exhaustion
- **WHEN** the eighth Planner decision has not produced a final itinerary
- **THEN** no ninth decision is made in that pass and the best draft proceeds to validation or a controlled partial/failed result.

#### Scenario: Duplicate action
- **WHEN** a tool request repeats with identical validated arguments and evidence revision
- **THEN** a successful prior result is reused without a provider call, or repeated failure after its allowed retry stops that action with DUPLICATE_ACTION.

### Requirement: Global execution budgets
A run SHALL allow at most 40 external tool attempts, 30 model attempts, a 90-second planning-pass deadline, and a 180-second execution deadline. Limits SHALL survive re-planning, and cancellation SHALL propagate to in-flight calls.

#### Scenario: Retry consumes global allowance
- **WHEN** the fortieth tool attempt fails and would otherwise be retried
- **THEN** no forty-first provider attempt occurs and the run terminates or validates existing evidence.

#### Scenario: Overall deadline
- **WHEN** 180 seconds of active execution have elapsed
- **THEN** further external work is cancelled and the system emits a controlled terminal result without an unbounded loop.

### Requirement: Hosted model and explicit fixture mode
Configured live planning SHALL use the selected Qwen model through hosted DashScope with credentials supplied only through environment variables. Invalid structured responses SHALL receive at most one bounded repair. Keyless fixture mode SHALL be explicit and distinguishable from live model execution.

#### Scenario: Malformed model output
- **WHEN** initial and repaired model decisions both violate the response schema
- **THEN** the run returns a controlled error/fallback and does not invoke an unvalidated tool.

#### Scenario: Missing live credentials
- **WHEN** live mode is requested without required model configuration
- **THEN** the run reports a configuration error and does not silently claim fixture output is live planning.

### Requirement: Safe observable activity
The system SHALL expose ordered agent/tool start, success, failure, and skip events with timings and concise summaries. Events MUST exclude private chain-of-thought, full prompts, and credentials.

#### Scenario: Visible planning progress
- **WHEN** the Planner calls a route tool and Critic checks the draft
- **THEN** the activity view shows their ordered statuses and safe outcomes linked to the itinerary version.

### Requirement: Automatic development mode
The system SHALL support an auto mode that selects Mock when Qwen configuration is missing and SHALL independently select labeled Mock Amap data when its key is missing. Explicit live model mode SHALL still reject missing Qwen configuration.

#### Scenario: No keys in development
- **WHEN** a user submits a request in auto mode without API keys
- **THEN** the system runs fixture providers with visible source labels and does not claim live model or provider execution.
