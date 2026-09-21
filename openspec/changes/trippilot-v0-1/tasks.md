# Tasks

Implementation was approved in the subsequent user request. Checked tasks have corresponding code and validation evidence in docs/acceptance-report.md. Each unit targets roughly 15–60 minutes with Codex assistance; phase budgets are estimates, not delivery claims. See [design.md](design.md) for decisions and [acceptance.md](acceptance.md) for completion gates.

## 1. Phase A — Backend skeleton (0.5h)

- [x] 1.1 Create the documented backend package boundaries and Python >=3.11 environment; pin compatible FastAPI/Pydantic/LangGraph/test dependencies and verify clean installation plus import smoke check.
- [x] 1.2 Add environment settings, structured redacted logging, controlled errors, and /health; verify health and missing-configuration tests without keys or network.

## 2. Phase B — Qwen integration (0.75h)

- [x] 2.1 Check official DashScope documentation for the selected account region/model and implement an async ModelClient with 30-second timeouts and usage capture; verify mocked success, timeout, authentication, and absent-usage responses.
- [x] 2.2 Implement schema-validated decision output, one bounded repair, and explicit fixture ModelClient; verify malformed output cannot execute a tool and live mode without configuration fails clearly.

## 3. Phase C — Tool/provider layer (2h)

- [x] 3.1 Implement typed tool input/output/evidence/error models and registry allowlists, input/output validation, timeout/retry, and attempt accounting; verify unauthorized calls never reach providers and errors are redacted.
- [x] 3.2 Implement RailProvider, MockRailProvider, and DatasetRailProvider with dated direct/transfer fixtures; verify the same contract tests pass for both and unconfigured RealRailProvider returns unavailable without scraping.
- [x] 3.3 Implement AmapProvider and AmapPOITool with fixture injection, city/category search, GCJ-02 coordinates, and unknown opening-time handling; verify attraction/restaurant and malformed/empty results.
- [x] 3.4 Implement AmapRouteTool, AmapDistanceTool, and AmapWeatherTool; verify walking/driving, supported/unsupported transit, forecast horizon gaps, timeouts, and fixture operation without keys. Document actual supported API capabilities.

## 4. Phase D — LangGraph agents (1h)

- [x] 4.1 Implement shared typed state and Supervisor extraction/clarification/deterministic routing; verify the representative request, local-only routing, relative dates, and invalid request cases.
- [x] 4.2 Implement Transport and Local Travel nodes and specialist result collection; verify correct registry permissions and skipped unnecessary specialists with a fake model/provider graph.
- [x] 4.3 Wire explicit graph edges, global budgets, cancellation, and safe activity events; verify state/evidence preservation and graph-limit failure normalization.

## 5. Phase E — ReAct planner (1.5h)

- [x] 5.1 Implement Planner typed action/final decisions with 8-step limit and 90-second pass deadline; verify grounded draft output and hard stop on step/deadline exhaustion with an injected clock.
- [x] 5.2 Add canonical duplicate-action detection/cache, bounded retries, 40-tool/30-model global caps, and 180-second run deadline; verify failed/repair attempts count and re-planning cannot reset counters.
- [x] 5.3 Implement best-draft fallback and explicit finalization; verify missing rail evidence is reported without invented schedules. Keep Local Travel deterministic for V0.1; if optional ReAct is enabled, verify its shared 4-step cap with the same executor.

## 6. Phase F — Critic/replanning (1.5h)

- [x] 6.1 Implement chronology, opening intervals, station/interchange buffers, local travel, density, city/day coverage, and bounded route-comparison checks; verify closed POI, 15-minute rail risk, cross-station transfer, and missing-data cases.
- [x] 6.2 Implement six-category integer-fen cost reconciliation and budget validation; verify unknown fares, over-budget amounts, accommodation nights, and a cross-midnight fare counted once.
- [x] 6.3 Implement feedback routing with <=2 re-plans, repeated-issue early stop, and complete/partial/conflict outcomes; verify impossible constraints cannot loop or silently change the budget.
- [x] 6.4 Implement weather/transport/budget/route revisions and evidence invalidation; verify severe-rain indoor substitution, changed train selection, refreshed routes, and whole-itinerary revalidation.

## 7. Phase G — FastAPI endpoints (1.25h across both days)

- [x] 7.1 Implement create/poll/clarify/revise/cancel endpoints and public response schemas; verify 202 lifecycle, trace cursor ordering, 404 unknown run, 409 stale revision, and 422 invalid input.
- [x] 7.2 Implement bounded in-memory store, loopback/CORS defaults, cancellation propagation, and retention; verify 503 at capacity, expiry, and late callbacks cannot overwrite terminal states.

## 8. Phase H — React UI (2h)

- [x] 8.1 Scaffold React/Vite/TypeScript with locked dependencies, API client separate from UI, and shared response types; verify typecheck and production build.
- [x] 8.2 Build responsive input/clarification and itinerary panels with train, POI, local leg, daily/category cost, budget, and source labels; verify representative fixture flow on desktop and a 390px viewport.
- [x] 8.3 Add polling, cancellation, revisions, and loading/partial/conflict/configuration/failure states; verify old-plan retention during revisions and retry/resubmit on API failure or expired run.

## 9. Phase I — Map/trace UI (0.75h)

- [x] 9.1 Render ordered Supervisor/Rail Search/Amap POI/Planner/Critic activity with text/icon status and safe summaries; verify skipped/failed states and that no prompts, private reasoning, or secrets reach the UI.
- [x] 9.2 Reserve a day-selectable map area with POI/coordinate fallback; verify no-key behavior and backend-key exclusion from browser assets. Optional interactive Amap rendering is time-boxed and not a release gate; record deferred status if browser access is absent.

## 10. Phase J — Tests/evaluation (2.75h)

- [x] 10.1 Materialize the 24 cases in docs/evaluation-plan.md as versioned JSONL and provider fixtures with fixed clocks, expected routes/tools, and assertions; verify schema validity and source/license labels.
- [x] 10.2 Run independent backend unit and graph/API integration tests without external network; verify all required spec scenarios including max-step, fallback, re-planning, budget, redaction, cancellation, and provider substitution.
- [x] 10.3 Build the simple single-call baseline and TripPilot evaluation runner using the same frozen evidence universe and validator; verify metric denominators, null handling, run metadata, and deterministic repeatability.
- [x] 10.4 Run fixture evaluation and, when configured, a measured Qwen comparison with the same model/settings; publish raw per-case results and aggregates, or explicitly mark live comparison not run. Verify no fabricated percentages or unsupported transport facts in successful fixture cases.
- [x] 10.5 Complete one end-to-end happy flow, one severe-rain revision, one impossible-budget flow, and one provider outage in the browser; record acceptance evidence and confirm frontend build/typecheck pass.

## 11. Phase K — README/demo polish (1h plus 1h integration buffer)

- [x] 11.1 Replace planning-only README setup notes with tested local start/test/eval commands and configuration/mode instructions; verify a fresh environment can reproduce the fixture demo with no real keys.
- [x] 11.2 Add a concise demo script and screenshots, documented limitations, and MCP/A2A extension boundaries; verify no unimplemented feature or unmeasured improvement is presented as working.
- [x] 11.3 Review acceptance.md, implementation/spec alignment, Git diff, and secret exclusions; run strict OpenSpec validation and record remaining limitations. Do not push or archive an incomplete change.
