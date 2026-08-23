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

from src.api.errors import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    GradingUnavailableError,
    ModerationRejectedError,
    NotFoundError,
    RateLimitedError,
    TooLongError,
    UnprocessableError,
)
from src.api.routes import (
    auth,
    content_review,
    demo_instructor,
    demo_learner,
    evaluation,
    instructor_dashboard,
    learners,
    mastery,
    placement,
    questions,
    quiz,
    recommendation,
    rosters,
    sequencing_preview,
    subjects,
)
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


@app.exception_handler(AuthenticationError)
def _handle_authentication(request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": exc.message})


@app.exception_handler(ForbiddenError)
def _handle_forbidden(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message})


@app.exception_handler(UnprocessableError)
def _handle_unprocessable(request: Request, exc: UnprocessableError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message})


@app.exception_handler(TooLongError)
def _handle_too_long(request: Request, exc: TooLongError) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"error": "answer_too_long", "max_length": exc.max_length}
    )


@app.exception_handler(RateLimitedError)
def _handle_rate_limited(request: Request, exc: RateLimitedError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limited", "retry_after_seconds": exc.retry_after_seconds},
    )


@app.exception_handler(ModerationRejectedError)
def _handle_moderation_rejected(request: Request, exc: ModerationRejectedError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "moderation_rejected"})


@app.exception_handler(GradingUnavailableError)
def _handle_grading_unavailable(request: Request, exc: GradingUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "grading_unavailable"})


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
app.include_router(questions.router)
app.include_router(recommendation.router)
app.include_router(evaluation.router)
app.include_router(subjects.router)
app.include_router(sequencing_preview.router)
app.include_router(quiz.router)
app.include_router(auth.router)
app.include_router(learners.router)
app.include_router(rosters.router)
app.include_router(instructor_dashboard.router)
app.include_router(content_review.router)
app.include_router(demo_instructor.router)
