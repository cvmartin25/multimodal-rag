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

### Aktueller Stand “geht / geht noch nicht”

**Geht**
- End-to-End Indexing und Retrieval technisch im Servicepfad.
- Tenant-Feld wird verarbeitet, Evidence ohne URLs ausgegeben.
- Top-K/Top-N Logik und QA-Filter (default downrank/exclude) vorhanden.

**Noch offen / bewusst als nächster Schritt**
- Produktiver Flash-Relevanzpass für Video-Segmente (derzeit sichere Fallback-Logik).
- Vollständige Java-Integration für Status-Callbacks und Batch-Presign-Resolve.
- Performance-Härtung für große Tenants (Two-stage Retrieval aktivieren, DB-Optimierungen).
