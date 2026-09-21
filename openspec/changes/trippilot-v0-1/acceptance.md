# Acceptance criteria

These are future implementation gates. Passing OpenSpec structural validation does not mean the application is implemented or these gates passed.

| ID | Acceptance condition | Evidence | Spec / tasks |
|---|---|---|---|
| AC01 | Representative Chinese request preserves five days, all three cities, 4000-yuan cap and preferences; missing dates ask for clarification. | Intake/routing tests, visible clarification | trip-intake; 4.1 |
| AC02 | Five logical agents execute through typed state; local-only plans skip rail. | Graph integration trace and routing assertions | trip-intake; 4.2–4.3 |
| AC03 | Rail mock/dataset providers pass identical contracts; unconfigured real provider fails safely. No scraping. | Provider tests and dependency review | travel-tools; 3.1–3.2 |
| AC04 | POI/restaurant/route/distance/weather tools handle valid, empty, malformed, timed-out, and unsupported results. | Independent mocked provider tests | travel-tools; 3.3–3.4 |
| AC05 | Registry denies unauthorized calls; logs/errors/UI contain no secret markers. | Permission/redaction tests and browser asset check | travel-tools, planning-experience; 3.1, 9.2, 10.2 |
| AC06 | Planner max_steps=8, optional Local max_steps=4; retry/duplicate/deadline/global budgets terminate reliably. | Injected-clock/counter tests, cases 21–23 | bounded-planning; 5.1–5.3 |
| AC07 | Critic detects schedules, openings, station/transfer buffers, excessive travel/density, missing cities, and inefficient routes. | Cases 08–12, 18–19 and unit tests | itinerary-validation; 6.1 |
| AC08 | All six cost categories reconcile; overflow triggers repair/conflict; unknown fares stay unknown. | Cases 12–15 and integer arithmetic tests | itinerary-validation; 6.2 |
| AC09 | Weather, train conflict, budget and route revisions revalidate; no run exceeds two automatic re-plans. | Cases 13–20, graph trace, repeated-issue test | itinerary-validation; 6.3–6.4 |
| AC10 | Run API supports polling, clarification, revisions, cancel, expiry, capacity, and stable terminal states. | API integration suite including 404/409/422/503 | planning-experience; 7.1–7.2 |
| AC11 | Desktop three-panel UI and narrow-screen UI display itinerary, budget, provenance, uncertainty, safe trace and map fallback. | Browser checks at 1440px and 390px; typecheck/build | planning-experience; 8.1–9.2 |
| AC12 | Fixture demo works without keys; configured Qwen adapter has mocked coverage and documented opt-in live check. | Fresh local demo, config-error and malformed-output tests | bounded-planning; 2.1–2.2, 11.1 |
| AC13 | Twenty-four cases and all ten metrics are defined/materialized; baseline comparison uses measured rows or explicitly says not run. | Case-schema check, fixture run and evaluation report | planning-evaluation; 10.1–10.4 |
| AC14 | README accurately describes tested behavior, limitations, demo flow and future MCP/A2A boundaries; no fabricated gains. | Documentation/spec review and AC evidence record | all; 11.1–11.3 |

Completion requires all mandatory gates, an offline end-to-end success, severe-rain repair, impossible-budget conflict, and a provider outage demonstration. Optional live rail, interactive map, and real-model comparison without supplied credentials do not block the fixture demo; their status must be explicit. Application quality claims require application tests, not this planning validation.
