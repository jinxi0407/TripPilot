## Purpose
为 TripPilot 增加可独立验证的标准 Agent 与 Tool 协议调用，以及统一执行保护，使真实服务故障、预算限制和降级行为可观测，同时保留既有五角色规划、真实数据来源和本地演示兼容性。

## ADDED Requirements

### Requirement: Discoverable travel tools
The system SHALL expose exactly five travel tools through a real independently started MCP Streamable HTTP service, with typed input/output and original provider provenance.
#### Scenario: Discovery and invocation
- **WHEN** a standard MCP client connects and discovers tools
- **THEN** search_rail, search_poi, get_weather, calculate_distance and plan_route are available and valid calls return structured evidence-backed results
#### Scenario: Tool outage
- **WHEN** MCP connection or invocation times out
- **THEN** bounded recovery preserves the execution deadline and clearly records MCP FALLBACK if existing local providers are used

### Requirement: Discoverable specialist agents
The system SHALL expose independent Transport and Local Travel A2A services using standard Agent Cards, messages, tasks and structured artifacts.
#### Scenario: Transport delegation
- **WHEN** the Supervisor needs intercity transport
- **THEN** it verifies rail-search, transfer-analysis and transport-feasibility capabilities and receives a typed transport result through a real A2A task that calls MCP search_rail
#### Scenario: Local delegation
- **WHEN** the Supervisor needs local research
- **THEN** it verifies poi-search, weather-search, local-route-planning and distance-calculation capabilities and maps the artifact from real A2A and MCP calls into graph state
#### Scenario: Specialist unavailable
- **WHEN** discovery, connection or task completion fails
- **THEN** the system records A2A FALLBACK and invokes the existing local specialist within remaining runtime limits, or returns a controlled failure if insufficient budget remains

### Requirement: Unified bounded runtime
The system SHALL apply configurable policies to agent steps, replanning, tool and external call budgets, total deadlines, per-operation timeout, retry, permissions and duplicate detection across local and protocol paths.
#### Scenario: Forbidden tool
- **WHEN** the planner requests delete_database or another tool outside its allowlist
- **THEN** no handler runs and runtime records TOOL_NOT_ALLOWED
#### Scenario: Repeated action
- **WHEN** equivalent tool arguments repeat beyond the configured threshold without new effective observation
- **THEN** execution stops repeating the tool and records DUPLICATE_TOOL_CALL as a controlled observation
#### Scenario: Step and call budgets
- **WHEN** the configured step, tool-call or external-call limit is exhausted
- **THEN** further execution is refused with STEP_LIMIT_REACHED, TOOL_BUDGET_EXCEEDED or EXTERNAL_CALL_BUDGET_EXCEEDED, including failed attempts and retries
#### Scenario: Delegation cannot reset budgets
- **WHEN** an A2A task consumes a delegated allowance or its completion is uncertain
- **THEN** the parent accounts for that allowance before further calls and fallback cannot reset the overall limits
#### Scenario: Nonretryable errors
- **WHEN** credentials, input validation or tool permissions are invalid
- **THEN** runtime does not retry them, sanitizes the error and exposes the failure reason

### Requirement: Validated results and preserved planning
The system SHALL validate model, MCP and A2A results, retain the existing ReAct loop and Critic, and bound automatic replanning through shared policy.
#### Scenario: Invalid structured output
- **WHEN** a response violates its schema
- **THEN** it cannot enter graph state unchecked and produces a controlled repair attempt when eligible or a safe failure
#### Scenario: Rain and budget recovery
- **WHEN** the user simulates severe rain or sets the five-day three-city budget to 200 RMB
- **THEN** Critic drives indoor replacement or reports an unsatisfiable budget without inventing prices, within the replanning limit

### Requirement: Truthful observability and confidentiality
The system SHALL expose actual provider and runtime health, safe protocol traces, elapsed time and failure reason without credentials or private reasoning.
#### Scenario: Healthy runtime
- **WHEN** MCP discovery succeeds and both specialist cards are reachable
- **THEN** health and UI show MCP CONNECTED with five tools, A2A 2/2 ONLINE and active Harness policy
#### Scenario: Real execution trace
- **WHEN** a normal protocol-mode plan completes
- **THEN** trace includes actual A2A Transport to MCP search_rail and A2A Local Travel to MCP search_poi operations with source labels
#### Scenario: Failed runtime
- **WHEN** a protocol service becomes unavailable
- **THEN** health and execution state show disconnection or fallback and cannot continue to claim successful protocol execution

### Requirement: Reproducible local acceptance and compatibility
The system SHALL provide simple service startup, locked stable official SDK versions, real local protocol integration tests and existing regression compatibility before claiming protocol engineering support.
#### Scenario: Developer startup
- **WHEN** the documented backend-services command is run
- **THEN** MCP, two A2A specialists and the main backend start on centrally configured loopback endpoints with clean shutdown and health checks
#### Scenario: V0.2 regression
- **WHEN** existing offline tests and fixture Demo run without protocol services
- **THEN** previous API, map, rain and budget behavior remains supported
#### Scenario: Final LIVE acceptance
- **WHEN** Qwen and Amap are configured and all services are started
- **THEN** normal, rain, budget and MCP failure scenarios are verified with actual protocols, truthful fallback, Rail DATASET and no secrets or hidden reasoning in logs
