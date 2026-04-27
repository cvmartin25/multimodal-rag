from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


EvidenceType = Literal["pdf_page", "video_window", "audio_window", "image", "text_chunk"]
SourceKind = Literal["document", "video", "audio", "image", "text"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


class TenantContext(BaseModel):
    coach_profile_id: str = Field(alias="coachProfileId")


class QueryPayload(BaseModel):
    text: str


class RetrieveOptions(BaseModel):
    top_k: int | None = Field(default=None, alias="topK")
    top_n: int | None = Field(default=None, alias="topN")
    types: list[EvidenceType] | None = None
    collection: str | None = None
    include_qa: bool = Field(default=False, alias="includeQa")
    threshold: float = 0.3
    use_two_stage: bool | None = Field(default=None, alias="useTwoStage")


class RetrieveRequest(BaseModel):
    request_id: str = Field(alias="requestId")
    tenant: TenantContext
    query: QueryPayload
    options: RetrieveOptions | None = None
    debug: bool = False


class StorageRef(BaseModel):
    kind: str = "s3"
    bucket: str
    key: str


class SourceRef(BaseModel):
    kind: SourceKind
    source_id: str = Field(alias="sourceId")


class EvidenceLocator(BaseModel):
    page_number: int | None = Field(default=None, alias="pageNumber")
    start_sec: int | None = Field(default=None, alias="startSec")
    end_sec: int | None = Field(default=None, alias="endSec")
    padding_sec: int | None = Field(default=None, alias="paddingSec")


class DisplayData(BaseModel):
    title: str | None = None
    filename: str | None = None
    label: str | None = None


class Evidence(BaseModel):
    id: str
    type: EvidenceType
    tenant: TenantContext
    source: SourceRef
    locator: EvidenceLocator
    storage_refs: list[StorageRef] = Field(alias="storageRefs")
    display: DisplayData
    score: float
    labels: list[str] = []
    hint_for_llm: str | None = Field(default=None, alias="hintForLLM")
    extracted_text: str | None = Field(default=None, alias="extractedText")


class LlmHint(BaseModel):
    evidence_id: str = Field(alias="evidenceId")
    hint: str


class RetrieveResponse(BaseModel):
    request_id: str = Field(alias="requestId")
    evidences: list[Evidence]
    hints_for_llm: list[LlmHint] = Field(default_factory=list, alias="hintsForLLM")
    debug: dict[str, Any] | None = None


class PrepareContextRequest(BaseModel):
    request_id: str = Field(alias="requestId")
    tenant: TenantContext
    evidences: list[Evidence]
    max_items: int = Field(default=3, alias="maxItems")


class PreparedContextItem(BaseModel):
    evidence: Evidence
    checklist: list[str]


class PrepareContextResponse(BaseModel):
    request_id: str = Field(alias="requestId")
    prepared_items: list[PreparedContextItem] = Field(alias="preparedItems")


class IndexPayload(BaseModel):
    request_id: str = Field(alias="requestId")
    tenant: TenantContext
    source_kind: SourceKind = Field(alias="sourceKind")
    source_id: str = Field(alias="sourceId")
    title: str
    original_filename: str = Field(alias="originalFilename")
    mime_type: str = Field(alias="mimeType")
    collection: str | None = None
    content_base64: str = Field(alias="contentBase64")
    analyze_video_relevance: bool = Field(default=True, alias="analyzeVideoRelevance")
    content_bucket: str | None = Field(default=None, alias="contentBucket")
    content_key: str | None = Field(default=None, alias="contentKey")


class IndexResponse(BaseModel):
    request_id: str = Field(alias="requestId")
    job_id: str = Field(alias="jobId")
    status: JobStatus
    inserted_records: int = Field(alias="insertedRecords")
    message: str


class JobStatusResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    status: JobStatus
    inserted_records: int = Field(alias="insertedRecords")
    error: str | None = None

