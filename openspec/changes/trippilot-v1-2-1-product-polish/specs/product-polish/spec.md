# Spec Delta

## Purpose
TripPilot SHALL provide source-grounded, readable daily travel plans with clear clarification, compact weather, and a traveler-first presentation while retaining truthful technical evidence in demo mode.

## ADDED Requirements

### Requirement: Necessary clarification only
The system SHALL block only for origin, destination, start date, and duration/end date, and SHALL return explicit missing fields and actionable questions.
#### Scenario: Five days with a start date
- **WHEN** the representative Shanghai five-day query includes start_date
- **THEN** duration is five, end_date is start_date plus four days, and optional hotel/passenger details do not block planning
#### Scenario: Missing departure city
- **WHEN** origin is absent
- **THEN** the UI asks for departure city with a matching input and can resume

### Requirement: Feasible daily activity density
The planner SHALL use evidenced POIs and routes for normally two or more relaxed full-day activities and three or more compact full-day activities when feasible, respecting opening hours, meals, transit, preferences and bounded execution.
#### Scenario: Transfer or weather limitation
- **WHEN** arrival is late, severe weather limits candidates, or a long attraction consumes the available window
- **THEN** fewer activities are permitted with an explanation instead of invented filler
#### Scenario: Day quality feedback
- **WHEN** a full day is unjustifiably empty, too dense, excessively routed, poorly clustered, or lacks feasible preference alignment
- **THEN** Critic emits DAY_TOO_EMPTY, DAY_TOO_DENSE, EXCESSIVE_TRANSIT, POI_CLUSTER_INEFFICIENT or NO_PREFERENCE_ALIGNMENT as applicable and uses the existing bounded replanning path

### Requirement: Evidenced weather in the itinerary
The system SHALL expose city, forecast_date, condition, min/max temperatures, optional precipitation/probability, source and status using only existing weather-tool records.
#### Scenario: Real forecast available
- **WHEN** a non-stale amap_live forecast matches the day and city
- **THEN** Day Card and compact overview show its actual weather and available temperatures; demo mode may show Amap Weather LIVE and MCP get_weather
#### Scenario: Forecast unavailable
- **WHEN** the date has no reliable forecast
- **THEN** Day Card shows 天气待临近出发确认 and no fabricated numerical temperature
#### Scenario: Weather activity conflict
- **WHEN** Critic reports WEATHER_RISK for a day
- **THEN** affected outdoor activities show 天气可能影响该活动 using that existing judgment

### Requirement: Traveler-first presentation
The UI SHALL default to traveler mode with readable typography, compact preference chips, trip summary, complete activity timeline, selected-day numbered map markers, compact accommodation and transport, and centralized pre-departure checks.
#### Scenario: Inspect details or demo
- **WHEN** the user expands day/transport details or switches to demo mode
- **THEN** actual sources and runtime statuses become visible without changing execution logic
#### Scenario: Browser acceptance
- **WHEN** desktop and mobile render all day activities and switch days
- **THEN** content is not clipped, map markers follow activity order, and console has no application errors

### Requirement: Preserve measured evidence
The implementation MUST preserve the original 50-case dataset, labels, expected outputs, protocols, runtime budgets, memory design and benchmark results.
#### Scenario: New validation
- **WHEN** this product version is validated
- **THEN** new tests, LIVE results and screenshots are saved separately and old benchmark metrics are identified as historical
