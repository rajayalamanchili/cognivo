"""FastAPI app skeleton -- deployed as a Vercel Python Function (ASGI).

Stateless per request (FR-013): nothing here holds state in process
memory across requests beyond the module-level singletons (DB engine,
Langfuse client) that are safe to re-create on cold start.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.errors import ConflictError, NotFoundError, UnprocessableError
from src.api.routes import demo_learner, mastery, placement
from src.observability.tracing import configure_tracing

logger = logging.getLogger("cognivo.api")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_tracing()
    yield


app = FastAPI(title="Cognivo API", lifespan=_lifespan)


@app.exception_handler(NotFoundError)
def _handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(ConflictError)
def _handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message})


@app.exception_handler(UnprocessableError)
def _handle_unprocessable(request: Request, exc: UnprocessableError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message})


@app.exception_handler(Exception)
def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(placement.router)
app.include_router(mastery.router)
app.include_router(demo_learner.router)

# Remaining route modules register themselves here as each is implemented
# (questions.py: T048-T050).
