## Build Log

### 2026-04-27

- Neuer Python-Service unter `services/rag_service/` aufgebaut (FastAPI).
- Endpunkte implementiert:
  - `POST /v1/rag/retrieve`
  - `POST /v1/rag/index`
  - `GET /v1/rag/jobs/{jobId}`
  - `GET /health`
- Service-to-service Auth via Bearer Secret (`RAG_SERVICE_AUTH_TOKEN`) umgesetzt.
- Supabase Vector Store Adapter ergänzt (`match_documents` RPC + Insert in `documents`).
- Evidence-Output eingeführt (mit `storageRefs`, `locator`, `labels`, `hintForLLM`).
- Indexing-Pipelines eingebaut:
  - Text-Chunking (~1000 Token Näherung)
  - PDF pro Seite (Seitenbild + extractedText optional)
  - Audio-Windowing
  - Video-Windowing (120s / 10s Overlap)
- Video-Relevanzpass aktuell mit Fallback-Segmentierung implementiert (Flash-Analyse als nächster Schritt).
- Service-Doku + `requirements.txt` + optionales `schema.sql` für tenant/source Felder ergänzt.
- Optionalen Endpoint `/v1/rag/prepare-context` ergänzt (n8n-freundliche Kontexthinweise pro Evidence).
- Tenant-Filter im Retrieval gehärtet (Legacy Rows ohne Tenant werden ignoriert).
- Video-Relevanzpass erweitert:
  - Best-effort Flash-Klassifikation pro Window (`teaching|qa|admin|noise`)
  - deterministischer Fallback bei Fehlern
  - `noise` Fenster werden beim Indexing übersprungen.
- Flow-Dokumentation auf ausführlichen Wartungsstil umgestellt (analog `docs/flows/example.md`).
- Neue Flows ergänzt:
  - `07_indexing_job_orchestration_flow.md`
  - `90_stellschrauben_tuning.md`

### 2026-04-27 (Abend)

- Video-Pipeline auf “Full Video First” erweitert:
  - Flash analysiert zuerst das komplette Video und liefert Segment-Timestamps.
  - Windowing erfolgt danach nur innerhalb relevanter Segmente.
  - Fallback bleibt aktiv (Window-basierte Analyse / deterministisch), wenn Full-Pass fehlschlägt.
- Retrieval auf 2-Stage erweitert:
  - Stage 1: lexikalische Vorselektion im tenant-scoped Datensatz.
  - Stage 2: semantisches Reranking per Cosine-Similarity.
  - Neue Config-Schalter für Prefilter/Candidate-Tuning.
- Doku aktualisiert:
  - `04_video_indexing_flow.md` auf Full-pass Soll-/Fallback-Logik angepasst.
  - `02_chat_answering_flow.md` um 2-Stage Hinweis ergänzt.
  - `90_stellschrauben_tuning.md` um neue Retrieval/Video-Stellschrauben ergänzt.
- Unit-Tests mit Mocks ergänzt:
  - `services/rag_service/tests/test_retrieval_two_stage.py`
  - `services/rag_service/tests/test_video_full_pass_indexing.py`
  - Fokus: 2-Stage Ranking und Full-pass Video-Segment->Range->Window Pipeline.
  - Testlauf erfolgreich via `python -m unittest discover -s services/rag_service/tests -p "test_*.py" -v` (2/2 OK).

### Aktueller Stand “geht / geht noch nicht”

**Geht**
- End-to-End Indexing und Retrieval technisch im Servicepfad.
- Tenant-Feld wird verarbeitet, Evidence ohne URLs ausgegeben.
- Top-K/Top-N Logik und QA-Filter (default downrank/exclude) vorhanden.

**Noch offen / bewusst als nächster Schritt**
- Produktiver Flash-Relevanzpass für Video-Segmente (derzeit sichere Fallback-Logik).
- Vollständige Java-Integration für Status-Callbacks und Batch-Presign-Resolve.
- Performance-Härtung für große Tenants (Two-stage Retrieval aktivieren, DB-Optimierungen).
