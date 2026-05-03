## Delta: Alt vs Neu (Stand 2026-04-30)

Diese Datei fasst die wichtigsten Architektur- und Flow-Aenderungen gegenueber dem vorherigen Stand zusammen.

---

## 1) Betriebsmodus

- **Alt**: Workmode + Research/Proof als gemischte Zielrichtung.
- **Neu**: **Proof-first** als aktive Implementierung; Workmode vorerst nicht umgesetzt.

Auswirkung:
- Antworten sind auf Belegbarkeit optimiert (Paraphrase + Referenzen), nicht auf maximal billige Standardantworten.

---

## 2) Video-Indexing

- **Alt**: Fokus auf `video_window` (Window-basiertes Embedding aus Videofenstern).
- **Neu**: **Transcript-first** mit Whisper:
  - Relevanzsegmente (Flash full-pass/fallback) -> Time-Ranges
  - Transkription (`whisper-1`, Segment-Timestamps)
  - Span-Building (~40s variabel, max ~60s)
  - Embedding auf Transcript-Text
  - Speicherung als `video_span` mit absoluten `startSec/endSec`

Auswirkung:
- bessere Skalierbarkeit/Kostenkontrolle
- direkte Timestamp-Evidenz fuer den Player

---

## 3) PDF-Indexing

- **Alt**: PDF Seite als Chunk, Text optional und weniger strikt beschrieben.
- **Neu**:
  - Seite bleibt Chunk (`pdf_page`) mit multimodalem Embedding
  - `extracted_text` wird best-effort lokal gespeichert
  - feste Render-Defaults (Breite/Format/Qualitaet)
  - zusaetzliche Metadaten je Seite:
    - `extraction_quality`
    - `layout_complexity`
    - `has_tables`
    - `has_figures`

Auswirkung:
- stabilere Proof-Entscheidungen, bessere Debugbarkeit, spaeterer Workmode ohne Re-Index moeglich

---

## 4) Retrieval und Zitierformat

- **Alt**: Quellenhinweise vorhanden, Format noch offener.
- **Neu**: IEEE-artiges Zielbild explizit:
  - Antwort in eigenen Worten
  - Referenzliste wie `[1] PDF <Titel> Seite X`, `[2] Video <Titel> Minute mm:ss`

Auswirkung:
- konsistentere UX fuer Belege und sauberere Nachvollziehbarkeit.

---

## 5) Schema / Supabase

- **Alt**: generischer `documents`-Pfad mit `match_documents`.
- **Neu**:
  - `rag_sources`
  - `rag_chunks` mit `vector(3072)` (Gemini Embedding 2 fix)
  - `match_rag_chunks(...)` inkl. Tenant-Filter

Auswirkung:
- klareres Datenmodell fuer Source/Chunk-Trennung
- sauberer auf Proof-first zugeschnitten

---

## 6) Input-Pfad im Indexing

- **Alt**: primaer `contentBase64`.
- **Neu**: `contentUrl` (presigned) **oder** `contentBase64`.

Auswirkung:
- besser fuer Bucket-zentrierte Produktion und groessere Dateien.

---

## 7) Konfiguration / Stellschrauben

- **Neu hinzugekommen**:
  - `OPENAI_API_KEY`
  - `RAG_WHISPER_MODEL`
  - `RAG_TRANSCRIPT_LANGUAGE`
  - `RAG_TRANSCRIPT_TARGET_SPAN_SECONDS`
  - `RAG_TRANSCRIPT_MAX_SPAN_SECONDS`
  - `RAG_PDF_RENDER_TARGET_WIDTH`
  - `RAG_PDF_RENDER_FORMAT`
  - `RAG_PDF_RENDER_QUALITY`

Auswirkung:
- klar definierte Kosten-/Qualitaetshebel fuer Video und PDF.

---

## 8) Was unveraendert bleibt

- Java bleibt Source of Truth fuer Tenancy, Policy und Presigned URL Resolve.
- n8n bleibt Orchestrierungsschicht (Workflow, Retry, Promptaufbau).
- Python bleibt Worker fuer Indexing und Retrieval.
- Tenancy wird weiterhin serverseitig erzwungen.

