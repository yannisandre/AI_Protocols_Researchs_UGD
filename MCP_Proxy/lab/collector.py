from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lab.common import append_event, authorized, events, health, valid_run


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str
    destination: str
    content: str = Field(max_length=20000)


async def collect(request):
    if not authorized(request, "collector_write"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        data = Submission.model_validate(await request.json())
        valid_run(data.run_id)
    except (ValidationError, ValueError):
        return JSONResponse({"error": "invalid submission"}, status_code=400)
    append_event("collector", data.run_id, event="received", destination=data.destination, content=data.content)
    return JSONResponse({"received": True})


async def evidence(request):
    if not authorized(request, "collector_read"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse({"events": events(request.path_params["run_id"])})


app = Starlette(routes=[Route("/health", health), Route("/collect", collect, methods=["POST"]),
                        Route("/evidence/{run_id}", evidence)])
