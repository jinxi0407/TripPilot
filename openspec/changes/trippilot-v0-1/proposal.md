# Proposal

## Why

Generic LLM itineraries often ignore train schedules, geographic distance, weather, and total cost. TripPilot will demonstrate a small, inspectable multi-agent system that grounds a mainland China itinerary in provider evidence and verifies constraints before presenting it.

## What Changes

- Plan a local FastAPI/LangGraph backend and React/Vite/TypeScript frontend powered by hosted Qwen through DashScope.
- Use exactly five logical agents, structured Supervisor routing, a bounded ReAct Travel Planner, and a Critic with bounded feedback-driven re-planning.
- Introduce a controlled Tool Registry, replaceable rail providers, and Amap POI, route, distance, and weather tools with typed contracts, provenance, and controlled failures.
- Support multi-city, multi-day plans, six-category budgets, weather/transport/budget/route revisions, visible activity events, and an optional map visualization with a keyless fallback.
- Define an offline fixture path and 24 evaluation cases comparing simple LLM planning with TripPilot using measured results only.
- This change currently produces specification artifacts only. Application implementation starts only after a subsequent user approval.

## Capabilities

### New Capabilities

- `trip-intake`: Chinese travel intent extraction, date clarification, structured routing, and typed shared state.
- `travel-tools`: controlled tool access, replaceable rail and Amap providers, provenance, timeouts, and failures.
- `bounded-planning`: bounded ReAct itinerary composition, Qwen integration, and readable activity events.
- `itinerary-validation`: deterministic constraint checks, budget accounting, and bounded dynamic re-planning.
- `planning-experience`: local API lifecycle and responsive chat/itinerary/trace/map user experience.
- `planning-evaluation`: repeatable fixtures, independent tests, metrics, and baseline comparison.

### Modified Capabilities

None; the repository has no existing application or specifications.

## Impact

Future implementation affects `backend/`, `frontend/`, `evals/`, and project documentation. External dependencies are hosted Qwen, Amap when configured, and a future authorized rail API; mock/dataset rail is sufficient for V0.1. No external accounts or keys are required to review this proposal. Root engineering rules and environment placeholders accompany it.

## Non-goals

No payment, ticket purchase, hotel booking, production authentication, Kubernetes, cloud deployment, complex microservices, local GPU inference, self-hosted LLM, or unauthorized scraping. Flights, deployed MCP tools, and A2A services are extension designs only. Two focused implementation days prioritize a working local demo, then architecture, then feature count.
