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


@router.get("/api/v1/preferences")
async def get_preferences(request: Request):
    return {"preferences": request.app.state.runs.preferences.load().model_dump(), "state": "ACTIVE"}


from app.persistence.memory import extract_preferences
from app.schemas.product import PreferenceRequest, TravelPreferences


@router.post("/api/v1/preferences")
async def save_preferences(payload: PreferenceRequest, request: Request):
    data = extract_preferences(payload.query or "")
    data.update(payload.preferences.model_dump(exclude_unset=True))
    result = request.app.state.runs.preferences.update(
        TravelPreferences.model_validate(data), payload.remember_preferences
    )
    return {"preferences": result.model_dump(), "saved": payload.remember_preferences}


@router.post("/api/v1/preferences/clear")
async def clear_preferences(request: Request):
    request.app.state.runs.preferences.clear()
    return {"preferences": TravelPreferences().model_dump(), "cleared": True}
