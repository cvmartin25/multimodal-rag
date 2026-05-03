## Flow: PDF Indexing

Dieses Dokument beschreibt die PDF-Ingestion von “Upload fertig” bis “retrievalfähig”.

---

## Kurzüberblick

- Java markiert Dokument als `uploaded`.
- n8n startet den Python-Index-Job.
- Python zerlegt PDF seitenweise, erzeugt pro Seite multimodales Embedding und speichert Evidence.
- Jede Seite wird als `pdf_page` mit `locator.pageNumber` gespeichert.

---

## 1. Detaillierter Ablauf

1) Upload wurde in Java abgeschlossen (`complete-upload`).
2) Java/n8n triggert `POST /v1/rag/index` mit:
   - `coachProfileId`
   - `sourceKind=document`
   - `sourceId=documentId`
   - **Medienbytes**, über eine der Varianten:
     - `contentBase64`
     - `contentUrl` (presigned GET für das Original)
     - **`contentBucket` + `contentKey`**, wenn der Python-Service **Worker-Object-Storage** hat (`RAG_S3_*`): dann lädt Python das Original direkt per boto3 (`content_loader.py`), ohne dass Java eine Presigned-URL mitgeben muss.
3) Python erkennt `content_type=pdf`.
4) PDF wird in einzelne Seiten überführt.
5) Pro Seite:
   - Seitenbild mit fixer Zielbreite rendern (default 1280px, default JPEG)
   - Text-Layer lokal extrahieren als `extracted_text` (best effort)
   - Seite mit Gemini Embedding 2 embeddeden
   - Row in Supabase (`rag_chunks`) schreiben mit:
     - `embedding`
     - `metadata.evidence_type=pdf_page`
     - `metadata.locator.pageNumber`
     - `metadata.storage_refs` (zeigt auf Original oder auf **hochgeladenes Seitenbild** unter `{contentKey}/pages/{n}.…`, wenn Worker-Upload aktiv war)
     - `text_content=extracted_text`
     - `metadata.extraction_quality`, `metadata.layout_complexity`, `metadata.has_tables`, `metadata.has_figures`
   - Optional: gerendertes Seitenbild nach S3 **uploaden** (`object_storage.upload_pdf_page_image`), damit Chat/Flash später dasselbe Derivat per Java-Resolve laden kann.
6) Job endet in `active` (oder `error` mit Fehlertext).

---

## 2. Ablaufdiagramm

```mermaid
flowchart TD
  A[Java marks upload complete] --> B[n8n index workflow]
  B --> C[Python /v1/rag/index]
  C --> D[Load PDF bytes base64 URL or S3 worker GET]
  D --> E[Split into pages]
  E --> F[Render page image]
  F --> G[Extract page text optional]
  G --> H[Gemini Embedding 2 per page]
  H --> I[Store vector + locator.pageNumber + storageRef]
  I --> J[Job status active/error]
```

---

## 3. Answering-Bezug (wichtig für Wartung)

- Retrieval nutzt Embeddings + ggf. extractedText.
- In der Antwortphase sieht Flash die **Top-Seiten wirklich visuell** (Layout/Tabellen/Diagramme).
- Nachbarseiten (`p-1`, `p+1`) werden nur bei Bedarf ergänzt, um Kosten zu kontrollieren.

---

## 4. Fehlerfälle

- PDF kann nicht gelesen werden: Job auf `error`, Hinweis in Job-Status.
- Embedding einzelner Seite scheitert: Seite überspringen oder Job failen (Policy festlegen); aktuell fail-fast.
- Fehlende Storage-Refs: Fallback-Ref `inline` wird gesetzt, damit Retrieval nicht bricht.

---

## Relevante Dateien

| Bereich | Datei |
|---|---|
| Processing | `services/rag_service/src/rag_service/processors.py` |
| Indexing orchestration | `services/rag_service/src/rag_service/service.py` |
| Content load (Base64 / URL / S3 worker) | `services/rag_service/src/rag_service/content_loader.py` |
| S3 worker (GET/PUT) | `services/rag_service/src/rag_service/object_storage.py` |
| API entry | `services/rag_service/src/rag_service/main.py` |
| DB schema | `services/rag_service/schema.sql` |
