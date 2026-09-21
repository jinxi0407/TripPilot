## Purpose
Normalize Chinese travel requests into explicit constraints and select only the research needed for an evidence-grounded itinerary.

## ADDED Requirements

### Requirement: Structured travel intake
The system SHALL extract origin, required destinations, duration, dates, CNY budget, preferences, and hard versus soft constraints. It SHALL preserve user constraints and show default assumptions, including one adult and no implicit return leg.

#### Scenario: Representative multi-city request
- **WHEN** a user requests “我想从上海出发，用5天游玩杭州、南京和苏州。预算4000元，喜欢历史景点和夜景，不想每天太赶。请结合高铁、天气、景点位置和市内交通帮我规划行程。”
- **THEN** the normalized request contains Shanghai, all three destinations, five days, a 400000-fen budget, history/night-view preferences, and a relaxed pace, without silently choosing calendar dates.

#### Scenario: Invalid or oversized input
- **WHEN** a request has a negative budget, inconsistent dates/day count, more than 7 days, more than 4 required destinations, or more than 4000 characters
- **THEN** the system returns a structured input/scope error before provider calls.

### Requirement: Clarify required facts
The system SHALL request missing origin, destinations, duration, or calendar dates needed for live planning, and SHALL resolve relative dates against an explicit Asia/Shanghai clock. It MUST NOT invent missing facts.

#### Scenario: Missing dates
- **WHEN** a five-day request lacks calendar dates in live mode
- **THEN** the run enters needs_clarification with a date question and performs no dated train or forecast queries.

#### Scenario: Fixture demonstration
- **WHEN** the user explicitly selects the sample fixture demo
- **THEN** fixed fixture dates and synthetic data are visibly identified and no live-data claim is made.

### Requirement: Selective structured routing
The system SHALL expose a structured routing decision and use only required specialists. Routing SHALL NOT require an open-ended reasoning/action loop.

#### Scenario: Multi-city plan
- **WHEN** a dated request requires inter-city rail plus local activities
- **THEN** routing selects Transport and Local Travel, collects their structured outputs, and invokes Travel Planner and Critic.

#### Scenario: Local itinerary
- **WHEN** origin and only destination are the same city and no inter-city travel is requested
- **THEN** Transport is skipped, Local Travel is selected, and no rail tool is called.

### Requirement: State preserves evidence and constraints
The system SHALL retain typed request facts, research results, draft/final itineraries, validation, revision counts, and ordered activity events throughout the run. Re-planning MUST preserve hard user constraints unless the user explicitly changes them.

#### Scenario: Budget repair
- **WHEN** Critic returns a budget violation
- **THEN** the next planning pass receives the original budget and issue references, and the budget is not raised automatically.
