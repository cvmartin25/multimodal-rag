from __future__ import annotations

import re
from typing import Any

import numpy as np

from .config import Settings
from .content_loader import load_content_bytes
from .embedding import Embedder
from .gemini_client import GeminiClientFactory
from .openai_client import OpenAIClientFactory
from .models import (
    DisplayData,
    Evidence,
    EvidenceLocator,
    IndexPayload,
    LlmHint,
    PrepareContextRequest,
    PrepareContextResponse,
    PreparedContextItem,
    RetrieveRequest,
    RetrieveResponse,
    SourceRef,
    StorageRef,
    TenantContext,
)
from .processors import (
    build_transcript_spans,
    chunk_audio,
    chunk_text,
    chunk_video,
    detect_content_type,
    get_video_duration_seconds,
    split_pdf_to_pages,
)
from .transcription import transcribe_video, transcribe_video_ranges
from .vector_store import SupabaseVectorStore
from .video_analysis import (
    analyze_full_video_with_flash,
    analyze_windows_with_flash,
    build_segments_from_windows,
    to_time_ranges,
)


class RagService:
    def __init__(
        self,
        settings: Settings,
        vector_store: SupabaseVectorStore,
        embedder: Embedder,
        gemini_factory: GeminiClientFactory,
        openai_factory: OpenAIClientFactory,
    ) -> None:
        self._settings = settings
        self._store = vector_store
        self._embedder = embedder
        self._gemini_factory = gemini_factory
        self._openai_factory = openai_factory

    def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        options = request.options
        top_k = options.top_k if options and options.top_k else self._settings.default_topk
        top_n = options.top_n if options and options.top_n else self._settings.default_topn
        threshold = options.threshold if options else 0.3
        collection = options.collection if options and options.collection else self._settings.default_collection
        use_two_stage = (
            options.use_two_stage
            if options and options.use_two_stage is not None
            else self._settings.two_stage_enabled
        )

        query_vec = self._embedder.embed_query(request.query.text)
        if use_two_stage:
            matches = self._two_stage_search(
                coach_profile_id=request.tenant.coach_profile_id,
                query_text=request.query.text,
                query_vec=query_vec,
                collection=collection,
                top_k=max(top_k, 1),
                threshold=threshold,
            )
        else:
            # Search all types first; type filtering is applied post-map for schema flexibility.
            matches = self._store.search(
                query_embedding=query_vec,
                top_k=max(top_k, 1),
                threshold=threshold,
                content_type=None,
                collection=collection,
                coach_profile_id=request.tenant.coach_profile_id,
            )

        evidences: list[Evidence] = []
        include_qa = bool(options and options.include_qa)
        type_filter = set(options.types) if options and options.types else None

        for row in matches:
            if not self._row_matches_tenant(row=row, coach_profile_id=request.tenant.coach_profile_id):
                continue
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
                "twoStage": use_two_stage,
            }
            if request.debug
            else None,
        )

    def run_indexing(self, payload: IndexPayload) -> int:
        file_bytes = load_content_bytes(content_base64=payload.content_base64, content_url=payload.content_url)
        content_type = detect_content_type(payload.mime_type, payload.original_filename)
        collection = payload.collection or self._settings.default_collection
        self._store.upsert_source(
            {
                "id": payload.source_id,
                "coach_profile_id": payload.tenant.coach_profile_id,
                "source_kind": payload.source_kind,
                "title": payload.title,
                "original_filename": payload.original_filename,
                "mime_type": payload.mime_type,
                "storage_bucket": payload.content_bucket,
                "storage_key": payload.content_key,
                "language": self._settings.transcript_language,
                "metadata": {"request_id": payload.request_id},
            }
        )

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
            pages = split_pdf_to_pages(
                file_bytes,
                target_width=self._settings.pdf_render_target_width,
                image_format=self._settings.pdf_render_format,
                image_quality=self._settings.pdf_render_quality,
            )
            for idx, page in enumerate(pages):
                vec = self._embedder.embed_binary_document(page.image_bytes, page.image_mime_type)
                row = self._build_base_row(
                    payload=payload,
                    collection=collection,
                    evidence_type="pdf_page",
                    chunk_index=idx,
                    chunk_total=len(pages),
                    embedding=vec,
                    text_content=page.extracted_text[:10000] if page.extracted_text else "",
                    metadata={
                        "labels": ["teaching", "proof"],
                        "locator": {"pageNumber": page.page_number},
                        "storage_refs": self._default_storage_refs(
                            payload,
                            page_number=page.page_number,
                            extension=page.image_extension,
                        ),
                        "hint_for_llm": f"Nutze Seite {page.page_number} als Proof-Quelle und zitiere exakt.",
                        "extraction_quality": page.extraction_quality,
                        "layout_complexity": page.layout_complexity,
                        "has_tables": page.has_tables,
                        "has_figures": page.has_figures,
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
            full_duration = get_video_duration_seconds(file_bytes, mime_type=payload.mime_type)
            segments = []
            if payload.analyze_video_relevance:
                segments = analyze_full_video_with_flash(
                    video_bytes=file_bytes,
                    mime_type=payload.mime_type,
                    duration_sec=full_duration,
                    gemini_factory=self._gemini_factory,
                )
            if not segments:
                fallback_windows = chunk_video(
                    video_bytes=file_bytes,
                    mime_type=payload.mime_type,
                    window_seconds=self._settings.window_seconds,
                    overlap_seconds=self._settings.overlap_seconds,
                )
                segments = (
                    analyze_windows_with_flash(windows=fallback_windows, gemini_factory=self._gemini_factory)
                    if payload.analyze_video_relevance
                    else build_segments_from_windows(fallback_windows)
                )

            ranges = to_time_ranges(segments=segments, include_qa=True)
            transcript_segments = transcribe_video_ranges(
                video_bytes=file_bytes,
                mime_type=payload.mime_type,
                ranges=ranges,
                openai_factory=self._openai_factory,
                model=self._settings.whisper_model,
                language=self._settings.transcript_language,
            )
            if not transcript_segments:
                transcript_segments = transcribe_video(
                    video_bytes=file_bytes,
                    mime_type=payload.mime_type,
                    openai_factory=self._openai_factory,
                    model=self._settings.whisper_model,
                    language=self._settings.transcript_language,
                )

            spans = build_transcript_spans(
                segments=transcript_segments,
                target_seconds=self._settings.transcript_target_span_seconds,
                max_seconds=self._settings.transcript_max_span_seconds,
            )
            for idx, span in enumerate(spans):
                vec = self._embedder.embed_text_document(span.text)
                span_start = int(max(0, span.start_sec))
                span_end = int(min(full_duration, max(span.end_sec, span.start_sec + 1)))
                row = self._build_base_row(
                    payload=payload,
                    collection=collection,
                    evidence_type="video_span",
                    chunk_index=idx,
                    chunk_total=len(spans),
                    embedding=vec,
                    text_content=span.text,
                    metadata={
                        "labels": ["teaching", "proof", "transcript"],
                        "segment_id": f"ts_{idx:04d}",
                        "segment_summary": "Transcript span from Whisper segmentation.",
                        "locator": {
                            "startSec": span_start,
                            "endSec": span_end,
                            "paddingSec": 0,
                        },
                        "storage_refs": self._default_storage_refs(payload),
                        "hint_for_llm": "Nutze diese Transcript-Spanne fuer Zeitstempel-Zitat im IEEE-Stil.",
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

    def _two_stage_search(
        self,
        coach_profile_id: str,
        query_text: str,
        query_vec: list[float],
        collection: str,
        top_k: int,
        threshold: float,
    ) -> list[dict[str, Any]]:
        rows = self._store.fetch_tenant_rows(
            coach_profile_id=coach_profile_id,
            collection=collection,
            limit=self._settings.two_stage_prefilter_limit,
        )
        if not rows:
            return []

        terms = self._tokenize(query_text)
        if not terms:
            terms = []

        lexical_ranked = sorted(
            rows,
            key=lambda r: self._lexical_score(r, terms),
            reverse=True,
        )
        candidates = lexical_ranked[: max(self._settings.two_stage_candidate_count, top_k)]
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in candidates:
            emb = row.get("embedding")
            if not isinstance(emb, list) or not emb:
                continue
            sim = self._cosine_similarity(query_vec, emb)
            if sim >= threshold:
                row_copy = dict(row)
                row_copy["similarity"] = sim
                scored.append((sim, row_copy))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in scored[:top_k]]

    def prepare_context(self, request: PrepareContextRequest) -> PrepareContextResponse:
        items: list[PreparedContextItem] = []
        for ev in request.evidences[: max(request.max_items, 1)]:
            if ev.tenant.coach_profile_id != request.tenant.coach_profile_id:
                continue
            checklist: list[str] = []
            if ev.type == "pdf_page":
                checklist = [
                    "Check table headers and footnotes on this page.",
                    "Verify if the relevant statement spans neighboring pages.",
                    "Cite page number explicitly in IEEE style, e.g. [1] PDF ... Seite X.",
                ]
            elif ev.type in {"video_window", "video_span"}:
                checklist = [
                    "Locate exact timestamp where concept is explained.",
                    "Prefer statement at sentence start for clean citation.",
                    "Return IEEE style citation, e.g. [2] Video ... Minute mm:ss.",
                ]
            else:
                checklist = [
                    "Use source conservatively.",
                    "Cite source id in final answer.",
                ]
            items.append(PreparedContextItem(evidence=ev, checklist=checklist))
        return PrepareContextResponse(requestId=request.request_id, preparedItems=items)

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
        if evidence_type in {"video_window", "video_span"}:
            return "video"
        if evidence_type == "audio_window":
            return "audio"
        if evidence_type == "text_chunk":
            return "text"
        return evidence_type

    def _default_storage_refs(
        self,
        payload: IndexPayload,
        page_number: int | None = None,
        extension: str = "png",
    ) -> list[dict[str, str]]:
        if payload.content_bucket and payload.content_key:
            key = payload.content_key
            if page_number is not None:
                key = f"{payload.content_key.rstrip('/')}/pages/{page_number}.{extension}"
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
    def _row_matches_tenant(row: dict[str, Any], coach_profile_id: str) -> bool:
        direct = row.get("coach_profile_id")
        if direct is not None:
            return str(direct) == coach_profile_id
        meta = row.get("metadata") or {}
        meta_coach = meta.get("coach_profile_id")
        if meta_coach is not None:
            return str(meta_coach) == coach_profile_id
        # Legacy rows without tenant data are treated as non-match in service mode.
        return False

    @staticmethod
    def _row_content_type_to_evidence_type(content_type: str | None) -> str:
        if content_type == "pdf":
            return "pdf_page"
        if content_type == "video":
            return "video_span"
        if content_type == "audio":
            return "audio_window"
        if content_type == "text":
            return "text_chunk"
        return "image"

    @staticmethod
    def _guess_source_kind(evidence_type: str) -> str:
        if evidence_type in {"pdf_page", "text_chunk"}:
            return "document"
        if evidence_type in {"video_window", "video_span"}:
            return "video"
        if evidence_type == "audio_window":
            return "audio"
        return "image"

    @staticmethod
    def _build_display_label(evidence_type: str, locator: dict[str, Any]) -> str:
        if evidence_type == "pdf_page" and locator.get("pageNumber"):
            return f"Seite {locator['pageNumber']}"
        if evidence_type in {"video_window", "video_span", "audio_window"} and locator.get("startSec") is not None:
            start = int(locator["startSec"])
            return f"ab {start // 60:02d}:{start % 60:02d}"
        return evidence_type

    @staticmethod
    def _default_hint_for(evidence: Evidence) -> str:
        if evidence.type == "pdf_page" and evidence.locator.page_number:
            return (
                f"Focus on page {evidence.locator.page_number}. "
                "Respond in own words and cite in IEEE style [n] PDF <title> Seite <x>."
            )
        if evidence.type in {"video_window", "video_span"} and evidence.locator.start_sec is not None:
            return "Respond in own words and cite timestamp in IEEE style [n] Video <title> Minute mm:ss."
        return "Use this source, respond in own words, and cite in IEEE style."

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [t for t in re.findall(r"[a-zA-Z0-9äöüÄÖÜß]{3,}", text.lower())]

    @staticmethod
    def _lexical_score(row: dict[str, Any], terms: list[str]) -> float:
        if not terms:
            return 0.0
        meta = row.get("metadata") or {}
        haystack = " ".join(
            [
                str(row.get("title") or ""),
                str(row.get("original_filename") or ""),
                str(row.get("text_content") or ""),
                str(meta.get("segment_summary") or ""),
                " ".join(str(x) for x in (meta.get("labels") or [])),
            ]
        ).lower()
        score = 0.0
        for term in terms:
            if term in haystack:
                score += 1.0
        return score

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        va = np.array(a, dtype=np.float64)
        vb = np.array(b, dtype=np.float64)
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        if denom == 0.0:
            return 0.0
        return float(np.dot(va, vb) / denom)

    @staticmethod
    def _match_segment_for_window(segments: list[Any], start_sec: int, end_sec: int):
        best = None
        best_overlap = -1
        for seg in segments:
            overlap = max(0, min(end_sec, seg.end_sec) - max(start_sec, seg.start_sec))
            if overlap > best_overlap:
                best = seg
                best_overlap = overlap
        return best

