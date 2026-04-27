from __future__ import annotations

import base64
from typing import Any

from .config import Settings
from .embedding import Embedder
from .models import (
    DisplayData,
    Evidence,
    EvidenceLocator,
    IndexPayload,
    LlmHint,
    RetrieveRequest,
    RetrieveResponse,
    SourceRef,
    StorageRef,
    TenantContext,
)
from .processors import (
    chunk_audio,
    chunk_text,
    chunk_video,
    detect_content_type,
    split_pdf_to_pages,
)
from .vector_store import SupabaseVectorStore
from .video_analysis import build_segments_from_windows


class RagService:
    def __init__(self, settings: Settings, vector_store: SupabaseVectorStore, embedder: Embedder) -> None:
        self._settings = settings
        self._store = vector_store
        self._embedder = embedder

    def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        options = request.options
        top_k = options.top_k if options and options.top_k else self._settings.default_topk
        top_n = options.top_n if options and options.top_n else self._settings.default_topn
        threshold = options.threshold if options else 0.3
        collection = options.collection if options and options.collection else self._settings.default_collection

        query_vec = self._embedder.embed_query(request.query.text)
        # Search all types first; type filtering is applied post-map for schema flexibility.
        matches = self._store.search(
            query_embedding=query_vec,
            top_k=max(top_k, 1),
            threshold=threshold,
            content_type=None,
            collection=collection,
        )

        evidences: list[Evidence] = []
        include_qa = bool(options and options.include_qa)
        type_filter = set(options.types) if options and options.types else None

        for row in matches:
            evidence = self._map_row_to_evidence(row=row, coach_profile_id=request.tenant.coach_profile_id)
            if type_filter and evidence.type not in type_filter:
                continue
            if not include_qa and "qa" in evidence.labels:
                # Soft drop by default for safety.
                continue
            evidences.append(evidence)

        evidences = evidences[:top_n if top_n > 0 else len(evidences)]
        hints = [
            LlmHint(
                evidenceId=e.id,
                hint=e.hint_for_llm or self._default_hint_for(e),
            )
            for e in evidences
        ]
        return RetrieveResponse(
            requestId=request.request_id,
            evidences=evidences,
            hintsForLLM=hints,
            debug={
                "topK": top_k,
                "topN": top_n,
                "returned": len(evidences),
            }
            if request.debug
            else None,
        )

    def run_indexing(self, payload: IndexPayload) -> int:
        file_bytes = base64.b64decode(payload.content_base64)
        content_type = detect_content_type(payload.mime_type, payload.original_filename)
        collection = payload.collection or self._settings.default_collection

        inserted = 0
        if content_type == "text":
            text = file_bytes.decode("utf-8", errors="replace")
            chunks = chunk_text(text)
            for idx, chunk in enumerate(chunks):
                vec = self._embedder.embed_text_document(chunk)
                row = self._build_base_row(
                    payload=payload,
                    collection=collection,
                    evidence_type="text_chunk",
                    chunk_index=idx,
                    chunk_total=len(chunks),
                    embedding=vec,
                    text_content=chunk,
                    metadata={
                        "labels": ["text"],
                        "locator": {},
                        "storage_refs": self._default_storage_refs(payload),
                    },
                )
                self._store.insert_record(row)
                inserted += 1

        elif content_type == "pdf":
            pages = split_pdf_to_pages(file_bytes)
            for idx, page in enumerate(pages):
                vec = self._embedder.embed_binary_document(page.image_bytes, page.image_mime_type)
                row = self._build_base_row(
                    payload=payload,
                    collection=collection,
                    evidence_type="pdf_page",
                    chunk_index=idx,
                    chunk_total=len(pages),
                    embedding=vec,
                    text_content=page.extracted_text[:10000] if page.extracted_text else None,
                    metadata={
                        "labels": ["teaching"],
                        "locator": {"pageNumber": page.page_number},
                        "storage_refs": self._default_storage_refs(payload, page_number=page.page_number),
                        "hint_for_llm": f"Read PDF page {page.page_number}.",
                    },
                )
                self._store.insert_record(row)
                inserted += 1

        elif content_type == "audio":
            windows = chunk_audio(file_bytes, mime_type=payload.mime_type)
            for idx, w in enumerate(windows):
                vec = self._embedder.embed_binary_document(w.payload, w.mime_type)
                row = self._build_base_row(
                    payload=payload,
                    collection=collection,
                    evidence_type="audio_window",
                    chunk_index=idx,
                    chunk_total=len(windows),
                    embedding=vec,
                    text_content=None,
                    metadata={
                        "labels": ["audio"],
                        "locator": {
                            "startSec": int(w.start_sec),
                            "endSec": int(w.end_sec),
                            "paddingSec": self._settings.video_padding_seconds,
                        },
                        "storage_refs": self._default_storage_refs(payload),
                    },
                )
                self._store.insert_record(row)
                inserted += 1

        elif content_type == "video":
            windows = chunk_video(
                video_bytes=file_bytes,
                mime_type=payload.mime_type,
                window_seconds=self._settings.window_seconds,
                overlap_seconds=self._settings.overlap_seconds,
            )
            segments = build_segments_from_windows(windows)
            segment_by_id = {s.segment_id: s for s in segments}

            for idx, w in enumerate(windows):
                segment = segment_by_id.get(f"seg_{idx:04d}")
                vec = self._embedder.embed_binary_document(w.payload, w.mime_type)
                row = self._build_base_row(
                    payload=payload,
                    collection=collection,
                    evidence_type="video_window",
                    chunk_index=idx,
                    chunk_total=len(windows),
                    embedding=vec,
                    text_content=(segment.summary if segment else None),
                    metadata={
                        "labels": [segment.label] if segment else ["teaching"],
                        "segment_id": segment.segment_id if segment else None,
                        "segment_summary": segment.summary if segment else None,
                        "locator": {
                            "startSec": int(w.start_sec),
                            "endSec": int(w.end_sec),
                            "paddingSec": self._settings.video_padding_seconds,
                        },
                        "storage_refs": self._default_storage_refs(payload),
                        "hint_for_llm": "Inspect this video time range for a precise citation.",
                    },
                )
                self._store.insert_record(row)
                inserted += 1

        else:
            # image fallback
            vec = self._embedder.embed_binary_document(file_bytes, payload.mime_type)
            row = self._build_base_row(
                payload=payload,
                collection=collection,
                evidence_type="image",
                chunk_index=0,
                chunk_total=1,
                embedding=vec,
                text_content=None,
                metadata={
                    "labels": ["image"],
                    "locator": {},
                    "storage_refs": self._default_storage_refs(payload),
                },
            )
            self._store.insert_record(row)
            inserted += 1

        return inserted

    def _build_base_row(
        self,
        payload: IndexPayload,
        collection: str,
        evidence_type: str,
        chunk_index: int,
        chunk_total: int,
        embedding: list[float],
        text_content: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        row = {
            "title": payload.title,
            "content_type": self._to_legacy_content_type(evidence_type),
            "original_filename": payload.original_filename,
            "chunk_index": chunk_index,
            "chunk_total": chunk_total,
            "text_content": text_content.replace("\x00", "") if text_content else None,
            "metadata": {
                **metadata,
                "evidence_type": evidence_type,
                "coach_profile_id": payload.tenant.coach_profile_id,
                "source_kind": payload.source_kind,
                "source_id": payload.source_id,
            },
            "embedding": embedding,
            "collection": collection,
            "coach_profile_id": payload.tenant.coach_profile_id,
            "source_kind": payload.source_kind,
            "source_id": payload.source_id,
        }
        return row

    @staticmethod
    def _to_legacy_content_type(evidence_type: str) -> str:
        if evidence_type == "pdf_page":
            return "pdf"
        if evidence_type == "video_window":
            return "video"
        if evidence_type == "audio_window":
            return "audio"
        if evidence_type == "text_chunk":
            return "text"
        return evidence_type

    def _default_storage_refs(self, payload: IndexPayload, page_number: int | None = None) -> list[dict[str, str]]:
        if payload.content_bucket and payload.content_key:
            key = payload.content_key
            if page_number is not None:
                key = f"{payload.content_key.rstrip('/')}/pages/{page_number}.png"
            return [{"kind": "s3", "bucket": payload.content_bucket, "key": key}]
        # fallback when S3 ref is not yet integrated
        return [
            {
                "kind": "inline",
                "bucket": "inline",
                "key": f"{payload.source_kind}/{payload.source_id}",
            }
        ]

    def _map_row_to_evidence(self, row: dict[str, Any], coach_profile_id: str) -> Evidence:
        meta = row.get("metadata") or {}
        locator = meta.get("locator") or {}
        storage_refs = meta.get("storage_refs") or [
            {"kind": "inline", "bucket": "inline", "key": row.get("original_filename", "unknown")}
        ]
        evidence_type = meta.get("evidence_type") or self._row_content_type_to_evidence_type(row.get("content_type"))
        label = self._build_display_label(evidence_type, locator)
        score = float(row.get("similarity", 0.0))
        return Evidence(
            id=str(row.get("id")),
            type=evidence_type,
            tenant=TenantContext(coachProfileId=coach_profile_id),
            source=SourceRef(
                kind=str(meta.get("source_kind") or self._guess_source_kind(evidence_type)),
                sourceId=str(meta.get("source_id") or row.get("original_filename", "unknown")),
            ),
            locator=EvidenceLocator(
                pageNumber=locator.get("pageNumber"),
                startSec=locator.get("startSec"),
                endSec=locator.get("endSec"),
                paddingSec=locator.get("paddingSec"),
            ),
            storageRefs=[StorageRef(**ref) for ref in storage_refs],
            display=DisplayData(
                title=row.get("title"),
                filename=row.get("original_filename"),
                label=label,
            ),
            score=score,
            labels=list(meta.get("labels") or []),
            hintForLLM=meta.get("hint_for_llm"),
            extractedText=row.get("text_content"),
        )

    @staticmethod
    def _row_content_type_to_evidence_type(content_type: str | None) -> str:
        if content_type == "pdf":
            return "pdf_page"
        if content_type == "video":
            return "video_window"
        if content_type == "audio":
            return "audio_window"
        if content_type == "text":
            return "text_chunk"
        return "image"

    @staticmethod
    def _guess_source_kind(evidence_type: str) -> str:
        if evidence_type in {"pdf_page", "text_chunk"}:
            return "document"
        if evidence_type == "video_window":
            return "video"
        if evidence_type == "audio_window":
            return "audio"
        return "image"

    @staticmethod
    def _build_display_label(evidence_type: str, locator: dict[str, Any]) -> str:
        if evidence_type == "pdf_page" and locator.get("pageNumber"):
            return f"Seite {locator['pageNumber']}"
        if evidence_type in {"video_window", "audio_window"} and locator.get("startSec") is not None:
            start = int(locator["startSec"])
            return f"ab {start // 60:02d}:{start % 60:02d}"
        return evidence_type

    @staticmethod
    def _default_hint_for(evidence: Evidence) -> str:
        if evidence.type == "pdf_page" and evidence.locator.page_number:
            return f"Focus on page {evidence.locator.page_number} and cite clearly."
        if evidence.type == "video_window" and evidence.locator.start_sec is not None:
            return "Use this video range and cite exact timestamp."
        return "Use this source and cite evidence."

