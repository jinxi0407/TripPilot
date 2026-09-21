from fastapi import APIRouter, Query, Request

from app.schemas.api import ClarificationRequest, PlanRequest, PlanResponse, RevisionRequest

router = APIRouter()


@router.post("/api/plan", status_code=202, response_model=PlanResponse)
@router.post("/api/v1/plans", status_code=202, response_model=PlanResponse)
async def create_plan(payload: PlanRequest, request: Request) -> dict:
    service = request.app.state.runs
    return service.public(service.create(payload))


@router.get("/api/trace/{task_id}", response_model=PlanResponse)
@router.get("/api/v1/plans/{task_id}", response_model=PlanResponse)
async def get_plan(task_id: str, request: Request, after_sequence: int = Query(default=0, ge=0)) -> dict:
    service = request.app.state.runs
    return service.public(service.store.get(task_id), after_sequence)


@router.post("/api/v1/plans/{task_id}/clarifications", status_code=202, response_model=PlanResponse)
async def clarify(task_id: str, payload: ClarificationRequest, request: Request) -> dict:
    service = request.app.state.runs
    return service.public(service.clarify(task_id, payload))


@router.post("/api/v1/plans/{task_id}/revisions", status_code=202, response_model=PlanResponse)
async def revise(task_id: str, payload: RevisionRequest, request: Request) -> dict:
    service = request.app.state.runs
    return service.public(service.revise(task_id, payload))


@router.post("/api/v1/plans/{task_id}/cancel", response_model=PlanResponse)
async def cancel(task_id: str, request: Request) -> dict:
    service = request.app.state.runs
    return service.public(service.cancel(task_id))
