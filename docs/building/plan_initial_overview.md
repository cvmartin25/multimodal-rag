## Build Plan (27.04.2026) – Java Backend + n8n Chat + Python RAG Service

Dieses Dokument ist die **vollständige, fortlaufend erweiterbare Spezifikation** für die geplante Erweiterung:

- **Java Backend** bleibt “Source of Truth” (Tenancy/Auth/Stripe/Policies/Statusmaschinen).
- **n8n** ist die Chat- & Agent-Laufzeit (Memory, Tool-Calling, LLM-Orchestrierung).
- **Python RAG Service** macht das “Heavy Lifting” (Preprocessing, Indexing, Retrieval; multimodal).

Ziel: Man kann das System später umsetzen/weiterentwickeln, **ohne diesen Chat** zu benötigen.

---

## 1) Zielbild (High-level)

### 1.1 Komponenten & Verantwortlichkeiten

#### Java Backend (Source of Truth)
- **Auth & Rollen** (z. B. Clerk), User State, `coachProfileId` (“coachId”) aus DB.
- **Tenancy-Enforcement**: jede Operation ist scoped auf `coachProfileId`.
- **S3 Ownership & Policies**: canonical storage keys; Zugriff nur über presigned URLs.
- **Statusmaschinen** für Uploads/Jobs (z. B. `pending_upload → uploaded → processing → active/error`).
- **Batch-Resolve**: presigned URLs serverseitig ausstellen (Audit/Logging).
- **Limits/Quotas** pro Coach (Chat, Indexing, Storage, etc.).

#### n8n (Chat/Agent Runtime)
- **Agent Node**: Memory, Tool-Calling, Prompting/Orchestrierung.
- Ruft **genau zwei Tools** auf (siehe Kapitel 3):
  1) Python `retrieve`
  2) Java `resolve-media-refs` (Batch)
- Ruft anschließend **Gemini Flash** (oder anderes Modell) auf, um die finale Antwort zu generieren.

#### Python RAG Service (Processing Plane)
- **Indexing**:
  - PDFs: Seitenlogik, Seitenbilder, optional extractedText, Embedding-Schreiben.
  - Videos: Relevanz-Flagging (Flash), Segmentierung, Windowing, Embedding-Schreiben.
- **Retrieval**: Query → (Embedding) → Vektor-/Hybrid-Suche → Evidence-Paket ohne URLs.
- **Keine** Chat-Memory-Logik, keine UI; deterministische Services.

---

## 2) Kernprinzipien (nicht verhandelbar)

### 2.1 Tenancy / Trust
- `coachProfileId` kommt **immer** aus dem Java Backend (DB-basiert), nicht aus Client-Text.
- n8n muss `coachProfileId` als **trusted Kontext** erhalten (z. B. Java → n8n Webhook-Aufruf mit `coachProfileId` oder signiertem Token).
- Python vertraut nicht auf frei gelieferte IDs aus dem Usertext; Python arbeitet **immer tenant-scoped**.

### 2.2 “2 Calls Sweet Spot” für Chat
- **Call 1**: n8n → Python `retrieve` (liefert `storageRef` + `locator`, keine URLs)
- **Call 2**: n8n → Java `resolve-media-refs` (Batch, liefert presigned URLs)
- **LLM**: n8n → Gemini Flash mit (URLs + Locator + Hints + Memory)

**Default-Parameter (MVP)**
- `topK` (retrieve): **8**
- `topN` (resolve + Flash): **3**
- `expiresInSeconds` (presigned URLs): **300s**

### 2.3 Keine permanenten privaten URLs
- Es werden **keine** dauerhaft öffentlichen URLs gespeichert.
- `storageRef` (bucket/key) ist canonical; presigned URLs sind kurzlebig (z. B. 5 Minuten).

### 2.4 Multimodal “on-demand”
- Bei PDFs/Videos wird Flash in der Antwortphase **nur** für Top-N Evidences genutzt (z. B. N=3).
- Indexing-time Flash ist nur dort erlaubt, wo es massiv \(N\) reduziert oder Qualität stark verbessert (z. B. Video-Relevanzpass).

---

## 3) API Contracts (stabil, versioniert)

Alle Endpunkte sind **versioniert** (z. B. `/v1/...`), um spätere Evolution ohne Bruch zu erlauben.

### 3.1 Python Tool: `POST /v1/rag/retrieve`

**Zweck**: Liefert multimodale Evidences für eine Userfrage, **ohne** presigned URLs.

#### Request (minimal)
- `requestId`: string (ULID/UUID) – tracing
- `tenant.coachProfileId`: string/uuid – muss trusted sein
- `query.text`: string
- `options.topK`: int (z. B. 8–20)
- `options.types`: array (z. B. `["pdf_page","video_window"]`)
- optional `options.timeRange`, `options.sourceIds`, `options.labels`
- optional `debug`: boolean

**Wichtig (aus dem Chat, häufiges Missverständnis)**
- Embedding-Modelle liefern **keinen** Chunk-Text/Summary “zurück”. Alles Textliche, was gespeichert wird (z. B. `extractedText` bei PDF oder Segment-Summary bei Video), ist **eigene Pipeline-Logik** (Extraktion/Flash), nicht “Embedding-Output”.

#### Response (minimal)
- `requestId`
- `evidences[]` (siehe Evidence Schema)
- optional `hintsForLLM[]` (kurze Hinweise pro Evidence)
- optional `debug` (scores, modelId, timing)

#### Hard rules
- Ergebnis ist **tenant-scoped** (`coachProfileId`).
- `evidences[].storageRefs` enthalten **nur** `bucket/key` (oder equivalent), niemals URLs.
- Python darf intern Query-Embedding machen (empfohlen), damit n8n keine Embedding-Nodes benötigt.

### 3.2 Java Tool: `POST /api/media:resolve` (Batch)

**Zweck**: Batchweise presigned GET URLs für `storageRef`s ausstellen.

#### Request (empfohlen)
- `requestId`
- `coachProfileId`
- `expiresInSeconds` (z. B. 300)
- `items[]`:
  - `evidenceId`
  - `refs[]`: `{bucket,key}`

#### Response (empfohlen)
- `requestId`
- `expiresAt`
- `resolved[]`:
  - `evidenceId`
  - `urls[]`: `{bucket,key,url,contentType,expiresAt}`
- `denied[]`:
  - `evidenceId`
  - `ref`
  - `reason` (FORBIDDEN/NOT_FOUND/...)

#### Warum Mapping auf `evidenceId`?
- n8n bleibt “dumm”: kein Join nötig, weniger Workflow-Bugs, weniger Zeitverlust.

**Batch bedeutet außerdem**
- n8n dedupliziert `(bucket,key)` über alle TopN Evidences.
- Java resolved in **einem** Request (statt N Requests pro Evidence).

### 3.3 Auth (MVP → Produkt)

#### MVP
- Service-to-service Auth über **Header Secret** (Bearer).
- Mindestanforderungen:
  - TLS only
  - Secrets niemals loggen
  - Rotation möglich
  - (Optional) IP allowlist / private networking

#### Produktionsreife (später)
- HMAC-signierte Requests **oder** mTLS **oder** JWT service-to-service.
- Ziel: Replay-Schutz, per-service Scopes, bessere Audits.

---

## 4) Evidence Schema (zentrales Datenmodell)

Ein Evidence Record ist ein standardisiertes Paket, das n8n/LLM/Frontend konsistent behandeln kann.

### 4.1 Gemeinsame Felder (alle Types)
- `id` (evidenceId): string
- `type`: `"pdf_page"` | `"video_window"` | später `"audio_window"` | `"image"` | `"text_chunk"`
- `tenant.coachProfileId`
- `source`:
  - `kind`: `"document"` | `"video"` | `"audio"` | `"image"`
  - `documentId` / `videoId` / ...
- `locator`: type-spezifisch (siehe unten)
- `storageRefs[]`: array von `{kind:"s3", bucket, key}`
- `display`: UI-freundliche Felder (`filename`, `title`, `label`)
- `score`: float (optional)
- `labels[]`: z. B. `["teaching"]`, `["qa"]` (optional)
- `hintForLLM`: kurzer Hinweis (optional; kann auch getrennt in `hintsForLLM[]` kommen)

### 4.2 PDF Evidence: `pdf_page`
- `locator.pageNumber`: int (**Konvention festlegen**: 1-based empfohlen)
- `storageRefs` enthält i. d. R. das Seitenbild (`.../pages/{n}.png`) und optional das Original-PDF.
- Optional: `extractedText` (für Hybrid & Debug, nicht als “Quelle der Wahrheit”)

**Hinweis zu “Overlap”**
- Nicht als Chunk-Overlap beim Indexing, sondern als **Neighbour Pages** beim Answering:
  - Wenn Seite 12 getroffen: Flash bekommt optional Seite 11–13, aber nur wenn nötig.

### 4.3 Video Evidence: `video_window`
- `locator.startSec`, `locator.endSec`, optional `locator.paddingSec`
- `storageRefs` enthält i. d. R. das Originalvideo (oder später ein segmentiertes Derivat).
- Optional: `segmentId` als Verweis auf Analyse-Segment (siehe Kapitel 6).

### 4.4 Audio Evidence: `audio_window` (später)
- Wie `video_window`, nur Audiofile als `storageRef`.
- Wird fürs Schema vorgesehen, aber zunächst nicht implementiert (MVP: Text+PDF+Video).

---

## 5) Chat Answering Flow (n8n)

### 5.1 Ablauf
1) n8n Agent Node nimmt `question` + `memory` entgegen, kennt `coachProfileId` (trusted).
2) Tool-Call: Python `retrieve` mit `coachProfileId` + `question` → `evidences[]`.
3) n8n nimmt **TopN** (z. B. 3) evidences, extrahiert `storageRefs`, dedupliziert.
4) Tool-Call: Java `resolve-media-refs` (Batch) mit den TopN refs → presigned URLs.
5) n8n ruft Gemini Flash:
   - Prompt: Frage + Memory + “Evidence Pack”
   - Attachments: URLs + Locator + hintForLLM
6) n8n liefert Antwort zurück + optional strukturierte “citations” (Seite/Timestamp).

### 5.2 PDF “Seite wirklich ansehen” (Entscheidung)
Für PDFs ist der Standard:
- Retrieval nutzt Embeddings + optional extractedText.
- **Answering**: Flash bekommt die **Top 3 Seiten als Seitenbild/PDF-Seite** (presigned URLs) und darf **Layout, Tabellen, Diagramme** interpretieren.
- Optional: Flash bekommt zusätzlich den `extractedText` als “schnell lesbaren” Zusatz, aber die visuelle Seite ist “Ground Truth”.

Das ist bewusst **on-demand** (nur TopN), damit es nicht teuer wird.

### 5.3 Q&A Policy (Sicherheit)
Risiko: Teilnehmer nennt falsche Fakten; das System zitiert diese als “Wahrheit”.

Empfohlene Policy:
- Q&A Inhalte werden **gelabelt** (z. B. `qa`) und nicht gelöscht.
- Retrieval default: `teaching` bevorzugen.
- Q&A nur:
  - wenn User explizit danach fragt (“Fragerunde”, “Teilnehmerfrage”)
  - oder wenn keine Teaching Evidence vorhanden ist.
- Prompting: Q&A Zitate als “In der Fragerunde wurde gesagt …” kennzeichnen, nicht als Fakt behaupten.

**Zusatz (MVP Default)**
- Q&A wird **indexiert**, aber bei Retrieval standardmäßig **downranked** (oder per `labels`-Filter ausgeschlossen), bis der User explizit nach Q&A fragt.

---

## 6) Indexing Pipelines (Python)

### 6.1 PDF Pipeline (Seitenlogik)

**Ziel**: Jede Seite ist eine semantische Einheit, die Flash später multimodal interpretieren kann.

Schritte:
1) Input: `documentId`, `coachProfileId`, S3 key des Originals.
2) PDF → Seitenbilder rendern (PNG/JPG) + optional Seiten-PDFs.
3) Optional: extractedText pro Seite (für Hybrid/Debug; nicht zwingend OCR, sondern PDF-Text falls vorhanden).
4) Embedding pro Seite:
   - Input an Embedding: Seitenbild oder Seiten-PDF (je nach Modellunterstützung)
   - Output: Vektor
5) Speichern pro Seite:
   - embedding
   - `locator.pageNumber`
   - `storageRef` zur Seitenimage
   - optional `extractedText` / kurzer Seitentitel
6) Status update: `processing → active` oder `error`.

**Answering-time**
- Flash bekommt TopN Seiten als Bild (plus optional Neighbour Pages), nicht nur extractedText.

**Neighbour Pages Policy (empfohlen)**
- Standard: nur TopN Seiten.
- Bei “Seitenübergreifenden” Antworten darf Python/n8n zusätzlich `pageNumber-1` und `pageNumber+1` resolved mitgeben (max. +2 Seiten), aber nur wenn:
  - `extractedText` auf “Fortsetzung”/abgeschnittene Sätze hindeutet, oder
  - Flash explizit nach Kontext fragt.

### 6.2 Video Pipeline (Relevanzpass → Windowing → Embedding)

**Ziel**: Nicht das ganze Video embedden, sondern nur relevante Teile, um Kosten & Datenmenge \(N\) zu reduzieren und Retrieval-Qualität zu erhöhen.

#### Stage A: Flash Relevanz-Analyse (einmal pro Video)
Flash schaut das Video (in geeigneter Sampling-Strategie) und gibt eine Liste relevanter Segmente zurück.

Output pro Segment (empfohlen):
- `segmentId`
- `startSec`, `endSec`
- `label`: `teaching` | `qa` | `admin` | `noise` (minimal)
- `summary`: 1–3 Sätze
- optional `tags[]`: 5–15 Keywords
- optional `whyRelevant`: 1 Satz (Debug)

**Hinweis zur Kostenkontrolle**
- Keine “Flash Summary pro Window”.
- Summary/Tags **nur pro Segment**, Windows referenzieren `segmentId`.

Warum Segment-Summary?
- Vermeidet “Flash Summary pro Window” (teuer).
- Liefert Textmetadaten für Hybrid-Filter, UI und Debug.

#### Stage B: Windowing (nur innerhalb relevanter Segmente)
Beispiel-Policy:
- Windows: 110–120s
- Overlap: 10s

Erzeuge Windows nur für Segmente mit `label in {"teaching","qa"}` (qa je nach Policy).

#### Stage C: Embedding (nur relevante Windows)
- Embedding Model erzeugt Vektor pro Window (multimodal).
- Speichere pro Window:
  - embedding
  - `locator.startSec/endSec/paddingSec`
  - `segmentId` (Ref auf Segment-Metadaten)
  - `storageRef` auf Originalvideo (oder Derivat)

**Answering-time**
- Flash bekommt das Originalvideo als URL plus Locator (Zeitfenster + Puffer).
- Flash soll den logischen Satzanfang finden und korrekt zitieren (Timestamp).

---

## 7) Datenmodell / Storage (Supabase/pgvector + S3)

### 7.1 Canonical StorageRefs
- Originaldokumente/-videos liegen unter canonical keys, z. B.:
  - `mycoach/{coachProfileId}/documents/{documentId}/original`
  - `mycoach/{coachProfileId}/documents/{documentId}/pages/{page}.png`
  - `mycoach/{coachProfileId}/videos/{videoId}/original`

### 7.2 “Textspalte pro Vektor” – was gilt wann?
- **Text embedding**: Text kommt nicht “vom Embedding zurück”; er muss aus eurem Chunking stammen und gespeichert werden (z. B. `text_content`).
- **PDF-Seiten**: extractedText kann gespeichert werden (wenn verfügbar), ist aber nicht die primäre Quelle der Wahrheit.
- **Video**: keine natürlichen Textchunks; speichert Segment-Summary/Tags als Textmetadaten.

### 7.3 Skalierung / Performance (große Coaches)

Problem:
- Gemini Embedding 2 nutzt 3072 dims.
- pgvector HNSW hat (laut bisherigem Stand) ein Dim-Limit von 2000 → HNSW nicht nutzbar.
- Ohne passenden ANN-Index droht exact scan; Query-Zeit wächst mit Anzahl Vektoren pro Coach.

#### 7.3.1 Concurrency vs. “Anzahl Nutzer”
Performance-Probleme entstehen meist durch **gleichzeitige Requests**, nicht durch MAU/DAU.

Faustformel:

\[
Concurrency \approx RPS \times \text{mittlere Request-Dauer (s)}
\]

Beispiel:
- 100 aktive User stellen im Schnitt alle 30s eine Frage → ~3.3 RPS
- End-to-End (retrieve + resolve + Flash) dauert ~6s → Concurrency ~20

#### 7.3.2 Wann exact scan kritisch wird (Daumenregeln)
Ohne ANN-Index und ohne Two-stage Retrieval steigt Query-Zeit grob linear mit \(N\) (Vektoren pro Coach).

Richtwerte pro Coach (tenant-scope):
- ~10k Vektoren: oft noch “ok-ish”
- ~10k–50k: spürbar, bei Peaks kritisch
- ~50k–200k: interaktiver Chat wird ohne Gegenmaßnahmen oft unangenehm

Diese Schwellen hängen stark von DB-Tuning und Parallelität ab, sind aber gute Planungswerte.

Deshalb muss die Architektur **von Anfang an** mindestens diese Hebel vorsehen:
- harte Tenant-Filter (`coachProfileId`)
- Reduktion \(N\) durch Video-Relevanzpass
- Hybrid/Two-stage Retrieval (Text+Meta vor Vektor) sobald Daten wachsen
- TopN klein (z. B. 3) für presigned+Flash

**Two-stage Retrieval (geplant)**
- Stage 1: günstige Vorauswahl über Metadaten + Textindex (BM25) auf extractedText / Segment-Summaries / Tags
- Stage 2: Vektorsuche auf Kandidatenmenge

**Langfrist-Option**
- Falls pgvector die Ziel-Performance nicht schafft: “Vector Backend” austauschbar machen (Qdrant/Milvus/Weaviate/Pinecone), ohne dass n8n/Java Contracts brechen.

#### 7.3.3 pgvector vs. “echte” Vector DB (Begriffsdefinition)
- **pgvector**: Embeddings liegen in Postgres (Supabase). Vorteile: SQL-Filter, weniger Infrastruktur. Nachteil: ANN-Optionen/Performance können limitieren (hier: HNSW-Dim-Limit).
- **Vector DB**: Spezialdatenbank für ANN/Scale. Vorteile: starke ANN-Performance bei großen Datenmengen/QPS. Nachteil: extra System, Sync/ACL/Backup-Design.

Strategie: MVP kann pgvector sein, aber das Python `retrieve` soll so designt werden, dass das Vector-Backend später austauschbar bleibt.

---

## 8) Kostenhebel (damit es wirtschaftlich bleibt)

Multimodal ist teurer als Text-only. Kosten werden planbar, wenn:
- Video-Relevanzpass reduziert Einbettungen drastisch.
- Keine Flash-Summaries pro Window, nur pro Segment.
- TopN (Flash-ready) ist klein (3–5).
- Caching für häufige Queries (kurzfristig) möglich ist.
- Indexing wird als Setup-Leistung bepreist (Setup Fee) + laufende Seats/Quotas.

**Produkt-UX Leitplanke (empfohlen)**
- Coaches werden im Onboarding zu “kuratiert starten” angeleitet (Referenzvideos pro Thema), aber es gibt einen bezahlten “Indexiere alles”-Pfad (Setup).

---

## 9) Wochenreports: “häufigste Fragen pro Coach”

Ziel: Coaches bekommen einen Mehrwert-Service: “Was fragen Kunden am häufigsten / was wird nicht verstanden?”

### 9.1 Minimal-Ansatz (empfohlen): Wochenreport ohne RAG-Explorer
- Pro Userfrage wird ein Record geloggt (pro Coach).
- Ein wöchentlicher Batch-Job erstellt Aggregation/Cluster/Ranking.
- Coach sieht:
  - Top Themen
  - paraphrasierte Beispiel-Fragen
  - Trends vs Vorwoche
  - “Content gaps” (z. B. viele Fragen, aber häufig “keine Evidenz” oder viele negative Votes)

### 9.1.1 Wochenreport-Workflow (konkret)
- Trigger: 1× pro Woche (Cron in n8n)
- Input: alle `coach_questions` der letzten 7 Tage (scoped auf `coachProfileId`)
- Schritte:
  - Normalisierung/PII-Strip (falls nicht schon beim Logging)
  - Gruppierung in Themen (einfacher Start: LLM “group similar questions”; später: Embedding+Clustering)
  - Summary pro Thema + Trend vs Vorwoche
- Output: `coach_weekly_reports` (JSON) + “Top Topics” Tabelle (optional)

### 9.2 Datenspeicherung (nicht zu groß)
Um Tabellenwachstum zu kontrollieren:
- Retention: Klartext-Fragen z. B. 6–12 Monate, ältere Daten nur aggregiert.
- Speichere nicht komplette Prompt/Antwort/Evidence-Dumps, nur:
  - `coachProfileId`, `createdAt`, `questionText` (PII-gestrippt), optional `feedback`, optional `answerHadEvidence`.

**Retention Default (Vorschlag)**
- Klartext-Fragen: 12 Monate
- Wochenreports: dauerhaft

### 9.3 “RAG später” ohne Umbau ermöglichen
- Optional Feld/Tabelle für `questionEmbedding` vorsehen (kann initial leer bleiben).
- Damit kann später ein “Explorer” gebaut werden (“ähnliche Fragen zu Thema X”), ohne Schema-Refactor.

---

## 10) Offene Punkte / TODOs (bewusst markiert)

Diese Punkte müssen vor Umsetzung final entschieden werden:
- **Locator-Konvention**: `pageNumber` 1-based? Timestamp rounding? Padding Default?
- **Labels**: Minimalset für Video-Segmente (z. B. `teaching/qa/noise/admin`) finalisieren.
- **Q&A Default Policy**: standardmäßig aus oder nur als “QA-zitiert”-Modus?
- **Resolve Expiry**: Default `expiresInSeconds` (z. B. 300).
- **Auth Upgrade Path**: Wann Wechsel von Header secret auf HMAC/mTLS/JWT?
- **Vector-Backend Strategie**: pgvector-only vs. spätere Migration; Two-stage Retrieval ab welchem \(N\) verpflichtend?
- **Indexing Trigger**: genaue Orchestrierung (Java→n8n→Python) und welche Status in Java persistiert werden.

### 10.1 Empfohlene Default-Entscheidungen (damit wir starten können)
- `pageNumber` Konvention: **1-based**
- `topK/topN`: **8/3**
- `expiresInSeconds`: **300**
- Q&A Default: **indexiert + label `qa`, aber standardmäßig nicht als “Faktenquelle”** (downrank / filter)

### 10.2 Normen (Locator, Zeit, Padding) – Default für Implementierung
Diese Normen sind bewusst “boring defaults”, damit UI/Backend/Python/n8n konsistent bleiben.

- **PDF `pageNumber`**: **1-based** (Seite 1 = erste Seite im PDF).
- **Video/Audio Zeitangaben**:
  - `startSec/endSec/paddingSec` sind **integers in Sekunden**.
  - UI darf mm:ss anzeigen; Backend bleibt in Sekunden.
  - **Rounding**: bei Ableitung aus Frames/Timecodes immer auf die **nächste volle Sekunde nach unten** (floor), damit keine “zu späten” Starts entstehen.
- **Padding Default**:
  - Wenn nicht explizit gesetzt: `paddingSec = 30` (Answering-time), damit Flash Satzanfang findet.
  - Hard cap: `paddingSec <= 60` (Kosten/Context begrenzen).
- **Window-Policy Default (Video)**:
  - `windowLenSec = 120`
  - `windowOverlapSec = 10`
  - Schrittweite = 110s

### 10.3 Indexing-Trigger & Job-of-Record (konkret, MVP)
Ziel: Java bleibt Owner von Tenancy/Status; n8n orchestriert; Python arbeitet.

#### 10.3.1 Entities (konzeptionell)
- **Java DB** hält Records für:
  - `documents` / `videos` (inkl. `status`)
  - `rag_jobs` (optional, aber empfohlen) mit `jobType`, `status`, `error`, `progress`
- **Supabase/Vector Store** hält Evidence/Embedding-Records (nicht “Job-of-record”).

#### 10.3.2 Statusmaschine (Minimalset)
- Für Dokument/Video:
  - `pending_upload` → `uploaded` → `processing` → `active` | `error`
- Für Job:
  - `queued` → `running` → `succeeded` | `failed`

#### 10.3.3 Trigger Flow (MVP)
1) Frontend lädt Datei via Java presigned PUT hoch.
2) Java setzt nach `complete-upload`: `status=uploaded`.
3) Java stößt Indexing an:
   - Variante MVP: Java ruft n8n Webhook `index-start` mit `{coachProfileId, documentId|videoId}`.
4) n8n Workflow:
   - ruft Python `/v1/rag/index` (oder getrennt `/v1/index/document` / `/v1/index/video`) mit IDs.
5) Python:
   - setzt Java-Status auf `processing` (über Java Endpoint oder DB-Update-Mechanismus)
   - führt Pipeline aus (PDF/Video)
   - schreibt Embeddings/Evidence nach Supabase
   - setzt Java-Status auf `active` oder `error` + Fehlerdetails

**Warum so?**
- Java bleibt der Ort, wo UI/Policy/Quotas sauber hängen.
- n8n bleibt der Orchestrator (Retries/Dead-letter möglich).
- Python bleibt “Worker/Processing Plane”.

### 10.4 Skalierungsstrategie als Entscheidungspfad (damit wir nicht umbauen müssen)
Wir starten pragmatisch mit Supabase/pgvector, aber planen bewusst den “Exit”, falls \(N\) groß wird.

#### 10.4.1 Sofort (MVP) – pgvector + starke Reduktion
- Tenant-filter immer (`coachProfileId`)
- Video-Relevanzpass (Flash) ist Pflicht, um \(N\) klein zu halten
- Retrieval: `topK=8`, signieren/Flash: `topN=3`

#### 10.4.2 Ab wann Two-stage Retrieval Pflicht wird (Planungsregel)
Wenn eines der folgenden Kriterien pro Coach erreicht ist, wird Two-stage (Text/Meta Vorfilter → Vector) Pflicht:
- **> 50k Vektoren** in tenant-scope, oder
- **Peak Concurrency > 10** für Retrieval, oder
- p95 Retrieval-Zeit > 800ms (ohne LLM)

#### 10.4.3 Vector Backend “Swap” (falls nötig)
Python `retrieve` kapselt den Vector Store Zugriff so, dass wir später wechseln können:
- pgvector/Supabase → Qdrant/Milvus/Weaviate/Pinecone
ohne die n8n Tools oder Java Resolve Contracts zu ändern.

---

## 11) Implementierungsreihenfolge (MVP Roadmap)

1) Evidence Schema + Contracts (`retrieve`, `resolve-media-refs`)
2) Java Batch-Resolve Endpoint + Tenancy checks + Auditing
3) Python `retrieve` minimal: Query embedding + vector search + evidence output (ohne Video-Flagging zunächst möglich)
4) PDF Indexing: Seitenbilder + embeddings + storageRefs
5) Video Indexing Stage A (Flash segments) + Stage B/C (Window embeddings)
6) n8n Agent Workflow: 2 Tools + Flash Answering + UI citations
7) Wochenreport: question logging + weekly aggregation + coach view
8) Skalierung: Two-stage retrieval + caching + quotas

