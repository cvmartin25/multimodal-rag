from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Header, status
from dotenv import load_dotenv

from .auth import authorize_service_call
from .config import load_settings
from .embedding import Embedder
from .gemini_client import GeminiClientFactory
from .job_store import InMemoryJobStore
from .models import (
    IndexPayload,
    IndexResponse,
    JobStatusResponse,
    PrepareContextRequest,
    PrepareContextResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from .service import RagService
from .vector_store import SupabaseVectorStore
from .openai_client import OpenAIClientFactory

load_dotenv()

settings = load_settings()
job_store = InMemoryJobStore()
gemini_factory = GeminiClientFactory(api_key=settings.gemini_api_key)
openai_factory = OpenAIClientFactory(api_key=settings.openai_api_key)
service = RagService(
    settings=settings,
    vector_store=SupabaseVectorStore(settings=settings),
    embedder=Embedder(gemini_factory=gemini_factory),
    gemini_factory=gemini_factory,
    openai_factory=openai_factory,
)

app = FastAPI(title="CoachApp RAG Service", version="0.1.0")


def _auth(authorization: str | None = Header(default=None)) -> None:
    authorize_service_call(settings=settings, authorization=authorization)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/rag/retrieve", response_model=RetrieveResponse)
def retrieve(
    payload: RetrieveRequest,
    _: None = Depends(_auth),
) -> RetrieveResponse:
    return service.retrieve(payload)


@app.post("/v1/rag/prepare-context", response_model=PrepareContextResponse)
def prepare_context(
    payload: PrepareContextRequest,
    _: None = Depends(_auth),
) -> PrepareContextResponse:
    return service.prepare_context(payload)


@app.post("/v1/rag/index", response_model=IndexResponse)
def index(
    payload: IndexPayload,
    _: None = Depends(_auth),
) -> IndexResponse:
    job = job_store.create()
    job_store.set_running(job.job_id)
    try:
        inserted = service.run_indexing(payload)
        state = job_store.set_succeeded(job.job_id, inserted_records=inserted)
        return IndexResponse(
            requestId=payload.request_id,
            jobId=state.job_id,
            status=state.status,
            insertedRecords=state.inserted_records,
            message="Indexing finished successfully.",
        )
    except Exception as exc:
        state = job_store.set_failed(job.job_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "requestId": payload.request_id,
                "jobId": state.job_id,
                "status": state.status,
                "error": state.error,
            },
        ) from exc


@app.get("/v1/rag/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(
    job_id: str,
    _: None = Depends(_auth),
) -> JobStatusResponse:
    state = job_store.get(job_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobStatusResponse(
        jobId=state.job_id,
        status=state.status,
        insertedRecords=state.inserted_records,
        error=state.error,
    )

